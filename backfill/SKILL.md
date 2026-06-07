---
name: backfill
description: >
  이미 PARA 에 filed 된 사안 폴더를 *현 표준으로 소급 보강* — ① 지메일 thread 에서 `_thread.md`
  재구성(참여자 contact_id 해석), ② 소스파일 ephemeral 파싱(`_parse`+`refined.md`), ③ 참여자
  인맥 멱등 연결(link-event/new-person). "옛 회의록 _thread 만들어줘", "이 사안 정식 파싱·인맥
  연결해줘", "지메일/Drive 마이그레이션" 류에. `/backfill <폴더>` = 1건, `/backfill audit` = 보강
  필요 폴더 스캔. 전 단계 멱등(skip-if-present) — 재실행·재마이그레이션 안전.
---

# backfill

이미 `02_areas|01_projects/.../<사안>/` 에 자리잡은 기록을 **현 표준 구조로 소급 보강**한다.
오늘(2026-06-07) KARP 의학위원회에서 손으로 검증한 절차를 굳힌 것.

helper: `python3 ~/.claude/skills/backfill/backfill.py <subcommand>` (JSON 출력). 판단(어느 thread·
diverge vision 보정·누구 링크)은 이 문서(에이전트), 결정형(gog fetch·docker parse·scan)은 helper.

## 경계 (기존 스킬과 안 겹침)

- [[brainify]] = 인박스 → PARA *신규 편입*(forward).
- [[refine]] = *이미 있는* `_parse` → `refined.md`.
- **backfill = 이미 filed 된 사안에 `_thread`·`_parse`·인맥을 *소급 생성·연결*.** 지메일/Drive 마이그레이션의 실행 엔진.

## 멱등성 (핵심)

전 단계가 **skip-if-present** — `_thread.md` 존재/`_parse` sentinel(pdf=diff.json·비pdf=docling.json)/`link-event` 의 `[[event]]` 중복검사. 같은 폴더를 다시 돌리거나, 마이그레이션이 같은 자료를 다시 만나도 **중복 0**. (contact_id·threadId·내용은 안정 키.)

## 모드 1 — 단건 (`/backfill <폴더>`)

대상 = 사안 소스 폴더(예: `sources/02_areas/대한방사선방어학회/의학위원회/2026-03-11_KARP_의학위원회_27대1차회의록`).

1. **scan** — `backfill.py scan "<폴더>"`. `_thread.md` 유무·`need_parse`·`xlsx_skipped` 확인.

2. **_thread.md 재구성** (없을 때): 
   - **threadId 판단**(에이전트): 그 사안의 *대표 thread* 를 정한다 — 보통 최종/회람 메일. 후보 threadId 는 사안의 동반/형제 노트 frontmatter `gmail_thread_id(s):` 에서 찾는다(`grep -h gmail_thread knowledge/.../<사안 관련 노트>`). 시리즈면 *회람·확정본* thread 1개(제2차 모델).
   - `backfill.py thread "<폴더>" --thread-id <tid>` → gog fetch + `build_thread_md` → `_thread.md`(참여자 contact_id 해석 포함). gog 는 `.keyring-password` 캐시로 비대화식.

3. **_parse 생성** — `backfill.py parse "<폴더>"` (기본 `--engine dual`: pdf=docling+mineru+diff, office=docling). 
   - **xlsx 등 데이터 스프레드시트는 자동 제외**(정책 — 노트가 구조화 데이터를 담음).
   - 결과의 `needs_vision_refine: true`(verdict=diverge PDF)인 파일은 **에이전트가 vision 보정**: `refine.py read <_parse>` 로 두 파서 markdown·충돌점 확인 → 원본 PDF 를 `Read`(멀티모달)로 검증 → `refine.py write <_parse> --base-engine <docling|mineru|vision> --correction "..." --body-file ...`. (match/single 은 helper 가 이미 자동 promote.)
   - 정본 노트 frontmatter 갱신: `parse_via: refined:<engine>`, `parse: sources/.../<주원본>_parse/`.
   - 대량(마이그레이션): mineru 가 느리면 `--engine docling`(단일) 로 — refine 가 single 자동 promote. 단 fidelity 는 dual↓.

4. **인맥 멱등 연결** — `_thread.md` 의 참여자를 인맥에 연결:
   - `python3 ~/.claude/skills/brainify/brainify.py contacts "<폴더 절대경로>"` → `matched/unmatched/held/no_contact` 버킷.
   - **링크 판단**(에이전트): 그 사안에 *실제로 관련된* 사람만. 회의면 위원·배석. **단순 CC·무관 수신자 제외 가능**(예 타 위원회 총무 — Dr. Ben 이 포함 원하면 추가). held(동명이인)는 보고만.
     - `matched` → `brainify.py link-event <정본stem> --contact-id <cid> --context "<한 줄>"` (멱등).
     - `unmatched`(contact_id 有·노트 無) → `brainify.py new-person --name --email --contact-id --org --event <정본stem> --context --date`.
     - `no_contact` 인데 *이미 인맥노트 있는* 사람(이메일 미해석) → `link-event ... --person <인맥노트stem>`.
   - 정본 노트 본문 「관련 노트」에 forward `[[인맥]]` 링크 + (있으면) 후속작업 "인맥 등록" 체크.

5. 결과 표 보고: 폴더 → _thread(✓/생성) · _parse(파일별 engine/verdict) · 인맥(link N·신설 M·held K·제외).

## 모드 2 — 감사 (`/backfill audit`)

`02_areas|01_projects` 의 사안 폴더들을 훑어 보강 필요분 스캔:
- `for d in sources/0[12]_*/**/*/; do backfill.py scan "$d"; done` 류로 `_thread.md` 없음·`need_parse` 있는 폴더 목록화 → Dr. Ben 과 우선순위 정해 모드1 적용.

## 제약

- **gog**: `GOG_KEYRING_PASSWORD`(`~/.config/gogcli/.keyring-password` 캐시) 필요 — helper 가 자동 로드. 계정 기본 `kimbi.kirams@gmail.com`.
- **파서**: docker `2nd-brain-parser` compose(`~/projects/2nd-brain/docker/2nd-brain-parser/`) — helper 가 warm up→teardown. 모델 볼륨 재사용(다운로드 0). ai4lt CPU 에서 docling·mineru 모두 작동 실증(2026-06-07).
- **원본 불변**: `sources/` 원본은 안 고침(파싱 산출 `_parse/` 만 추가). 노트는 `knowledge/`.
- **vault = SyncThing**(git 아님). 스킬·helper 변경만 git(claude-skills).
