#!/usr/bin/env python3
"""refine — 2nd-brain-parser 의 post 단계(결정형 helper; 판단은 SKILL.md 의 LLM).

extract(2nd-brain-parser 컨테이너 + parser-drain)가 만든 `_parse/{docling,mineru,diff}.json`
을 읽어 **단일 권위 풀텍스트 `refined.md`** 를 만든다. match/single 은 결정형 승격(LLM 0),
diverge 만 LLM 이 두 markdown 을 비전검증·보정해 write 한다.
이미지는 docling 대신 `ocr.json` 하나만 나오며(스키마 동일), 이것도 1차 소스로 인정한다 —
mineru 짝이 없어 verdict='single' → promote 경로(2026-08-05 추가, `_primary()` 주석 참조).

서브커맨드 (모두 stdout JSON):
  scan [--root D]      D(기본 00_inbox) 아래 refined.md 없는 `*_parse/` 나열 + verdict·needs_llm.
  read  <parse_dir>    verdict·metrics·details·docling.md·mineru.md (LLM 보정 재료).
  promote <parse_dir>  match/single → docling markdown 그대로 refined.md (결정형, LLM 0).
  write <parse_dir> ... diverge → LLM 보정본(--body-file) + frontmatter → refined.md.

핸드오프: refined.md 존재 = refine 완료(멱등 마커). 그 뒤 brainify 가 refined.md 만 소비.
refined.md frontmatter 규약은 구 brainify-inbox §3 에서 계승(source_pdf·base_engine·corrections·generated·host).

환경변수:
  REFINE_VAULT   정본 vault (기본 ~/projects/2nd-brain-vault)
"""
from __future__ import annotations
import argparse
import datetime
import json
import os
import pathlib
import socket
import sys

VAULT = pathlib.Path(os.path.expanduser(os.environ.get("REFINE_VAULT", "~/projects/2nd-brain-vault")))
INBOX = VAULT / "sources" / "00_inbox"


def _load(p: pathlib.Path) -> dict | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _source_of(parse_dir: pathlib.Path) -> pathlib.Path:
    """`<원본.ext>_parse/` → `<원본.ext>` (parser-drain 신규 규약)."""
    name = parse_dir.name
    return parse_dir.parent / (name[:-len("_parse")] if name.endswith("_parse") else name)


def _verdict(parse_dir: pathlib.Path) -> tuple[str, dict | None]:
    """diff.json 의 verdict. 없으면 'single'(비-PDF/mineru 부재 — 듀얼 비교 불가)."""
    diff = _load(parse_dir / "diff.json")
    if diff is None:
        return "single", None
    return diff.get("verdict", "?"), diff


def _primary(parse_dir: pathlib.Path) -> tuple[str, dict | None]:
    """풀텍스트의 1차 소스. `(파일명, 내용)` — 없으면 `("", None)`.

    docling.json 이 표준이지만 **이미지는 `ocr.json` 하나만 나온다**(extract 의 parse-ocr 경로:
    image→mineru). 스키마는 docling.json 과 같다(markdown·via·pages). 이걸 인정하지 않으면
    OCR 이 성공해 텍스트를 다 뽑아 놓고도 refined.md 로 승격될 길이 없어 brainify 가 영구히
    stub(parse_confidence:low)을 쓴다 — 2026-08-05 실측으로 vault 에 그렇게 묶인 ocr.json 이
    46개였다. mineru 짝이 없으니 verdict 는 자연히 'single' → promote(결정형, LLM 0).
    """
    for name in ("docling.json", "ocr.json"):
        d = _load(parse_dir / name)
        if d:
            return name, d
    return "", None


def _candidates(root: pathlib.Path) -> list[pathlib.Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*_parse") if p.is_dir())


def cmd_scan(args) -> int:
    # --root 는 절대경로·vault 상대경로 둘 다 받는다. 예전엔 상대경로를 그대로 rglob 해서
    # 뒤의 relative_to(VAULT) 가 ValueError 로 죽었다(2026-08-05).
    if args.root:
        root = pathlib.Path(os.path.expanduser(args.root))
        if not root.is_absolute():
            root = VAULT / root
    else:
        root = INBOX
    items: list[dict] = []
    for pd in _candidates(root):
        engine_file, primary = _primary(pd)
        if not primary:
            # extract 미완/실패 — refine 불가
            items.append({"parse_dir": str(pd.relative_to(VAULT)), "status": "no-extract",
                          "parse_error": (pd / ".parse-error").exists()})
            continue
        done = (pd / "refined.md").exists()
        verdict, _ = _verdict(pd)
        items.append({
            "parse_dir": str(pd.relative_to(VAULT)),
            "source": str(_source_of(pd).relative_to(VAULT)),
            "verdict": verdict,
            "primary": engine_file,
            "has_mineru": (pd / "mineru.json").exists(),
            "refined": done,
            "needs_llm": (verdict == "diverge") and not done,
            "action": "skip(done)" if done else ("refine" if verdict == "diverge" else "promote"),
        })
    pending = [i for i in items if not i.get("refined") and i.get("status") != "no-extract"]
    print(json.dumps({"root": str(root), "count": len(items),
                      "pending": len(pending), "items": items},
                     ensure_ascii=False, indent=2))
    return 0


def cmd_read(args) -> int:
    pd = (VAULT / args.parse_dir) if not os.path.isabs(args.parse_dir) else pathlib.Path(args.parse_dir)
    if not pd.exists():
        print(json.dumps({"error": f"없음: {pd}"}, ensure_ascii=False)); return 1
    engine_file, primary = _primary(pd)
    docling = primary or {}
    mineru = _load(pd / "mineru.json")
    verdict, diff = _verdict(pd)
    out = {
        "parse_dir": str(pd),
        "source": str(_source_of(pd).relative_to(VAULT)),
        "source_abs": str(_source_of(pd)),
        "verdict": verdict,
        "primary": engine_file,
        "metrics": (diff or {}).get("metrics"),
        "thresholds": (diff or {}).get("thresholds"),
        "details": (diff or {}).get("details"),
        "docling": {"pages": docling.get("pages"), "via": docling.get("via"),
                    "markdown": docling.get("markdown", "")},
        "mineru": ({"pages": mineru.get("pages"), "markdown": mineru.get("markdown", "")}
                   if mineru else None),
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0


def _write_refined(pd: pathlib.Path, base_engine: str, corrections: list[str],
                   body: str, confidence: str) -> dict:
    source_rel = _source_of(pd).relative_to(VAULT)
    fm = ["---", f"source_pdf: {source_rel}", f"base_engine: {base_engine}"]
    if corrections:
        fm.append("corrections:")
        for c in corrections:
            fm.append(f'  - "{c}"')
    else:
        fm.append("corrections: []")
    fm += [
        f"generated: {datetime.date.today().isoformat()}",
        f"host: {socket.gethostname()}",
        f"refine_confidence: {confidence}",
        "---",
        "",
    ]
    out = pd / "refined.md"
    out.write_text("\n".join(fm) + body.rstrip("\n") + "\n", encoding="utf-8")
    return {"ok": True, "refined": str(out), "base_engine": base_engine,
            "corrections": len(corrections), "confidence": confidence}


def cmd_promote(args) -> int:
    """match/single → docling markdown 그대로 refined.md (결정형)."""
    pd = (VAULT / args.parse_dir) if not os.path.isabs(args.parse_dir) else pathlib.Path(args.parse_dir)
    engine_file, primary = _primary(pd)          # docling.json 우선, 없으면 ocr.json(이미지)
    if not primary:
        print(json.dumps({"error": f"docling.json·ocr.json 둘 다 없음/손상: {pd}"}, ensure_ascii=False)); return 1
    if (pd / "refined.md").exists() and not args.force:
        print(json.dumps({"ok": True, "skipped": "refined.md 이미 있음", "refined": str(pd / "refined.md")},
                         ensure_ascii=False)); return 0
    md = primary.get("markdown", "")
    conf = "low" if (primary.get("via") == "error" or len(md.strip()) < 20) else "ok"
    res = _write_refined(pd, primary.get("via", engine_file.removesuffix(".json")), [], md, conf)
    print(json.dumps(res, ensure_ascii=False)); return 0


def cmd_write(args) -> int:
    """diverge → LLM 보정본(--body-file) + 채택 엔진·사유 → refined.md."""
    pd = (VAULT / args.parse_dir) if not os.path.isabs(args.parse_dir) else pathlib.Path(args.parse_dir)
    if not pd.exists():
        print(json.dumps({"error": f"없음: {pd}"}, ensure_ascii=False)); return 1
    body = pathlib.Path(args.body_file).read_text(encoding="utf-8") if args.body_file else ""
    if not body.strip():
        print(json.dumps({"error": "본문(--body-file)이 비어 있음"}, ensure_ascii=False)); return 1
    res = _write_refined(pd, args.base_engine, list(args.correction or []), body, args.confidence)
    print(json.dumps(res, ensure_ascii=False)); return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="refine", description="2nd-brain-parser post 단계 helper")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ps = sub.add_parser("scan"); ps.add_argument("--root", default="")
    pr = sub.add_parser("read"); pr.add_argument("parse_dir")
    pp = sub.add_parser("promote"); pp.add_argument("parse_dir"); pp.add_argument("--force", action="store_true")
    pw = sub.add_parser("write")
    pw.add_argument("parse_dir")
    pw.add_argument("--base-engine", required=True, choices=["docling", "mineru", "vision", "merged"])
    pw.add_argument("--correction", action="append", help="보정 사유(반복 가능)")
    pw.add_argument("--body-file", required=True)
    pw.add_argument("--confidence", default="ok", choices=["ok", "low"])
    args = ap.parse_args(argv)
    return {"scan": cmd_scan, "read": cmd_read,
            "promote": cmd_promote, "write": cmd_write}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
