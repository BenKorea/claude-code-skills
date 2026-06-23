#!/usr/bin/env python3
"""인맥 노트 Phase 1 스키마 마이그레이션 (2026-06-23).

기존 02_areas/인맥/*.md 의 frontmatter 에 Phase 1 신설 필드를 **비파괴·멱등**으로 보강한다.
- 빠진 필드만 추가(기존 값·순서·본문 불변). 재실행 안전(이미 있으면 skip).
- affiliation_scope 는 organization 기반 best-effort 판정(KIRAMS 계열=internal / 비어있지 않으면 external).
  판정이 애매한 케이스(internal 후보·org 공백)는 리포트로 따로 출력 → Dr. Ben 이 검토 후 department·표시명 수동 보강.
- 본문 섹션(## 교류 이력 등)은 *건드리지 않는다* — 노트마다 구조가 달라 위험. 본문은 그 노트를 만질 때 점진 전환.

사용:
  python3 migrate_inmaek_phase1.py            # dry-run (변경 미리보기만)
  python3 migrate_inmaek_phase1.py --apply    # 실제 기록
"""
from __future__ import annotations
import argparse
import pathlib
import re
import sys

VAULT = pathlib.Path.home() / "projects" / "2nd-brain-vault"
INMAEK = VAULT / "knowledge" / "02_areas" / "인맥"

# 내 기관(한국원자력의학원/KIRAMS) 계열 — 매칭되면 affiliation_scope=internal 후보(동료).
# 주의: "방사선보건원"은 KHNP(한국수력원자력)에도 있어 오판 → 제외. "한국수력원자력"은 "원자력의학원"을 포함 안 해 안전.
KIRAMS_PATTERNS = ["한국원자력의학원", "원자력의학원", "KIRAMS", "kirams", "원자력병원"]

# Phase 1 신설/표준 필드: (key, 기본값). 값이 빈 placeholder 면 "" (key: 만 기록).
# affiliation_scope 는 아래에서 동적 결정하므로 여기서 제외.
PHASE1_FIELDS: list[tuple[str, str]] = [
    ("contacts_display_name", ""),
    ("department", ""),
    ("first_encounter_basis", ""),
    ("gcontacts_first_registered", ""),
    ("last_interaction", ""),
    ("last_role_change", ""),
    ("career_history_in_body", "false"),
    ("gtask_parent_id", ""),
    ("is_academic", "false"),
    ("zotero", ""),
    ("photo", "none"),
    ("gcontacts_sync", "pending"),
]

KEY_RE = re.compile(r"^([A-Za-z_][\w-]*):")


def split_frontmatter(text: str):
    """(fm_lines, body, ok). fm_lines = '---' 사이 내용 줄들(경계 제외). 없으면 ok=False."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return [], text, False
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return [], text, False
    return lines[1:end], lines[end + 1:], True


def present_keys(fm_lines: list[str]) -> set[str]:
    keys = set()
    for ln in fm_lines:
        m = KEY_RE.match(ln)
        if m:
            keys.add(m.group(1))
    return keys


def get_value(fm_lines: list[str], key: str) -> str:
    for ln in fm_lines:
        m = KEY_RE.match(ln)
        if m and m.group(1) == key:
            return ln[m.end():].strip()
    return ""


def decide_scope(org: str) -> str:
    if not org.strip():
        return ""  # org 공백 → 판정 보류(리포트)
    low = org.lower()
    for pat in KIRAMS_PATTERNS:
        if pat.lower() in low:
            return "internal"
    return "external"


def migrate_note(path: pathlib.Path):
    """반환: (changed_keys, scope_decision, note_status). 파일은 수정 안 함(호출자가 결정)."""
    text = path.read_text(encoding="utf-8")
    fm_lines, body, ok = split_frontmatter(text)
    if not ok:
        return None, None, "frontmatter 없음(skip)"
    have = present_keys(fm_lines)
    org = get_value(fm_lines, "organization")

    additions: list[str] = []
    # affiliation_scope 먼저 (동적)
    scope = decide_scope(org)
    if "affiliation_scope" not in have:
        additions.append(f"affiliation_scope: {scope}")
    # 나머지 Phase1 필드
    for key, default in PHASE1_FIELDS:
        if key not in have:
            additions.append(f"{key}: {default}" if default else f"{key}:")

    if not additions:
        return [], scope, "이미 최신(skip)"

    new_fm = fm_lines + additions
    new_text = "---\n" + "\n".join(new_fm) + "\n---\n" + "\n".join(body)
    if body and not text.endswith("\n"):
        pass
    # 본문 줄 보존: split 이 마지막 개행을 잃을 수 있어 원본 꼬리 개행 맞춤
    if not new_text.endswith("\n"):
        new_text += "\n"
    return (additions, scope, new_text)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="실제 기록(미지정=dry-run)")
    args = ap.parse_args()

    if not INMAEK.exists():
        print(f"✋ 인맥 폴더 없음: {INMAEK}")
        return 1

    notes = sorted(p for p in INMAEK.glob("*.md")
                   if not p.name.startswith("_") and p.name != "README.md")

    changed, skipped, errors = 0, 0, 0
    internal_candidates: list[str] = []   # department 보강 필요
    no_org: list[str] = []                # org 공백 → scope 미정

    print(f"{'=== APPLY ===' if args.apply else '=== DRY-RUN (미적용) ==='}  대상 {len(notes)}개\n")
    for p in notes:
        additions, scope, result = migrate_note(p)
        if additions is None:
            print(f"  ⚠ {p.name}: {result}")
            errors += 1
            continue
        if not additions:
            skipped += 1
            continue
        changed += 1
        scope_tag = scope or "∅(org공백)"
        print(f"  + {p.name}  [scope={scope_tag}]  필드 {len(additions)}개 추가")
        if scope == "internal":
            internal_candidates.append(f"{p.name} (org: {get_value(split_frontmatter(p.read_text(encoding='utf-8'))[0], 'organization')})")
        if scope == "":
            no_org.append(p.name)
        if args.apply:
            p.write_text(result, encoding="utf-8")

    print(f"\n--- 요약 ---  변경 {changed} · 이미최신 {skipped} · 오류 {errors}")
    if internal_candidates:
        print(f"\n⭐ 내부(동료) 판정 — department·표시명(부서_성명_보직) 수동 보강 필요 ({len(internal_candidates)}):")
        for c in internal_candidates:
            print(f"   - {c}")
    if no_org:
        print(f"\n❓ organization 공백 — affiliation_scope 미정(빈값) ({len(no_org)}): {', '.join(no_org)}")
    if not args.apply:
        print("\n→ 실제 적용: python3 migrate_inmaek_phase1.py --apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
