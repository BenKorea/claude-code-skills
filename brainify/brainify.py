#!/usr/bin/env python3
"""brainify — 결정형 helper (메커니즘만; PARA 분류·요약 등 판단은 SKILL.md 의 LLM 이 한다).

서브커맨드 (모두 stdout JSON, 단 --help 제외):
  scan                 00_inbox 의 처리 대상 나열 + 중복(dedup) 상태.
  inspect <item>       항목의 markdown 추출(스레드 본문 + 첨부 2nd-brain-parser 파싱) + 식별자.
  commit  <item> ...   원본을 sources/<para>/<name>/ 로 이동 + knowledge/<para>/<name>.md
                       동반 노트(frontmatter+본문) 작성 + 정책 플래그 + inbox 비움.
  audit                플래그된(para_review:pending / parse_confidence:low) 노트 나열.
  renote-scan          refined.md 가 뒤늦게 생긴 parse_confidence:low 노트 나열(재작성 후보).
  renote-read  <note>  재작성 재료: 기존 노트 + refined.md 전문 + _thread.md.
  renote-write <note>  본문 교체(--body-file, 생략 가능) + parse_confidence 갱신 + renoted 마커.

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
# HWP/HWPX 는 컨테이너 docling 경로가 실패(soffice 프로필 미초기화) → 호스트 hwp_refine.py 로 직접 refined.md 생산.
# parser-drain(extract)이 아직 안 돈 항목을 brainify 가 먼저 만나도 self-heal (레이스 제거). 2nd-brain repo(in-routine)에 존재.
HWP_REFINE = pathlib.Path(os.path.expanduser(os.environ.get(
    "BRAINIFY_HWP_REFINE", "~/projects/2nd-brain/docker/parser-drain/hwp_refine.py")))

# 2nd-brain-parser 가 파싱하는 확장자 (그 외는 첨부로만 보존, 본문 추출 안 함)
AUDIO = {".m4a", ".mp3", ".wav", ".ogg", ".opus", ".aac", ".amr"}   # 폰 음성녹음 등 — parser-drain 오디오 루프(faster-whisper)가 refined.md 생산
IMAGE = {".jpg", ".jpeg", ".png", ".webp", ".jfif", ".heic", ".bmp", ".tif", ".tiff", ".gif"}  # 폰 사진·스캔·명판 등 — parser-drain 이미지 루프(MinerU OCR)가 <원본>_parse/ocr.json 생산 (2026-07-20: 사진 무인 편입 활성)
PARSEABLE = {".pdf", ".docx", ".pptx", ".xlsx", ".hwp", ".hwpx", ".doc", ".ppt", ".xls",
             ".odt", ".odp", ".ods", ".rtf"} | AUDIO | IMAGE


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


def _msg_count(thread_md: pathlib.Path) -> int:
    """_thread.md frontmatter 의 message_count. 없으면 0."""
    if not thread_md.exists():
        return 0
    try:
        return int(_front(thread_md).get("message_count", "0") or 0)
    except (TypeError, ValueError):
        return 0


def _filed_count(note: pathlib.Path) -> int:
    """이 노트가 *실제로 반영한* 메시지 수.

    1순위 = 노트 frontmatter `thread_message_count` (commit 이 기록).
    2순위 = 노트가 가리키는 sources/ 의 `_thread.md` 의 message_count — **하위호환**:
    2026-07-14 이전 노트엔 1순위 필드가 없다. 그 노트들도 commit 때 _thread.md 를
    sources 로 옮겨놨으므로 그 스냅샷이 "무엇까지 반영했는가"의 증거가 된다.
    """
    fm = _front(note)
    try:
        n = int(fm.get("thread_message_count", "") or 0)
        if n:
            return n
    except (TypeError, ValueError):
        pass
    src = (fm.get("sources", "") or "").strip().strip("/")
    if not src:
        return 0
    return _msg_count(VAULT / src / "_thread.md")


def _dedup(identifier: str, inbox_count: int) -> dict:
    """중복/갱신 판정 — thread_id 단독이 아니라 **thread_id + message_count**.

    thread_id 만 보면 "이미 노트 있음 → skip" 이 되어, 스레드에 새 답장이 와도 재캡처만
    쌓이고 노트는 첫 스냅샷에 얼어붙는다(2026-07-14 규명: 7통 중 1통만 반영된 채 정체).
    중복 방지가 갱신 차단으로 작동한 것. 그래서 *메시지가 늘었으면 갱신 대상*으로 본다.
    """
    hits = _grep_knowledge(identifier) if identifier else []
    if not hits:
        return {"already_brainified": False, "existing_notes": [], "stale": False,
                "update_of": "", "filed_message_count": 0}
    filed = max((_filed_count(pathlib.Path(h)) for h in hits), default=0)
    stale = bool(inbox_count) and inbox_count > filed
    # 갱신 대상이면 *어느 노트를 고칠지* 를 함께 준다 (새 노트 생성 = 중복 → 금지)
    target = ""
    if stale:
        target = next((h for h in hits if _filed_count(pathlib.Path(h)) == filed), hits[0])
        try:
            target = str(pathlib.Path(target).relative_to(VAULT))
        except ValueError:
            pass
    return {"already_brainified": not stale, "existing_notes": hits, "stale": stale,
            "update_of": target, "filed_message_count": filed}


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


# ── 파싱 제외 정책 (backfill 과 동일 — 권위: backfill SKILL.md/backfill.py) ──
BULK_PAGES = 100             # 방대 reference PDF auto-parse 제외 임계(페이지)
BULK_MB = 20                 # 방대 제외 임계(MB)
BULK_NAME = re.compile(r"(?i)초록집|자료집|proceedings|abstract|논문집|카탈로그|catalog|book")


def _pdf_pages(p: pathlib.Path):
    try:
        r = subprocess.run(["pdfinfo", str(p)], capture_output=True, text=True, timeout=30)
        for line in r.stdout.splitlines():
            if line.startswith("Pages:"):
                return int(line.split()[1])
    except Exception:
        pass
    return None


def _is_bulk(f: pathlib.Path):
    """방대 reference 판정 → (bool, reason). 이름패턴(전 포맷) OR PDF(페이지≥100 또는 크기≥20MB)."""
    m = BULK_NAME.search(f.name)
    if m:
        return True, f"이름패턴({m.group()})"
    if f.suffix.lower() == ".pdf":
        pg = _pdf_pages(f)
        if pg is not None:                       # 페이지 primary(고해상 스캔 size 무관)
            if pg >= BULK_PAGES:
                return True, f"{pg}p≥{BULK_PAGES}p"
        elif f.stat().st_size / 1048576 >= BULK_MB:   # 페이지 미상 → size fallback
            return True, f"{f.stat().st_size/1048576:.0f}MB≥{BULK_MB}MB(페이지 미상)"
    return False, ""


def _parse(host_path: pathlib.Path) -> dict:
    """파일 1개 → {via, markdown}. refined.md(refine 산출) 우선, 없으면 docling fallback.
    제외(백필 정책): xlsx 데이터=경량 stdlib 추출(docling X), 방대 reference PDF=on-demand page-Read."""
    pre = _refined(host_path)
    if pre is not None:
        return pre
    if host_path.suffix.lower() in AUDIO:                             # 오디오 — docling N/A, 전사는 parser-drain(whisper)
        return {"via": "pending-transcription", "markdown": "",
                "reason": "오디오 전사 대기 — parser-drain 오디오 루프(whisper venv 머신)가 refined.md 생산"}
    if host_path.suffix.lower() in IMAGE:                             # 이미지 — refined.md 없이 parser-drain 이미지 루프의 ocr.json 소비 (2026-07-20)
        ocr = host_path.parent / (host_path.name + "_parse") / "ocr.json"
        if ocr.exists():
            try:
                d = json.loads(ocr.read_text(encoding="utf-8"))
                eng = str(d.get("engine", "ocr:pipeline"))
                return {"via": eng if eng.startswith("ocr") else "ocr:" + eng, "markdown": d.get("markdown", "") or ""}
            except Exception as e:
                return {"via": "error", "markdown": "", "error": f"ocr.json 파싱 실패: {str(e)[-200:]}"}
        return {"via": "pending-ocr", "markdown": "",
                "reason": "이미지 OCR 대기 — parser-drain 이미지 루프(MinerU)가 ocr.json 생산"}
    if host_path.suffix.lower() in (".xlsx", ".xls"):                 # 데이터 스프레드시트 — docling 불요
        return {"via": "skipped-xlsx", "markdown": "", "reason": "데이터 스프레드시트(zipfile→sharedStrings 경량 추출로 파악)"}
    bulk, reason = _is_bulk(host_path)                                # 방대 reference — auto-parse 제외
    if bulk:
        return {"via": "skipped-bulk", "markdown": "", "reason": reason}
    if host_path.suffix.lower() in (".hwp", ".hwpx"):                # HWP — 컨테이너 docling 실패 경로. 호스트 hwp_refine 로 refined.md 직접 생산(parser-drain 미선행 시 self-heal, 레이스 제거)
        if not HWP_REFINE.exists():
            return {"via": "error", "markdown": "", "error": f"hwp_refine.py 없음: {HWP_REFINE} (2nd-brain repo 미clone?)"}
        try:
            subprocess.run(["python3", str(HWP_REFINE), str(host_path)],
                           capture_output=True, text=True, timeout=300, check=True)
        except Exception as e:
            return {"via": "error", "markdown": "", "error": f"hwp_refine 실패: {str(e)[-200:]}"}
        pre = _refined(host_path)                                     # hwp_refine 이 만든 refined.md 재소비
        if pre is not None:
            return pre
        return {"via": "error", "markdown": "", "error": "hwp_refine 실행됐으나 refined.md 없음"}
    cmd = [
        "docker", "run", "--rm", "-u", f"{os.getuid()}:{os.getgid()}",
        "-v", f"{VAULT}:/home/user/projects/2nd-brain-vault",
        "-v", f"{MODELS_VOLUME}:/home/user/.cache/huggingface",
        "-e", "HF_HOME=/home/user/.cache/huggingface", "-e", "HOME=/home/user",
        # 2026-07-20 회귀수리: 컨테이너 바이너리명이 `2nd-brain-parser`(심볼릭, 재빌드마다 탈락) → `brain-pdf`(base, 안정).
        # 심볼릭 회귀로 docling fallback 이 항상 via:error → 무인 커밋 전부 parse_confidence:low 였음(handoff 2026-07-17).
        PARSER_IMAGE, "brain-pdf", "parse-docling", _container_path(host_path),
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
                            "identifier": fm.get("gmail_thread_id", ""),
                            "message_count": _msg_count(p / "_thread.md")})
        elif p.is_file() and p.suffix.lower() in PARSEABLE:
            out.append({"item": p.name, "kind": "file",
                        "identifier": "sha:" + _sha256(p),
                        "message_count": 0})
    return out


def cmd_scan(_args) -> int:
    items = _items()
    for it in items:
        it.update(_dedup(it["identifier"], it.get("message_count", 0)))
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
        result["message_count"] = _msg_count(item / "_thread.md")
        body = (item / "_thread.md").read_text(encoding="utf-8") if (item / "_thread.md").exists() else ""
        result["parts"].append({"name": "_thread.md", "via": "(email body)", "markdown": body})
        for att in sorted(item.iterdir()):
            if att.is_file() and att.suffix.lower() in PARSEABLE:
                pr = _parse(att)
                result["parts"].append({"name": att.name, "via": pr["via"], "markdown": pr["markdown"]})
    else:  # 낱개 파일
        result["kind"] = "file"
        result["identifier"] = "sha:" + _sha256(item)
        result["message_count"] = 0
        pr = _parse(item)
        result["parts"].append({"name": item.name, "via": pr["via"], "markdown": pr["markdown"]})
    result.update(_dedup(result["identifier"], result.get("message_count", 0)))
    # 갱신(stale)이면 기존 노트 본문을 함께 준다 — LLM 이 새 메시지를 반영하되
    # Dr. Ben 이 손으로 쓴 「내 생각」 등을 보존해 *병합*하도록. commit 은 이 노트를 제자리 갱신.
    if result.get("stale") and result.get("update_of"):
        prev = VAULT / result["update_of"]
        if prev.exists():
            result["existing_note_body"] = prev.read_text(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


def _slug(s: str, n: int = 60) -> str:
    s = re.sub(r"\s+", "-", (s or "").strip())
    s = re.sub(r'[\\/:*?"<>|]', "", s).strip("-. ")
    return s[:n] or "untitled"


def _move_into(src: pathlib.Path, dst: pathlib.Path) -> None:
    """src → dst 이동 (dst 가 이미 있으면 덮어씀).

    갱신(재캡처) 경로에서 필요: dst 가 *디렉토리*인데 그냥 shutil.move 하면 그 **안으로** 중첩된다
    (`_parse/_parse`). 파일이면 os.rename 이 덮어쓰지만 디렉토리는 아니므로 먼저 지운다.
    """
    if dst.exists():
        shutil.rmtree(dst) if dst.is_dir() else dst.unlink()
    shutil.move(str(src), str(dst))


def cmd_commit(args) -> int:
    item = INBOX / args.item
    if not item.exists():
        print(json.dumps({"error": f"없음: {item}"}, ensure_ascii=False)); return 1

    # ── 갱신 경로: 같은 thread_id 의 노트가 이미 있고 메시지가 늘었으면 *그 노트를 제자리 갱신*.
    # 새 노트/새 sources 폴더를 만들면 "한 사안 = 한 정본" 이 깨지고 중복이 쌓인다.
    # args.para/--name 은 이 경우 무시된다 — 기존 좌표가 권위.
    updating = ""
    if item.is_dir() and (item / "_thread.md").exists():
        d = _dedup(_front(item / "_thread.md").get("gmail_thread_id", ""), _msg_count(item / "_thread.md"))
        if d["stale"] and d["update_of"]:
            updating = d["update_of"]

    if updating:
        note = VAULT / updating
        para = str(note.parent.relative_to(KNOWLEDGE))
        name = note.stem
        src_rel = (_front(note).get("sources", "") or "").strip().strip("/")
        dest_src = (VAULT / src_rel) if src_rel else (SOURCES / para / name)
        sources_field = f"{src_rel}/" if src_rel else f"sources/{para}/{name}/"
    else:
        para = args.para.strip("/")  # 예: 02_areas/재정
        name = _slug(args.name)
        dest_src = SOURCES / para / name
        note = KNOWLEDGE / para / f"{name}.md"
        sources_field = f"sources/{para}/{name}/"

    dest_src.mkdir(parents=True, exist_ok=True)
    # 식별자 재도출
    if item.is_dir():
        identifier = _front(item / "_thread.md").get("gmail_thread_id", "")
        id_field = f"gmail_thread_id: {identifier}" if identifier else ""
        msg_count = _msg_count(item / "_thread.md")
        for c in item.iterdir():
            _move_into(c, dest_src / c.name)   # 재캡처본이 옛 스냅샷을 덮어씀 (raw 층 갱신)
        item.rmdir()
    else:
        identifier = "sha:" + _sha256(item)
        id_field = f"source_sha256: {identifier.split(':',1)[1]}"
        msg_count = 0
        _move_into(item, dest_src / item.name)
        # 파생 _parse(refined.md·json) 도 원본 옆으로 동반 이동 — 안 옮기면 inbox 에 고아로 남고
        # source 와 분리됨(CLAUDE.md: _parse 는 sources 경로+_parse 위치). 스레드 분기는 폴더 통째 이동이라 무관.
        parse_dir = item.parent / (item.name + "_parse")
        if parse_dir.exists():
            _move_into(parse_dir, dest_src / parse_dir.name)
    body = pathlib.Path(args.body_file).read_text(encoding="utf-8") if args.body_file else ""
    tags = "[" + ", ".join(t.strip() for t in (args.tags or "").split(",") if t.strip()) + "]"
    note.parent.mkdir(parents=True, exist_ok=True)
    fm = [
        "---",
        f"title: {args.title or name}",
        f"date: {args.date or ''}",
        f"tags: {tags}",
        f"sources: {sources_field}",
    ]
    if id_field:
        fm.append(id_field)
    if msg_count:
        # 이 노트가 *반영한* 메시지 수. 다음 재캡처가 이보다 많으면 갱신 대상(_dedup).
        fm.append(f"thread_message_count: {msg_count}")
    if args.via:
        fm.append(f"parse_via: {args.via}")
    if args.doc_status and args.doc_status != "final":
        # 초안·준비·중간본 = source-trail (정본 아님). 확정본만 무표식(=final). 회의록 시리즈 clutter 방지.
        fm.append(f"doc_status: {args.doc_status}")
    if args.superseded_by:
        fm.append(f"superseded_by: \"[[{args.superseded_by}]]\"")
    if getattr(args, "source_missing", False):
        # 파싱 실패가 아니라 **파싱할 원본이 없음**. 파서를 아무리 고쳐도 해결되지 않으므로
        # parse_confidence:low 와 같은 통에 넣지 않는다(드레인 보고에서도 따로 센다).
        fm.append("source_missing: true")
    fm += [
        "para_review: pending",           # 정책: 낙관 배치 → 주간 감사
        f"parse_confidence: {args.confidence or 'ok'}",
        "---",
        "",
    ]
    note.write_text("\n".join(fm) + body + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "note": str(note), "sources": str(dest_src),
                      "identifier": identifier, "message_count": msg_count,
                      "updated": bool(updating)}, ensure_ascii=False))
    return 0


def cmd_audit(args) -> int:
    """플래그된 노트 나열 (주간 감사 대상). para_review:pending / parse_confidence:low / gcontacts_review:flagged.
    --inmaek-only = 인맥 잠정(gcontacts_review) 만 (금요일 인맥 브리핑 입력)."""
    flagged: list[dict] = []
    review_only = getattr(args, "inmaek_only", False)
    roots = [INMAEK] if review_only else ([KNOWLEDGE] if KNOWLEDGE.exists() else [])
    for root in roots:
        for md in root.rglob("*.md"):
            fm = _front(md)
            gr = fm.get("gcontacts_review", "")
            is_review = gr.startswith("flagged")
            if review_only and not is_review:
                continue
            if (fm.get("para_review") == "pending" or fm.get("parse_confidence") == "low" or is_review):
                flagged.append({"note": str(md.relative_to(VAULT)),
                                "para_review": fm.get("para_review", ""),
                                "parse_confidence": fm.get("parse_confidence", ""),
                                # 원본 부재 — 파싱 실패와 구분해 세라는 신호(소비자: drain-report.py).
                                "source_missing": str(fm.get("source_missing", "")).lower() == "true",
                                "gcontacts_review": gr,
                                "title": fm.get("title", ""),
                                "sources": fm.get("sources", "")})
    print(json.dumps({"count": len(flagged), "flagged": flagged}, ensure_ascii=False, indent=2))
    return 0


# ── renote: 뒤늦게 도착한 풀텍스트로 stub 노트 재작성 ─────────────────────────
#
# parse_confidence:low 는 "노트를 쓸 때 refined.md 가 없었다"는 뜻이다(parse_via: pending-ocr 등).
# 그런데 extract·refine 이 나중에 성공해도 **노트는 저절로 고쳐지지 않는다** — brainify 의 scan 은
# 00_inbox 의 미처리 항목만 보고, 이미 filed 된 노트는 대상이 아니기 때문이다(2026-08-05 규명).
# 그래서 refined.md 가 생긴 low 노트를 다시 집어 LLM 이 대조·보강하고 플래그를 내리는 경로를 둔다.
#
# 판단은 LLM 몫이다. 실제 후보를 보면 편차가 크다 — 어떤 노트는 촬영본 source-trail 이라 본문이
# 이미 충분하고 플래그만 낡았고, 어떤 노트는 풀텍스트가 없어 요약이 얕다. 그래서 helper 는
# 재료(기존 본문 + refined.md)를 모아 주기만 하고, 다시 쓸지 플래그만 내릴지는 스킬이 정한다.
MAX_REFINED_CHARS = 40000       # renote-read 가 넘겨줄 refined.md 1개당 상한


def _split_front(md: pathlib.Path) -> tuple[list[str], str]:
    """(frontmatter 줄 목록, 본문). frontmatter 가 없으면 ([], 전체)."""
    txt = md.read_text(encoding="utf-8")
    if not txt.startswith("---"):
        return [], txt
    end = txt.find("\n---", 3)
    if end == -1:
        return [], txt
    return txt[3:end].strip("\n").splitlines(), txt[end + len("\n---"):].lstrip("\n")


def _refined_targets(fm: dict) -> list[dict]:
    """노트 frontmatter 의 `sources:` → refined.md 후보 목록.

    sources 가 파일이면 `<파일>_parse/refined.md` 하나, 폴더면 그 안의 모든 `*_parse/refined.md`.
    (폴더형 = 스레드 캡처 — 첨부가 여럿일 수 있어 refined 도 여럿이다.)
    """
    rel = (fm.get("sources") or "").strip().strip('"')
    if not rel:
        return []
    src = VAULT / rel.rstrip("/")
    pds: list[pathlib.Path] = []
    if src.is_dir():
        pds = sorted(p for p in src.glob("*_parse") if p.is_dir())
    elif src.is_file():
        pds = [src.parent / (src.name + "_parse")]
    return [{"parse_dir": str(pd.relative_to(VAULT)),
             "refined": str((pd / "refined.md").relative_to(VAULT)),
             "ready": (pd / "refined.md").is_file()} for pd in pds]


def cmd_renote_scan(_args) -> int:
    """refined.md 가 (뒤늦게) 생긴 parse_confidence:low 노트 나열."""
    items: list[dict] = []
    for md in (KNOWLEDGE.rglob("*.md") if KNOWLEDGE.exists() else []):
        fm = _front(md)
        if fm.get("parse_confidence") != "low":
            continue
        if str(fm.get("source_missing", "")).lower() == "true":
            continue                      # 원본 부재 — refined 가 생길 리 없다
        tg = _refined_targets(fm)
        items.append({
            "note": str(md.relative_to(VAULT)),
            "title": fm.get("title", ""),
            "sources": fm.get("sources", ""),
            "targets": tg,
            # 붙어 있는 _parse 가 하나라도 있고 그 전부가 refined 면 재작성 재료가 갖춰진 것.
            "ready": bool(tg) and all(t["ready"] for t in tg),
        })
    ready = [i for i in items if i["ready"]]
    print(json.dumps({"count": len(items), "pending": len(ready), "items": items},
                     ensure_ascii=False, indent=2))
    return 0


def cmd_renote_read(args) -> int:
    """재작성 재료: 기존 노트(frontmatter+본문) + refined.md 전문 + _thread.md."""
    note = (VAULT / args.note) if not os.path.isabs(args.note) else pathlib.Path(args.note)
    if not note.exists():
        print(json.dumps({"error": f"없음: {note}"}, ensure_ascii=False)); return 1
    fm_lines, body = _split_front(note)
    fm = _front(note)
    parts = []
    src = VAULT / (fm.get("sources") or "").strip().strip('"').rstrip("/")
    thread = src / "_thread.md"
    if thread.is_file():
        parts.append({"name": "_thread.md", "markdown": thread.read_text(encoding="utf-8")})
    for t in _refined_targets(fm):
        if not t["ready"]:
            continue
        text = (VAULT / t["refined"]).read_text(encoding="utf-8")
        truncated = len(text) > MAX_REFINED_CHARS
        parts.append({"name": t["refined"], "truncated": truncated,
                      "markdown": text[:MAX_REFINED_CHARS],
                      **({"omitted_chars": len(text) - MAX_REFINED_CHARS} if truncated else {})})
    print(json.dumps({"note": str(note.relative_to(VAULT)), "frontmatter": fm_lines,
                      "existing_body": body, "parts": parts}, ensure_ascii=False))
    return 0


def cmd_renote_write(args) -> int:
    """본문 교체 + parse_confidence 갱신 + renoted 마커. frontmatter 의 나머지는 보존."""
    note = (VAULT / args.note) if not os.path.isabs(args.note) else pathlib.Path(args.note)
    if not note.exists():
        print(json.dumps({"error": f"없음: {note}"}, ensure_ascii=False)); return 1
    fm_lines, body = _split_front(note)
    if args.body_file:
        new_body = pathlib.Path(args.body_file).read_text(encoding="utf-8")
        if not new_body.strip():
            print(json.dumps({"error": "본문(--body-file)이 비어 있음"}, ensure_ascii=False)); return 1
        body = new_body
    today = __import__("datetime").date.today().isoformat()
    out_fm, seen_conf, seen_renoted = [], False, False
    for l in fm_lines:
        if l.startswith("parse_confidence:"):
            out_fm.append(f"parse_confidence: {args.confidence}"); seen_conf = True
        elif l.startswith("renoted:"):
            out_fm.append(f"renoted: {today}"); seen_renoted = True
        else:
            out_fm.append(l)
    if not seen_conf:
        out_fm.append(f"parse_confidence: {args.confidence}")
    if not seen_renoted:
        # 언제 풀텍스트로 다시 맞춰봤는지 — 같은 노트를 매번 다시 태우지 않게 하는 흔적.
        out_fm.append(f"renoted: {today}")
    note.write_text("---\n" + "\n".join(out_fm) + "\n---\n" + body.rstrip("\n") + "\n",
                    encoding="utf-8")
    print(json.dumps({"ok": True, "note": str(note.relative_to(VAULT)),
                      "confidence": args.confidence, "body_replaced": bool(args.body_file),
                      "renoted": today}, ensure_ascii=False))
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


# ── 자동 트랙 생성 게이트 (2026-06-23 결정: 역할/도메인 신호 있으면 잠정 생성·금요일 프루닝) ──
# 참여자 이름에 박힌 직책/역할 (academic·org). honorific '님' 무시.
ROLE_RE = re.compile(r"교수|부교수|조교수|박사|위원장|부위원장|위원|이사장|이사|부회장|회장|총무|감사|"
                     r"실장|부장|본부장|처장|원장|국장|과장|팀장|전문위원|연구위원|연구원|센터장|소장|"
                     r"대표|차장|사무국장|의장|간사|교사")
GENERIC_DOMAINS = {"gmail.com", "naver.com", "hanmail.net", "daum.net", "kakao.com", "nate.com",
                   "outlook.com", "hotmail.com", "yahoo.com", "icloud.com", "me.com"}
EXCLUDE_LOCAL = re.compile(r"^(noreply|no-reply|donotreply|do-not-reply|mailer-daemon|postmaster|"
                           r"webmaster|admin|master|system|automail|auto|info|news|newsletter)$", re.I)


def _gate_signal(p: dict) -> dict:
    """자동 생성 게이트 신호 (결정형). qualifies=True 면 brainify 가 잠정 인맥 생성 대상으로 표시.
    실제 생성 판단·필드 추론은 SKILL.md(LLM)·new-person --review. 여기선 신호만 노출."""
    name = p.get("name", "") or ""
    email = (p.get("email", "") or "").lower().strip()
    local, _, domain = email.partition("@")
    role = ROLE_RE.search(name)
    institutional = bool(domain) and domain not in GENERIC_DOMAINS
    excluded = (not email) or bool(EXCLUDE_LOCAL.match(local))
    return {"role": role.group(0) if role else "", "domain": domain,
            "institutional": institutional, "excluded": excluded,
            "qualifies": (bool(role) or institutional) and not excluded}


def cmd_contacts(args) -> int:
    """_thread.md participants → 인맥 매칭. matched(노트 有: 링크·related_events)/unmatched(contact_id 有·노트 無:
    게이트 통과 시 잠정 생성)/held(동명이인 보류: 주간검토)/no_contact(Contacts 미등록·무관).
    unmatched·no_contact 에 `signal`(게이트) 부착 — SKILL.md 가 qualifies 인 것만 new-person --review."""
    item = INBOX / args.item
    matched, unmatched, held, no_contact = [], [], [], []
    for p in _participants(item):
        cid = p.get("contact_id")
        if cid:
            note = _person_by_contact(cid)
            if note:
                matched.append({**p, "note": str(note.relative_to(VAULT)), "wikilink": note.stem})
            else:
                unmatched.append({**p, "signal": _gate_signal(p)})
        elif str(p.get("autocontact", "")).startswith("hold"):
            held.append(p)
        else:
            no_contact.append({**p, "signal": _gate_signal(p)})
    print(json.dumps({"item": args.item, "matched": matched, "unmatched": unmatched,
                      "held": held, "no_contact": no_contact}, ensure_ascii=False, indent=2))
    return 0


def _person_by_email(email: str) -> pathlib.Path | None:
    """email 로 인맥 노트 찾기 — contact_id 없는 신규 인물의 멱등 키 (재실행 중복 생성 차단)."""
    email = (email or "").strip()
    if not email or not INMAEK.exists():
        return None
    try:
        r = subprocess.run(["grep", "-ril", f"email: {email}", str(INMAEK)],
                           capture_output=True, text=True, timeout=20)
        hits = [l for l in r.stdout.splitlines() if l.strip()]
        return pathlib.Path(hits[0]) if hits else None
    except Exception:
        return None


def cmd_new_person(args) -> int:
    """인맥 노트 신설 (auto-created/unmatched 용). 멱등 키 = google_contact_id ▸ email (없으면 slug)."""
    if args.contact_id:
        exist = _person_by_contact(args.contact_id)
        if exist:
            print(json.dumps({"ok": True, "skipped": "이미 있음(contact_id)", "note": str(exist.relative_to(VAULT))}, ensure_ascii=False)); return 0
    if args.email:                                           # contact_id 없는 신규 인물 멱등
        exist = _person_by_email(args.email)
        if exist:
            print(json.dumps({"ok": True, "skipped": "이미 있음(email)", "note": str(exist.relative_to(VAULT))}, ensure_ascii=False)); return 0
    name = (args.name or "").strip() or (args.email or "person").split("@")[0]
    slug = _slug(name)
    note = INMAEK / f"{slug}.md"
    if note.exists():                                    # 동명 파일 충돌 → 이메일 local 로 구분
        note = INMAEK / f"{slug}_{(args.email or '').split('@')[0]}.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    rel = [f'  - "[[{args.event}]] — {args.context}"'] if args.event else []
    review = (args.review or "").strip()                    # 비면 정식, 값 있으면 잠정(flagged)+사유
    intro = (f"(brainify 자동 등록 [잠정·금요일 검토 대상: {review}] — {args.event or '메일'} 에서 신원 포착. "
             f"실제 관계인지·필드는 검토 후 확정)") if review else \
            f"(brainify 자동 등록 — {args.event or '메일'} 에서 신원 포착. 맥락은 추후 보강)"
    fm = ["---", f"title: {name}", f'aliases: ["{name}"]',
          f"google_contact_id: {args.contact_id or ''}",
          "contacts_display_name:",                         # [7] 외부=조직_성명_보직 / 내부동료=부서_성명_보직
          f"email: {args.email or ''}", f"organization: {args.org or ''}",
          "affiliation_scope:",                             # internal(내 기관 동료) | external
          "department:",                                    # internal 일 때 표시명에 쓰는 부서 (예: 핵의학과)
          f"title_role: {args.title_role or ''}", "secondary_roles: []",
          f"first_encounter: {args.date or ''}",
          "first_encounter_basis:",                         # met|email|calendar|estimated
          "gcontacts_first_registered:",                    # Google Contacts custom Sys_First_Registered 미러
          "last_interaction:", "last_role_change:",
          "career_history_in_body: false",
          "gtask_parent_id:",                               # 이 인물 전용 부모 Task ID (계층 루트)
          "is_academic: false", "zotero:", "photo: none",
          "relationship_tags: []",
          "related_events:" if rel else "related_events: []", *rel,
          "tags: [인맥]", "gcontacts_sync: pending",
          f"gcontacts_review: flagged ({review})" if review else "gcontacts_review:",   # 자동 생성 잠정 마커 → 금요일 브리핑
          "---", "",
          "## 한 줄 소개", "", intro, "",
          "## 첫 만남 맥락", "", "-", "",
          "## 교류 이력", "", "-", "",
          "## 대화 핵심", "", "-", "",
          "## 상대 관심사 / 내가 알게 된 것", "", "-", "",
          "## Career Timeline", "",
          "- [career_history:: (period:: YYYY-MM~) | (org:: [[기관]]) | (role:: 직책)]", "",
          "## 관련 노트", "", "-", ""]
    note.write_text("\n".join(fm) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "note": str(note.relative_to(VAULT)), "created": True}, ensure_ascii=False))
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
    # n/a = 파싱할 원본이 애초에 없음(첨부 0 self-forward 등). low(=파싱 실패)와 구분한다 —
    # 섞으면 고칠 수 없는 건이 매일 '파싱오류'로 보고돼 숫자를 오염시킨다(2026-08-05).
    pc.add_argument("--confidence", default="ok", choices=["ok", "low", "n/a"])
    pc.add_argument("--source-missing", dest="source_missing", action="store_true",
                    help="원본 첨부가 0건(포워드에 본문·첨부 미포함) — parse 대상 자체가 없음")
    pc.add_argument("--doc-status", dest="doc_status", default="final", choices=["final", "interim"],
                    help="final=확정본(full 요약·정본) / interim=초안·준비·중간본(source-trail, 요약 생략)")
    pc.add_argument("--superseded-by", dest="superseded_by", default="",
                    help="이 중간본을 대체하는 정본 노트 stem (회의록 시리즈)")
    pc.add_argument("--body-file", default="")
    pau = sub.add_parser("audit")
    pau.add_argument("--inmaek-only", dest="inmaek_only", action="store_true",
                     help="인맥 잠정(gcontacts_review: flagged) 만 — 금요일 인맥 브리핑 입력")
    sub.add_parser("renote-scan")
    prr = sub.add_parser("renote-read"); prr.add_argument("note")
    prw = sub.add_parser("renote-write")
    prw.add_argument("note")
    prw.add_argument("--body-file", dest="body_file", default="",
                     help="새 본문(생략하면 본문 유지하고 플래그만 갱신)")
    prw.add_argument("--confidence", default="ok", choices=["ok", "low"])
    pcon = sub.add_parser("contacts"); pcon.add_argument("item")
    ple = sub.add_parser("link-event")
    ple.add_argument("event", help="이벤트 노트 stem (= 동반 노트 --name)")
    ple.add_argument("--person", default="", help="인맥 노트 stem (contact-id 없을 때)")
    ple.add_argument("--contact-id", dest="contact_id", default="", help="google_contact_id (매칭 권위 키, 우선)")
    ple.add_argument("--context", default="", help="한 줄 맥락")
    pnp = sub.add_parser("new-person")
    pnp.add_argument("--name", required=True)
    pnp.add_argument("--email", default="")
    pnp.add_argument("--contact-id", dest="contact_id", default="")
    pnp.add_argument("--org", default="")
    pnp.add_argument("--title-role", dest="title_role", default="", help="직책 (이름에서 추론한 역할 등)")
    pnp.add_argument("--date", default="")
    pnp.add_argument("--event", default="", help="첫 연결 이벤트 노트 stem")
    pnp.add_argument("--context", default="", help="related_events 한 줄 맥락")
    pnp.add_argument("--review", default="", help="잠정 마커 사유 (자동 트랙 생성 시) — 값 있으면 gcontacts_review: flagged + 금요일 검토")
    args = ap.parse_args(argv)
    return {"scan": cmd_scan, "inspect": cmd_inspect, "commit": cmd_commit, "audit": cmd_audit,
            "renote-scan": cmd_renote_scan, "renote-read": cmd_renote_read,
            "renote-write": cmd_renote_write,
            "contacts": cmd_contacts, "link-event": cmd_link_event, "new-person": cmd_new_person}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
