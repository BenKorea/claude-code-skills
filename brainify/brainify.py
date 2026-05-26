#!/usr/bin/env python3
"""brainify — 결정형 helper (메커니즘만; PARA 분류·요약 등 판단은 SKILL.md 의 LLM 이 한다).

서브커맨드 (모두 stdout JSON, 단 --help 제외):
  scan                 00_inbox 의 처리 대상 나열 + 중복(dedup) 상태.
  inspect <item>       항목의 markdown 추출(스레드 본문 + 첨부 2nd-brain-parser 파싱) + 식별자.
  commit  <item> ...   원본을 sources/<para>/<name>/ 로 이동 + knowledge/<para>/<name>.md
                       동반 노트(frontmatter+본문) 작성 + 정책 플래그 + inbox 비움.
  audit                플래그된(para_review:pending / parse_confidence:low) 노트 나열.

판단(LLM)은 inspect 와 commit 사이에서: 에이전트가 markdown 을 읽고 PARA 좌표·파일명·
요약·내생각·링크를 정해 commit 인자로 넘긴다 (자동 우선·주간 감사 정책).

환경변수:
  BRAINIFY_VAULT          정본 vault (기본 ~/projects/2nd-brain-vault)
  BRAINIFY_PARSER_IMAGE   2nd-brain-parser 이미지 (기본 ghcr.io/benkorea/2nd-brain-parser:latest)
  BRAINIFY_MODELS_VOLUME  HF 모델 캐시 볼륨 (기본 2nd-brain-docker_brain-pdf-models)
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

VAULT = pathlib.Path(os.path.expanduser(os.environ.get("BRAINIFY_VAULT", "~/projects/2nd-brain-vault")))
INBOX = VAULT / "sources" / "00_inbox"
KNOWLEDGE = VAULT / "knowledge"
SOURCES = VAULT / "sources"
PARSER_IMAGE = os.environ.get("BRAINIFY_PARSER_IMAGE", "ghcr.io/benkorea/2nd-brain-parser:latest")
MODELS_VOLUME = os.environ.get("BRAINIFY_MODELS_VOLUME", "2nd-brain-docker_brain-pdf-models")

# 2nd-brain-parser 가 파싱하는 확장자 (그 외는 첨부로만 보존, 본문 추출 안 함)
PARSEABLE = {".pdf", ".docx", ".pptx", ".xlsx", ".hwp", ".hwpx", ".doc", ".ppt", ".xls",
             ".odt", ".odp", ".ods", ".rtf"}


def _front(md_path: pathlib.Path) -> dict:
    """_thread.md 등의 단순 frontmatter(key: value) 파싱."""
    out: dict = {}
    try:
        txt = md_path.read_text(encoding="utf-8")
    except Exception:
        return out
    if not txt.startswith("---"):
        return out
    end = txt.find("\n---", 3)
    if end == -1:
        return out
    for line in txt[3:end].splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip().strip('"')
    return out


def _grep_knowledge(identifier: str) -> list[str]:
    """knowledge/ frontmatter 에서 식별자(threadId/sha)를 가진 노트 경로 — vault-wide dedup."""
    if not identifier or not KNOWLEDGE.exists():
        return []
    try:
        r = subprocess.run(["grep", "-rl", identifier, str(KNOWLEDGE)],
                           capture_output=True, text=True, timeout=30)
        return [l for l in r.stdout.splitlines() if l.strip()]
    except Exception:
        return []


def _sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _container_path(host_path: pathlib.Path) -> str:
    """vault 내 호스트 경로 → 컨테이너 마운트 경로."""
    rel = host_path.resolve().relative_to(VAULT.resolve())
    return f"/home/user/projects/2nd-brain-vault/{rel}"


def _refined(host_path: pathlib.Path) -> dict | None:
    """refine 단계(2nd-brain-parser post)가 만든 `<원본>_parse/refined.md` 가 있으면 그 본문을 반환.
    extract(parser-drain)+refine 파이프라인의 산출을 소비 — brainify 는 파싱·비교를 다시 하지 않는다."""
    refined = host_path.parent / (host_path.name + "_parse") / "refined.md"
    if not refined.exists():
        return None
    txt = refined.read_text(encoding="utf-8")
    base = "refined"
    body = txt
    if txt.startswith("---"):
        end = txt.find("\n---", 3)
        if end != -1:
            for line in txt[3:end].splitlines():
                if line.startswith("base_engine:"):
                    base = "refined:" + line.split(":", 1)[1].strip()
            body = txt[end + 4:].lstrip("\n")
    return {"via": base, "markdown": body}


def _parse(host_path: pathlib.Path) -> dict:
    """파일 1개 → {via, markdown}. refined.md(refine 산출) 우선, 없으면 2nd-brain-parser docling fallback."""
    pre = _refined(host_path)
    if pre is not None:
        return pre
    cmd = [
        "docker", "run", "--rm", "-u", f"{os.getuid()}:{os.getgid()}",
        "-v", f"{VAULT}:/home/user/projects/2nd-brain-vault",
        "-v", f"{MODELS_VOLUME}:/home/user/.cache/huggingface",
        "-e", "HF_HOME=/home/user/.cache/huggingface", "-e", "HOME=/home/user",
        PARSER_IMAGE, "2nd-brain-parser", "parse-docling", _container_path(host_path),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            return {"via": "error", "markdown": "", "error": (r.stderr or "")[-300:]}
        d = json.loads(r.stdout)
        return {"via": d.get("via", "docling"), "markdown": d.get("markdown", "")}
    except Exception as e:
        return {"via": "error", "markdown": "", "error": str(e)}


def _items() -> list[dict]:
    """00_inbox 의 처리 대상: 스레드 폴더(_thread.md 보유) + 낱개 파싱가능 파일."""
    out: list[dict] = []
    if not INBOX.exists():
        return out
    for p in sorted(INBOX.iterdir()):
        if p.name.startswith(".") or p.name.endswith("_parse"):
            continue
        if p.is_dir():
            if (p / "_thread.md").exists():
                fm = _front(p / "_thread.md")
                out.append({"item": p.name, "kind": "thread",
                            "identifier": fm.get("gmail_thread_id", "")})
        elif p.is_file() and p.suffix.lower() in PARSEABLE:
            out.append({"item": p.name, "kind": "file",
                        "identifier": "sha:" + _sha256(p)})
    return out


def cmd_scan(_args) -> int:
    items = _items()
    for it in items:
        hits = _grep_knowledge(it["identifier"]) if it["identifier"] else []
        it["already_brainified"] = bool(hits)
        it["existing_notes"] = hits
    print(json.dumps({"vault": str(VAULT), "count": len(items), "items": items},
                     ensure_ascii=False, indent=2))
    return 0


def cmd_inspect(args) -> int:
    item = INBOX / args.item
    if not item.exists():
        print(json.dumps({"error": f"없음: {item}"}, ensure_ascii=False)); return 1
    result: dict = {"item": args.item, "parts": []}
    if item.is_dir():  # 스레드 폴더
        result["kind"] = "thread"
        result["identifier"] = _front(item / "_thread.md").get("gmail_thread_id", "")
        body = (item / "_thread.md").read_text(encoding="utf-8") if (item / "_thread.md").exists() else ""
        result["parts"].append({"name": "_thread.md", "via": "(email body)", "markdown": body})
        for att in sorted(item.iterdir()):
            if att.is_file() and att.suffix.lower() in PARSEABLE:
                pr = _parse(att)
                result["parts"].append({"name": att.name, "via": pr["via"], "markdown": pr["markdown"]})
    else:  # 낱개 파일
        result["kind"] = "file"
        result["identifier"] = "sha:" + _sha256(item)
        pr = _parse(item)
        result["parts"].append({"name": item.name, "via": pr["via"], "markdown": pr["markdown"]})
    result["already_brainified"] = bool(_grep_knowledge(result["identifier"])) if result["identifier"] else False
    print(json.dumps(result, ensure_ascii=False))
    return 0


def _slug(s: str, n: int = 60) -> str:
    s = re.sub(r"\s+", "-", (s or "").strip())
    s = re.sub(r'[\\/:*?"<>|]', "", s).strip("-. ")
    return s[:n] or "untitled"


def cmd_commit(args) -> int:
    item = INBOX / args.item
    if not item.exists():
        print(json.dumps({"error": f"없음: {item}"}, ensure_ascii=False)); return 1
    para = args.para.strip("/")  # 예: 02_areas/재정
    name = _slug(args.name)
    dest_src = SOURCES / para / name
    dest_src.mkdir(parents=True, exist_ok=True)
    # 식별자 재도출
    if item.is_dir():
        identifier = _front(item / "_thread.md").get("gmail_thread_id", "")
        id_field = f"gmail_thread_id: {identifier}" if identifier else ""
        for c in item.iterdir():
            shutil.move(str(c), str(dest_src / c.name))
        item.rmdir()
    else:
        identifier = "sha:" + _sha256(item)
        id_field = f"source_sha256: {identifier.split(':',1)[1]}"
        shutil.move(str(item), str(dest_src / item.name))
    body = pathlib.Path(args.body_file).read_text(encoding="utf-8") if args.body_file else ""
    tags = "[" + ", ".join(t.strip() for t in (args.tags or "").split(",") if t.strip()) + "]"
    note = KNOWLEDGE / para / f"{name}.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    fm = [
        "---",
        f"title: {args.title or name}",
        f"date: {args.date or ''}",
        f"tags: {tags}",
        f"sources: sources/{para}/{name}/",
    ]
    if id_field:
        fm.append(id_field)
    if args.via:
        fm.append(f"parse_via: {args.via}")
    fm += [
        "para_review: pending",           # 정책: 낙관 배치 → 주간 감사
        f"parse_confidence: {args.confidence or 'ok'}",
        "---",
        "",
    ]
    note.write_text("\n".join(fm) + body + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "note": str(note), "sources": str(dest_src),
                      "identifier": identifier}, ensure_ascii=False))
    return 0


def cmd_audit(_args) -> int:
    """플래그된 노트 나열 (주간 감사 대상)."""
    flagged: list[dict] = []
    if KNOWLEDGE.exists():
        for md in KNOWLEDGE.rglob("*.md"):
            fm = _front(md)
            if fm.get("para_review") == "pending" or fm.get("parse_confidence") == "low":
                flagged.append({"note": str(md.relative_to(VAULT)),
                                "para_review": fm.get("para_review", ""),
                                "parse_confidence": fm.get("parse_confidence", ""),
                                "sources": fm.get("sources", "")})
    print(json.dumps({"count": len(flagged), "flagged": flagged}, ensure_ascii=False, indent=2))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="brainify", description="brainify 결정형 helper")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan")
    pi = sub.add_parser("inspect"); pi.add_argument("item")
    pc = sub.add_parser("commit")
    pc.add_argument("item")
    pc.add_argument("--para", required=True, help="PARA 좌표, 예: 02_areas/재정")
    pc.add_argument("--name", required=True, help="파일명(slug), 예: 2026-05-22_anthropic_영수증")
    pc.add_argument("--title", default="")
    pc.add_argument("--tags", default="")
    pc.add_argument("--date", default="")
    pc.add_argument("--via", default="")
    pc.add_argument("--confidence", default="ok", choices=["ok", "low"])
    pc.add_argument("--body-file", default="")
    sub.add_parser("audit")
    args = ap.parse_args(argv)
    return {"scan": cmd_scan, "inspect": cmd_inspect,
            "commit": cmd_commit, "audit": cmd_audit}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
