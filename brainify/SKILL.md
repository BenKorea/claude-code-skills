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
   첨부의 **정제 markdown**, `identifier`, `via` 를 받는다.
   - (스레드면) **`brainify.py contacts "<item>"`** 도 호출 — `_thread.md` 의 `participants`(gmail-label-actions
     가 gog 로 해석한 이름·이메일·`contact_id`)를 인맥 노트와 매칭해 `matched`(노트 有)/`unmatched`(contact_id 有·노트 無)/`no_contact` 로 분류해 준다. 인맥 반영(§아래)의 입력.
   - **`_thread.md` 의 `mail_class` 확인** — 포워드 메일은 봉투 참여자가 실제 상대가 아닐 수 있다(§5 포워드 처리). `native`=봉투 그대로, `self-forward`=봉투 비고 본문에 진짜 상대, `other-forward`=봉투는 전달자(인맥)·인용 인물은 참조. 정책 [[project-gmail-forward-3class-policy]].
   - 파싱은 brainify 가 하지 않는다 — extract(parser-drain)+[[refine]] 가 만든 `<원본>_parse/refined.md`
     를 읽는다(`via: refined:<엔진>`). refined.md 가 없으면(파이프라인 미경유 단건) docling 1회 fallback
     (`via: docling`). 즉 **파싱이 끝난 다음부터가 brainify** — 두 파서 비교·보정은 refine 이 이미 끝냄.
   - `via: error` 또는 markdown 이 비정상적으로 짧으면 → commit 시 `--confidence low`.
   - refined.md 가 없고 PDF 가 듀얼 검증이 필요해 보이면 → 먼저 `/refine` 권유(또는 parser-drain 대기).
3. **판단 (LLM — 여기가 이 스킬의 핵심)**: inspect 결과를 읽고 결정한다.
   - **PARA 좌표**: `01_projects/<폴더>` · `02_areas/<영역>` · `03_resources/<주제>` ·
     `04_archive/...`. 기존 폴더 구조를 먼저 `ls`(또는 scan 의 힌트)로 확인해 재사용.
     폴더·파일명 규칙은 vault `CLAUDE.md` 권위 (이벤트=`YYYY-MM-DD_출처_내용`,
     논문=`저자_연도_주제`, 프로젝트 폴더=`시작년월_명`/`명_마감년월`).
   - **동반 노트 본문**: 표준 구조 — `[원본](sources/<para>/<name>/<파일>)` 첫 줄 →
     한 줄 요약 → 핵심 내용 → 내 생각 → `[[관련 노트]]` 링크. 관련 노트는
     `grep -ril <키워드> knowledge/` 로 찾아 wikilink.
   - **인맥 링크**: §2 `contacts` 의 `matched` 인물은 본문 `관련 노트`에 `[[<wikilink>]]` 로 건다.
   - 본문은 임시파일(예: `/tmp/brainify-body.md`)에 쓴다.
4. **commit** — `brainify.py commit "<item>" --para <좌표> --name <slug> --title "<라벨>"
   --tags "t1,t2" --date YYYY-MM-DD --via "<inspect via>" [--confidence low]
   --body-file /tmp/brainify-body.md`.
   helper 가 원본을 `sources/<para>/<name>/` 로 이동하고, `knowledge/<para>/<name>.md` 에
   frontmatter(+ `identifier`, `para_review: pending`, `parse_confidence`) + 본문을 쓴 뒤
   00_inbox 를 비운다.
5. **인맥 반영** (commit 후 — 노트 `<name>` 확정됐으므로): §2 `contacts` 의 4 버킷대로.
   - `matched`(인맥 노트 있음) → `brainify.py link-event "<name>" --contact-id "<contact_id>" --context "<한 줄>"`.
     그 사람 노트 `related_events:` 에 `[[<name>]]` 멱등 추가 → 관계 타임라인 누적.
   - `unmatched`(contact_id 있는데 인맥 노트 없음 — gmail-label-actions 가 auto-create 한 신규 Contact 포함) →
     `brainify.py new-person --name "<name>" --email "<email>" --contact-id "<cid>" --event "<name>" --context "<한 줄>"`
     로 **인맥 노트 신설**(템플릿 스텁 + first_encounter + related_events). 게이트는 **Dr. Ben 의 라벨링** — 라벨한 스레드의
     참여자라 신뢰. 풍부한 맥락(대화핵심·관심사)은 비워두고 주간 감사/수동 보강.
   - `held`(동명이인 보류 — 같은 이름 Contact 가 다른 이메일로 존재) → **생성하지 말고 보고**. 주간 감사가
     "기존 인물 새 이메일(병합)" vs "별개 신규" 판단.
   - `no_contact`(Contacts 미등록·동명이인도 아님) → 무시.

   **포워드 메일 처리 (`mail_class`) — 봉투 참여자만으론 부족** ([[project-gmail-forward-3class-policy]]):
   - `native` → 위 4 버킷 그대로 (봉투 = 실제 인맥).
   - `self-forward`(내 KIRAMS 포워드) → 봉투 참여자는 *나라서 비어 있음*. **본문 인용 헤더**(`----- Original Message -----From : 이름 <이메일>To :…Cc :…`)에서 **진짜 상대 추출** → 각 이메일을 `gog contacts search <email>` 로 contact_id 해석 → 위 버킷대로(직접 교신자라 unmatched 면 new-person OK).
   - `other-forward`(남이 포워드+코멘트) → **봉투 전달자 = 1순위 인맥**(위 버킷 그대로 link-event/new-person). 본문 인용 속 인물은 **"via 전달자" 참조만** — 인맥 노트 신설·autocontact ✗, 동반 노트 본문에 `참조: 홍길동 (via [[전달자]])` 로 적고 주간 감사가 승급 판단. 액션(할일/일정/회신)은 **전달자 코멘트(본문 상단)** 기준.
6. 처리 결과를 표로 보고: 항목 → PARA → 노트 → 인맥(matched 링크 N · 신규 노트 M · held 보류 K) → 플래그.

배치일 때: **첫 1~2건 처리 후 패턴(분류 기준·노트 톤)을 Dr. Ben 에게 한 번 확인**받고
나머지를 일괄 진행 (CLAUDE.md 배치 규칙).

### 헤드리스 (`--headless`, brain-drain 무인 호출)

`/brainify --headless "<item>"` 로 호출되면(host `brain-drain` 타이머가 `claude -p` 로 1건씩 발화)
**사용자가 없다 — 절대 묻지 말 것**. 위 "물어본다"·"한 번 확인" 분기를 모두 다음으로 대체:

- `already_brainified: true` → 묻지 말고 **skip**(로그만).
- PARA 좌표가 모호 → 묻지 말고 **가장 그럴듯한 좌표로 낙관 배치 + `--confidence` 와 무관하게
  commit**(helper 가 `para_review: pending` 부착). 교정은 주간 감사가.
- `via: error`/markdown 비정상·refined.md 부재로 듀얼검증 필요 → `--confidence low` 로 commit(유실 0).
- **인맥 반영도 그대로 수행** — `contacts` → `matched` 본문 `[[링크]]`+commit 후 `link-event`(멱등);
  `unmatched` → `new-person` 으로 인맥 노트 신설(라벨링이 게이트라 헤드리스도 생성); `held`(동명이인) → 생성 말고 로그/보고만(주간 감사).
- 배치 "패턴 확인" 스텝 생략 — 인자로 받은 그 1건만 처리하고 끝낸다(턴당 1항목).

근거: [자동 우선·주간 감사 정책](../../../../projects/2nd-brain-vault/knowledge/02_areas/brain-system/automation-review-policy.md)
— 건별 승인 폐기 = 낙관 배치 + 플래그 + 주간 감사. 헤드리스는 이 정책의 구현이다.

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
- 파싱은 **로컬 전용 2nd-brain-parser 컨테이너**(외부 API 0) — 재무·민감 자료 leak 방지.
- 원본은 불변: `sources/` 의 파일은 수정하지 않고 이동만. 생각·요약은 `knowledge/` 의 .md 에.
- Docker 가 없거나 `inspect` 가 `via: error` 면 그 항목은 본문 없이 첨부 보존만 하고
  `parse_confidence: low` 로 표시 후 감사로 넘긴다 (파이프라인을 막지 않는다).
