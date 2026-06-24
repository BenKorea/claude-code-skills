#!/usr/bin/env python3
"""contacts_sync — vault 인맥 노트 → Google Contact 결정형 동기 엔진.

인계장 2026-06-23_인맥-contacts-sync-프로토콜화-ai4lt.md 의 R1·R3·R4 코드화.
권위 = vault 노트(frontmatter + 본문 `## 교류 이력`). Google Contact 은 그 거울.

핵심 설계:
  * **vault → Contact 단방향 projection.** 매 실행이 vault 상태를 Contact 에 투영 → 멱등(고정점).
    biography(메모)·userDefined·names 모두 vault 에서 재구성하므로 재실행 안전(append 아님).
  * **full-state update** (R1): 현재 Contact JSON 을 받아 *관리 필드만* 덮어쓰고 통째 push
    → 우리가 안 만지는 필드(전화 등) 보존. displayName/displayNameLastFirst 는 제거해 재계산.
  * **gog `-n`(dry-run) 절대 미사용** — update --from-file 에서 실제 적용되는 버그(인계 R1·⚠).
    대신 자체 preview(쓰기 없음)가 기본, `--apply` 일 때만 push.
  * **--ignore-etag** 사용 (R1): gog get 의 etag 가 update 검증을 통과 못 하는 함정 →
    push 직전 fresh get 으로 무변경(동시 수정자 없음) 확인 후 --ignore-etag. solo-writer 라 안전.

모드:
  preview (기본)   계획(create|update|noop) + 만들 Person JSON + 빈 필수필드 보고. 쓰기 0.
  --apply          실제 동기. cid 있으면 R1(update), 없으면 R3(create→update) + vault writeback.

미구현(상위 LLM/후속):
  enrich (R5 학자 전공·부서 웹검색·동명이인 게이트) = brainify/skill 의 LLM 일 (이 엔진은 결정형만).
  photo  (R7 updateContactPhoto) = 별도 access-token mint 경로, 후속.
"""
from __future__ import annotations
import argparse
import copy
import json
import os
import pathlib
import re
import subprocess
import sys

VAULT = pathlib.Path(os.path.expanduser(os.environ.get("BRAINIFY_VAULT", "~/projects/2nd-brain-vault")))
INMAEK = VAULT / "knowledge" / "02_areas" / "인맥"
ACCOUNT = os.environ.get("GOG_ACCOUNT", "kimbi.kirams@gmail.com")   # gog 운영계정 (git userEmail 과 다름)
KEYRING_PW_FILE = pathlib.Path(os.path.expanduser("~/.config/gogcli/.keyring-password"))

# 복성(2자 성) — split_name 예외. 그 외는 성 1자 가정.
COMPOUND_SURNAMES = {"남궁", "황보", "제갈", "사공", "선우", "독고", "동방", "서문"}
# 관리 userDefined 키 (vault 가 권위; 그 외 기존 키는 보존)
UD_FIRST = "인맥등록일"
UD_LAST = "최근교류일"


# ── gog 호출 ──────────────────────────────────────────────────────────────
def _gog_env() -> dict:
    env = dict(os.environ)
    if not env.get("GOG_KEYRING_PASSWORD") and KEYRING_PW_FILE.exists():
        env["GOG_KEYRING_PASSWORD"] = KEYRING_PW_FILE.read_text(encoding="utf-8").strip()
    return env


def _gog(args: list[str], input_text: str | None = None, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(["gog", "-a", ACCOUNT, *args], input=input_text,
                          capture_output=True, text=True, timeout=timeout, env=_gog_env())


def gog_get(cid: str) -> dict | None:
    """현재 Contact JSON (primary result). 없으면 None."""
    r = _gog(["contacts", "get", cid, "-j", "--results-only"])
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except Exception:
        return None


# ── vault 노트 파싱 ────────────────────────────────────────────────────────
def find_note(arg: str) -> pathlib.Path | None:
    p = pathlib.Path(arg)
    if p.exists() and p.suffix == ".md":
        return p
    cand = INMAEK / (arg if arg.endswith(".md") else arg + ".md")
    return cand if cand.exists() else None


def parse_note(path: pathlib.Path) -> tuple[dict, dict]:
    """(frontmatter, body_sections). frontmatter 는 scalar + inline/block list 모두 처리.
    body_sections: {'교류 이력': [line, ...]} 등 `## 헤더` → 그 아래 라인 리스트."""
    txt = path.read_text(encoding="utf-8")
    fm: dict = {}
    body = txt
    if txt.startswith("---"):
        end = txt.find("\n---", 3)
        if end != -1:
            fm = _parse_fm(txt[3:end])
            body = txt[end + 4:]
    sections: dict[str, list[str]] = {}
    cur = None
    for line in body.splitlines():
        m = re.match(r"^#{2,3}\s+(.*)$", line)
        if m:
            cur = m.group(1).strip()
            sections[cur] = []
        elif cur is not None:
            sections[cur].append(line)
    return fm, sections


def _strip_comment(val: str) -> str:
    """YAML 인라인 주석 제거 — 공백 뒤 `#` 부터 끝까지. (값 내부 # 은 공백 선행 없으면 보존: URL fragment 등)"""
    return re.split(r"\s#", val, 1)[0].rstrip()


def _parse_fm(block: str) -> dict:
    out: dict = {}
    lines = block.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if ":" not in line or line.startswith(" "):
            i += 1
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = _strip_comment(val.strip())
        if val.startswith("[") and val.endswith("]"):           # inline list
            inner = val[1:-1].strip()
            out[key] = [x.strip().strip('"').strip("'") for x in inner.split(",") if x.strip()] if inner else []
        elif val == "":                                          # block list or empty
            items = []
            j = i + 1
            while j < len(lines) and lines[j].lstrip().startswith("- "):
                items.append(_strip_comment(lines[j].lstrip()[2:].strip()).strip('"').strip("'"))
                j += 1
            out[key] = items if items else ""
            i = j
            continue
        else:
            out[key] = val.strip('"').strip("'")
        i += 1
    return out


# ── 이름·표시명 ────────────────────────────────────────────────────────────
def split_name(title: str, family: str = "", given: str = "") -> tuple[str, str]:
    """한글 본명 → (family, given). 복성 처리. override 우선."""
    if family or given:
        return family, given
    t = (title or "").strip()
    if len(t) >= 2 and t[:2] in COMPOUND_SURNAMES:
        return t[:2], t[2:]
    if len(t) >= 2:
        return t[:1], t[1:]
    return t, ""


def display_parts(fm: dict) -> tuple[str, str, str]:
    """contacts_display_name(언더바형 `조직_성명_직책`) → (prefix, unstructured, suffix).
    표시명 없으면 (조직/부서, 본명, 직책) 폴백."""
    dn = (fm.get("contacts_display_name") or "").strip()
    if dn and "_" in dn:
        parts = [x for x in dn.split("_") if x]
        prefix = parts[0]
        suffix = parts[-1] if len(parts) >= 3 else ""
        return prefix, " ".join(parts), suffix
    # 폴백: scope 에 따라 prefix = 부서(internal) or 조직(external)
    scope = (fm.get("affiliation_scope") or "external").strip()
    org = (fm.get("organization") or "").split(" (")[0].strip()
    dept = (fm.get("department") or "").strip()
    prefix = dept if scope == "internal" and dept else org
    name = (fm.get("title") or "").strip()
    suffix = (fm.get("title_role") or "").strip()
    uns = " ".join(x for x in [prefix, name, suffix] if x)
    return prefix, uns, suffix


# ── biography(메모) 재구성 (R4) ────────────────────────────────────────────
_LOG_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")
_TASK = re.compile(r"\[task::[^\]]*\]")


def build_biography(fm: dict, sections: dict) -> str:
    """역할 헤더(secondary_roles) + 교류 로그(본문 `## 교류 이력`). 신원줄 금지(구조화 필드와 중복)."""
    header_parts = fm.get("secondary_roles") or []
    if isinstance(header_parts, str):
        header_parts = [header_parts] if header_parts else []
    header = "; ".join(p for p in header_parts if p)
    logs: list[str] = []
    for raw in sections.get("교류 이력", []):
        s = raw.strip()
        if not s.startswith("- "):
            continue
        s = s[2:].strip()
        s = _TASK.sub("", s)
        ev = _WIKILINK.search(s)
        ev_name = ev.group(1).split("|")[0] if ev else ""
        s = _WIKILINK.sub("", s).strip()
        dm = _LOG_DATE.search(s)
        date = dm.group(1) if dm else ""
        # vault 형식 `YYYY-MM-DD · 채널 · 요약` → 메모 `YYYY-MM-DD 이벤트 — 요약`
        rest = re.sub(r"^\d{4}-\d{2}-\d{2}\s*", "", s).strip(" ·-—")
        bits = [b.strip() for b in rest.split("·") if b.strip()]
        summary = bits[-1] if bits else rest
        line = date
        if ev_name:
            line += f" {ev_name}"
        if summary:
            line += f" — {summary}"
        if line.strip():
            logs.append(line.strip())
    out = []
    if header:
        out.append(header + ("." if not header.endswith(".") else ""))
    out += logs
    return "\n".join(out).strip()


# ── Person JSON 빌드 ───────────────────────────────────────────────────────
REQUIRED = ["contacts_display_name", "email", "organization", "title_role"]


def build_person(fm: dict, sections: dict, current: dict | None) -> dict:
    """현재 Contact(있으면)에 관리 필드를 overlay 한 desired Person. full-state(비관리 필드 보존)."""
    person = copy.deepcopy(current) if current else {}
    fam, giv = split_name(fm.get("title", ""), fm.get("family", ""), fm.get("given", ""))
    prefix, uns, suffix = display_parts(fm)
    name_obj = {"givenName": giv, "familyName": fam, "unstructuredName": uns}
    if prefix:
        name_obj["honorificPrefix"] = prefix
    if suffix:
        name_obj["honorificSuffix"] = suffix
    # displayName/displayNameLastFirst 는 넣지 않음 → People API 가 unstructuredName 으로 재계산
    person["names"] = [name_obj]

    org_name = (fm.get("organization") or "").strip()
    dept = (fm.get("department") or "").strip()
    role = (fm.get("title_role") or "").strip()
    if org_name or dept or role:
        org_obj = {}
        if org_name:
            org_obj["name"] = org_name
        if dept:
            org_obj["department"] = dept
        if role:
            org_obj["title"] = role
        person["organizations"] = [org_obj]

    email = (fm.get("email") or "").strip()
    if email:
        person["emailAddresses"] = [{"value": email}]

    # userDefined: 기존 보존 + 관리키 overlay
    ud = [u for u in (person.get("userDefined") or []) if u.get("key") not in (UD_FIRST, UD_LAST)]
    first = (fm.get("gcontacts_first_registered") or fm.get("first_encounter") or "").strip()
    last = (fm.get("last_interaction") or "").strip()
    if first:
        ud.append({"key": UD_FIRST, "value": first})
    if last:
        ud.append({"key": UD_LAST, "value": last})
    if ud:
        person["userDefined"] = ud

    bio = build_biography(fm, sections)
    if bio:
        person["biographies"] = [{"value": bio, "contentType": "TEXT_PLAIN"}]
    return person


def _comparable(person: dict) -> dict:
    """비교용 정규화 — etag·metadata·resourceName 등 서버 메타 제거."""
    p = copy.deepcopy(person)
    for k in ("etag", "metadata", "resourceName", "displayName", "displayNameLastFirst"):
        p.pop(k, None)
    for arr in ("names", "organizations", "emailAddresses", "userDefined", "biographies", "phoneNumbers"):
        for item in p.get(arr, []) or []:
            item.pop("metadata", None)
            for nk in ("displayName", "displayNameLastFirst"):
                item.pop(nk, None)
    return p


def missing_required(fm: dict) -> list[str]:
    return [k for k in REQUIRED if not (fm.get(k) or "").strip()]


# ── apply (R1 update / R3 create) ─────────────────────────────────────────
def do_update(cid: str, desired: dict) -> dict:
    """R1: fresh get(무변경 확인 불요 — solo-writer) → full-state from-file --ignore-etag."""
    payload = copy.deepcopy(desired)
    payload["resourceName"] = cid
    # displayName 류 제거(재계산) — names 내부는 build_person 에서 이미 안 넣음
    payload.pop("displayName", None)
    payload.pop("displayNameLastFirst", None)
    r = _gog(["contacts", "update", cid, "--from-file", "-", "--ignore-etag", "-j"],
             input_text=json.dumps(payload, ensure_ascii=False))
    ok = r.returncode == 0
    return {"ok": ok, "stdout": r.stdout[-500:], "stderr": r.stderr[-500:]}


def do_create(fm: dict) -> tuple[str | None, dict]:
    """R3 1단계: create(플래그만). resourceName 반환."""
    fam, giv = split_name(fm.get("title", ""), fm.get("family", ""), fm.get("given", ""))
    flags = ["contacts", "create", "--given", giv or (fm.get("title") or "person")]
    if fam:
        flags += ["--family", fam]
    if (fm.get("organization") or "").strip():
        flags += ["--org", fm["organization"].strip()]
    if (fm.get("title_role") or "").strip():
        flags += ["--title", fm["title_role"].strip()]
    flags += ["-j"]
    r = _gog(flags)
    if r.returncode != 0:
        return None, {"ok": False, "stderr": r.stderr[-500:]}
    try:
        cid = json.loads(r.stdout).get("resourceName")
    except Exception:
        cid = None
    return cid, {"ok": bool(cid), "stdout": r.stdout[-300:]}


# ── vault writeback ────────────────────────────────────────────────────────
def writeback(path: pathlib.Path, cid: str, first_registered: str):
    """create 후 google_contact_id·gcontacts_first_registered·gcontacts_sync: yes 갱신(멱등)."""
    txt = path.read_text(encoding="utf-8")
    lines = txt.splitlines()
    if not lines or lines[0] != "---":
        return
    end = next((i for i in range(1, len(lines)) if lines[i] == "---"), None)
    if end is None:
        return

    def set_field(key: str, value: str):
        for i in range(1, end):
            if lines[i].startswith(key + ":"):
                lines[i] = f"{key}: {value}"
                return
        lines.insert(end, f"{key}: {value}")

    set_field("google_contact_id", cid)
    if first_registered:
        set_field("gcontacts_first_registered", first_registered)
    set_field("gcontacts_sync", "yes")
    path.write_text("\n".join(lines) + ("\n" if not txt.endswith("\n") else ""), encoding="utf-8")


# ── main ───────────────────────────────────────────────────────────────────
def cmd_sync(args) -> int:
    note = find_note(args.note)
    if note is None:
        print(json.dumps({"ok": False, "error": f"인맥 노트 없음: {args.note}"}, ensure_ascii=False)); return 1
    fm, sections = parse_note(note)
    cid = (fm.get("google_contact_id") or "").strip()
    current = gog_get(cid) if cid else None
    desired = build_person(fm, sections, current)
    plan = "update" if cid else "create"
    if cid and current is not None and _comparable(desired) == _comparable(current):
        plan = "noop"
    missing = missing_required(fm)
    out = {
        "note": str(note.relative_to(VAULT)), "plan": plan,
        "google_contact_id": cid, "missing_required": missing,
        "desired": _comparable(desired),
    }
    if not args.apply:
        out["preview"] = True
        print(json.dumps(out, ensure_ascii=False, indent=2)); return 0

    # ── apply ──
    if plan == "noop":
        out["result"] = {"ok": True, "skipped": "무변경(멱등)"}
        print(json.dumps(out, ensure_ascii=False, indent=2)); return 0
    if plan == "create":
        new_cid, cres = do_create(fm)
        if not new_cid:
            out["result"] = {"ok": False, "stage": "create", **cres}
            print(json.dumps(out, ensure_ascii=False, indent=2)); return 1
        # 2단계: 구조화 이름·메모 등 full-state update
        current2 = gog_get(new_cid)
        desired2 = build_person(fm, sections, current2)
        ures = do_update(new_cid, desired2)
        first = (fm.get("gcontacts_first_registered") or fm.get("first_encounter") or "").strip()
        if ures["ok"]:
            writeback(note, new_cid, first)
        out["google_contact_id"] = new_cid
        out["result"] = {"create": cres, "update": ures, "writeback": ures["ok"]}
        print(json.dumps(out, ensure_ascii=False, indent=2)); return 0 if ures["ok"] else 1
    # update
    ures = do_update(cid, desired)
    if ures["ok"]:                                          # gcontacts_sync: yes (+빈 first_registered 채움) 멱등 writeback
        first = (fm.get("gcontacts_first_registered") or fm.get("first_encounter") or "").strip()
        writeback(note, cid, first if not (fm.get("gcontacts_first_registered") or "").strip() else "")
    out["result"] = {**ures, "writeback": ures["ok"]}
    print(json.dumps(out, ensure_ascii=False, indent=2)); return 0 if ures["ok"] else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="contacts_sync", description="vault 인맥 노트 → Google Contact 동기")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ps = sub.add_parser("sync", help="한 인물 노트 동기 (기본 preview, --apply 로 실제 push)")
    ps.add_argument("note", help="인맥 노트 경로 또는 stem")
    ps.add_argument("--apply", action="store_true", help="실제 동기 (없으면 preview·쓰기 0)")
    ps.add_argument("--account", default="", help="gog 계정 override")
    args = ap.parse_args(argv)
    if getattr(args, "account", ""):
        global ACCOUNT
        ACCOUNT = args.account
    return {"sync": cmd_sync}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
