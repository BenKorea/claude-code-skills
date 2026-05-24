---
name: brainify
description: >-
  2nd-brain 브레인화 — sources/00_inbox 의 유입물(스레드 캡처 폴더·낱개 파일 PDF/HWP/Office)을
  파싱→PARA 분류→동반 노트 작성까지 자동 편입한다. "인박스 브레인화해줘", "오늘 자료 흡수해줘",
  "이 PDF 정리해줘" 류 캡처 지시에. `/brainify` = 처리, `/brainify audit` = 주간 감사.
  자동 우선·주간 감사 정책(낙관 배치 + 플래그)을 따른다.
---

# brainify

00_inbox 의 유입물을 2nd-brain 에 편입(브레인화)한다. **결정형 메커니즘은
`brainify.py`(파싱·이동·dedup·노트 쓰기)에 위임**하고, 이 문서는 **판단(PARA 분류·요약·
내생각·링크)** 만 한다. 정책: [자동 우선·주간 감사](../../../../projects/2nd-brain-vault/knowledge/02_areas/brain-system/automation-review-policy.md)
— 건별 사람 승인 없이 낙관 배치하고 의심분에 플래그, 품질은 주 1회 감사.

helper 는 `python3 ~/.claude/skills/brainify/brainify.py <subcommand>` 로 호출하며
모든 출력은 JSON 이다.

## 모드 1 — 처리 (`/brainify`, 기본)

기본은 **건별 자동**. Dr. Ben 이 매 항목 승인하지 않는다 (정책). 단 `scan` 에서
`already_brainified: true` 거나 분류가 정말 모호하면 그 항목만 물어본다.

1. **scan** — `brainify.py scan`. 처리 대상(스레드 폴더·낱개 파일) + 각 항목의
   dedup 상태(`already_brainified`, `existing_notes`)를 받는다.
   - `already_brainified: true` → 기본 skip. 사용자에게 "이미 있음, 덮어쓸까요?" 만 확인.
2. **inspect** — 항목별 `brainify.py inspect "<item>"`. 스레드 본문(`_thread.md`)과
   첨부의 파싱 markdown(2brain-parser), `identifier`, `via` 를 받는다.
   - `via: error` 또는 markdown 이 비정상적으로 짧으면 → commit 시 `--confidence low`.
3. **판단 (LLM — 여기가 이 스킬의 핵심)**: inspect 결과를 읽고 결정한다.
   - **PARA 좌표**: `01_projects/<폴더>` · `02_areas/<영역>` · `03_resources/<주제>` ·
     `04_archive/...`. 기존 폴더 구조를 먼저 `ls`(또는 scan 의 힌트)로 확인해 재사용.
     폴더·파일명 규칙은 vault `CLAUDE.md` 권위 (이벤트=`YYYY-MM-DD_출처_내용`,
     논문=`저자_연도_주제`, 프로젝트 폴더=`시작년월_명`/`명_마감년월`).
   - **동반 노트 본문**: 표준 구조 — `[원본](sources/<para>/<name>/<파일>)` 첫 줄 →
     한 줄 요약 → 핵심 내용 → 내 생각 → `[[관련 노트]]` 링크. 관련 노트는
     `grep -ril <키워드> knowledge/` 로 찾아 wikilink.
   - 본문은 임시파일(예: `/tmp/brainify-body.md`)에 쓴다.
4. **commit** — `brainify.py commit "<item>" --para <좌표> --name <slug> --title "<라벨>"
   --tags "t1,t2" --date YYYY-MM-DD --via "<inspect via>" [--confidence low]
   --body-file /tmp/brainify-body.md`.
   helper 가 원본을 `sources/<para>/<name>/` 로 이동하고, `knowledge/<para>/<name>.md` 에
   frontmatter(+ `identifier`, `para_review: pending`, `parse_confidence`) + 본문을 쓴 뒤
   00_inbox 를 비운다.
5. 처리 결과를 표로 보고: 항목 → PARA 좌표 → 노트 경로 → 플래그.

배치일 때: **첫 1~2건 처리 후 패턴(분류 기준·노트 톤)을 Dr. Ben 에게 한 번 확인**받고
나머지를 일괄 진행 (CLAUDE.md 배치 규칙).

## 모드 2 — 주간 감사 (`/brainify audit`)

1. **audit** — `brainify.py audit`. `para_review: pending` · `parse_confidence: low`
   노트를 모은다.
2. 항목별 원본 ↔ 동반 노트를 비교해 PARA 좌표 적정성·파싱 품질을 점검.
   - 좌표 적정 → 노트에서 `para_review:` 줄 제거(또는 `done`).
   - 부적정 → 노트 + `sources/` 원본을 함께 이동하고 `sources:` 경로·플래그 갱신.
   - `parse_confidence: low` → 필요 시 대체 경로(예: GPU MinerU, 재변환)로 재파싱.
3. 감사 요약 보고: 점검 N건 / 좌표 교정 M건 / 재파싱 K건 / 남은 플래그.

## 제약

- **정본 vault 는 WSL2 ext4 `~/projects/2nd-brain-vault`** — git 아님(SyncThing 동기), commit 하지 않음.
- 파싱은 **로컬 전용 2brain-parser 컨테이너**(외부 API 0) — 재무·민감 자료 leak 방지.
- 원본은 불변: `sources/` 의 파일은 수정하지 않고 이동만. 생각·요약은 `knowledge/` 의 .md 에.
- Docker 가 없거나 `inspect` 가 `via: error` 면 그 항목은 본문 없이 첨부 보존만 하고
  `parse_confidence: low` 로 표시 후 감사로 넘긴다 (파이프라인을 막지 않는다).
