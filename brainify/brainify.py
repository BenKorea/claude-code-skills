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
INMAEK = KNOWLEDGE / "02_areas" / "인맥"   # 인맥(관계 맥락) 허브 노트 폴더
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
        # 파생 _parse(refined.md·json) 도 원본 옆으로 동반 이동 — 안 옮기면 inbox 에 고아로 남고
        # source 와 분리됨(CLAUDE.md: _parse 는 sources 경로+_parse 위치). 스레드 분기는 폴더 통째 이동이라 무관.
        parse_dir = item.parent / (item.name + "_parse")
        if parse_dir.exists():
            shutil.move(str(parse_dir), str(dest_src / parse_dir.name))
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


# ── 인맥 반영 (발신자 → 관계 맥락) ─────────────────────────────────────────
def _participants(item: pathlib.Path) -> list[dict]:
    """_thread.md frontmatter 의 participants 파싱 (gmail-label-actions 가 '  - {json}' per line 기록)."""
    tmd = item / "_thread.md"
    if not tmd.exists():
        return []
    out, in_block = [], False
    for line in tmd.read_text(encoding="utf-8").splitlines():
        if line.startswith("participants:"):
            in_block = True
            continue
        if in_block:
            s = line.strip()
            if s.startswith("- "):
                try:
                    out.append(json.loads(s[2:]))
                except Exception:
                    pass
            elif s and not line.startswith(" "):   # 다음 키 / --- → 블록 끝
                break
    return out


def _person_by_contact(contact_id: str) -> pathlib.Path | None:
    """google_contact_id 로 인맥 노트 찾기 (매칭 권위 키)."""
    if not contact_id or not INMAEK.exists():
        return None
    try:
        r = subprocess.run(["grep", "-rl", f"google_contact_id: {contact_id}", str(INMAEK)],
                           capture_output=True, text=True, timeout=20)
        hits = [l for l in r.stdout.splitlines() if l.strip()]
        return pathlib.Path(hits[0]) if hits else None
    except Exception:
        return None


def cmd_contacts(args) -> int:
    """_thread.md participants → 인맥 매칭 상태. matched(노트 有)/unmatched(contact_id 有·노트 無)/no_contact."""
    item = INBOX / args.item
    matched, unmatched, no_contact = [], [], []
    for p in _participants(item):
        cid = p.get("contact_id")
        if not cid:
            no_contact.append(p); continue
        note = _person_by_contact(cid)
        if note:
            matched.append({**p, "note": str(note.relative_to(VAULT)), "wikilink": note.stem})
        else:
            unmatched.append(p)
    print(json.dumps({"item": args.item, "matched": matched,
                      "unmatched": unmatched, "no_contact": no_contact}, ensure_ascii=False, indent=2))
    return 0


def cmd_link_event(args) -> int:
    """인맥 노트 related_events 에 이벤트 wikilink 멱등 추가 (--contact-id 우선, 없으면 --person stem)."""
    note = _person_by_contact(args.contact_id) if args.contact_id else None
    if note is None and args.person:
        cand = INMAEK / f"{args.person}.md"
        note = cand if cand.exists() else None
    if note is None or not note.exists():
        print(json.dumps({"ok": False, "error": f"인맥 노트 없음: {args.person or args.contact_id}"}, ensure_ascii=False)); return 1
    txt = note.read_text(encoding="utf-8")
    if f"[[{args.event}]]" in txt:                       # 멱등 — 이미 링크됨
        print(json.dumps({"ok": True, "skipped": "이미 있음", "note": str(note.relative_to(VAULT))}, ensure_ascii=False)); return 0
    lines = txt.splitlines()
    if not lines or lines[0] != "---":
        print(json.dumps({"ok": False, "error": "frontmatter 없음"}, ensure_ascii=False)); return 1
    fm_end = next((i for i in range(1, len(lines)) if lines[i] == "---"), None)
    if fm_end is None:
        print(json.dumps({"ok": False, "error": "frontmatter 미종료"}, ensure_ascii=False)); return 1
    entry = f'  - "[[{args.event}]] — {args.context}"' if args.context else f'  - "[[{args.event}]]"'
    re_idx = next((i for i in range(1, fm_end) if lines[i].startswith("related_events:")), None)
    if re_idx is not None:                               # 기존 리스트 끝에 삽입
        ins = re_idx + 1
        while ins < fm_end and lines[ins].lstrip().startswith("- "):
            ins += 1
        lines.insert(ins, entry)
    else:                                                # 필드 신설 (frontmatter 끝 직전)
        lines.insert(fm_end, "related_events:")
        lines.insert(fm_end + 1, entry)
    note.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "note": str(note.relative_to(VAULT)), "added": entry.strip()}, ensure_ascii=False))
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
    pcon = sub.add_parser("contacts"); pcon.add_argument("item")
    ple = sub.add_parser("link-event")
    ple.add_argument("event", help="이벤트 노트 stem (= 동반 노트 --name)")
    ple.add_argument("--person", default="", help="인맥 노트 stem (contact-id 없을 때)")
    ple.add_argument("--contact-id", dest="contact_id", default="", help="google_contact_id (매칭 권위 키, 우선)")
    ple.add_argument("--context", default="", help="한 줄 맥락")
    args = ap.parse_args(argv)
    return {"scan": cmd_scan, "inspect": cmd_inspect, "commit": cmd_commit, "audit": cmd_audit,
            "contacts": cmd_contacts, "link-event": cmd_link_event}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
