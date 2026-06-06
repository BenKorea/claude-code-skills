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
   - **★ 조직형 영역의 하위폴더 깊이 (조직/부서 — 2026-06-06)**: 영역이 *조직*(학회·기관·기업)이면
     `02_areas/<조직>/<하위단위>/` 까지 내려 배치. 하위단위 = 그 조직의 상설 하위그룹 — 위원회·상설 행사시리즈·주제
     (예 `의학위원회`·`이사회`·`2026_춘계학술대회`·`보험관련`·`경영공시`). **2단계 상한** — 더 깊게 중첩 금지.
     *기능 영역*(`finance`·`이력`·`인맥`·`brain-system`·`pc-hygiene`·`RPythonStudy`)은 제외 — 영역 레벨 그대로.
     - **우선순위**: ① `ls 02_areas/<조직>/` 로 기존 하위폴더 확인 → 주제에 명백히 맞는 *가장 깊은 기존* 폴더 재사용
       (예 의학위원회 메일 → 기존 `의학위원회/`). ② *(Phase 2 자리 — Google Drive 폴더 매니페스트 참조, 미구현)* ③ 없으면 LLM 추론.
     - **생성 권한 (cron 얇게 / audit 깊게)**: *기존* 폴더 재사용은 **모든 실행 허용**(헤드리스 포함, 위험 0).
       **새 하위폴더 생성은 대화형 실행(Dr. Ben 동석)에서만** — 무인·헤드리스(§아래 헤드리스)는 새 폴더 금지,
       **가장 가까운 기존 상위(조직 레벨)에 배치** + frontmatter `new_subfolder_suggested: <제안 경로>` + `para_review: pending` 플래그 → 주간 감사가 생성·이동.
     - **새 조직 폴더 위치**: 핵심 소속(직접 활동 학회·소속기관)은 `02_areas/<조직>/` 최상위, 주변·외부 기관은 `02_areas/조직/<조직>/`.
     - **신규 폴더 대장**: 새 하위폴더(또는 조직 폴더) 생성 시마다 `02_areas/brain-system/folder-creation-ledger.md` 에
       1줄(`YYYY-MM-DD · <생성 경로> · <근거 항목/스레드>`) append → 주간 감사가 이 대장으로 신규 폴더 적정성 검토.
   - **★ 부서 내부 구성 (한 사안 = 한 정본 + 한 소스폴더 — 2026-06-07)**: `<부서>` 로 라우팅한 *뒤*, 그 안을 이렇게 구성한다.
     캡처는 *스레드별* 폴더로 흩어져 오지만(회의 1건이 검토요청·회람·리마인드 등 여러 thread), PARA 에선 **사안(회의) 단위로 수렴**.
     - **표준 레이아웃**: `knowledge/02_areas/<조직>/<부서>/<사안식별자>.md`(정본, 부서 최상위 flat) ↔
       `sources/02_areas/<조직>/<부서>/<사안식별자>/`(그 사안의 **모든** 원본·첨부·`_parse`·`_thread.md` 수렴). 폴더명(sources) = 정본 노트(knowledge) basename — 짝 동일(§commit 의 `<name>`). **단발 파일도 폴더로**(낱개 파일 금지 — 정렬·일관성).
       - **★ 사안 명명 규약 (2026-06-07)**: `YYYY-MM-DD_<조직토큰>_<부서>_<사안>`. 구조 구분자 = **`_` 통일**(날짜·조직·부서·사안 경계), 사안 내부는 무구분(예 `27대2차회의록`). 사안 예: `27대N차회의록`·`27대명단`·`27대N차일정`(씨앗).
         **전역 자기서술 유지** — 조직·부서 토큰을 *반드시 포함*(폴더 경로와 중복돼도): wikilink basename 은 폴더 맥락 없이 전역 고유·인지돼야 함(링크·인박스가 부서 밖에서 참조). 이 중복은 *전역 주소성의 대가*.
         **금지(인지부하·정렬 오류원)**: 날짜년도 중복(`2026-…_2026-제2차` ✗), 구분자 혼용(`_`+`-` ✗), 한 부서 내 형식 불일치(회의 vs 회의록, 제N차 vs 27대N차 ✗) → **부서 내 한 형식**. (2026-06-07 KARP 의학위원회 3폴더 통일 실측.)
     - **이동 시 시리즈 머지**: brainify 가 시리즈 감지(아래 ★ §3) → **기존 `<부서>/<사안식별자>/` 있으면 새 폴더 금지, 그리로 원본 머지**
       + 정본 `## 준비 경위` 1줄 흡수. 없으면(단발·신규) `<사안식별자>/` 새로. → 한 회의에 폴더 1개(스레드마다 N개 ✗).
     - **부서 최상위 = 정본만**: 중간본(검토요청·회람·초안 v.x) 이메일 캡처의 *원본*은 사안 소스폴더에 머지, *노트*는 정본이 흡수한 뒤
       **thin source-trail + `doc_status: interim`** → 주간 감사가 `04_archive/` 로 이동(raw 본문은 sources `_thread.md` 가 보존). 부서/ 에 정본과 평평하게 안 남긴다.
     - **예외 — 시리즈 씨앗(정본 미도래 선행 이벤트)**: 차기 회의 *일정 확정*(Calendar 이벤트) 같은 **중간본 아닌 실 이벤트**인데 흡수할 정본이 아직 없으면 → 아카이브 X. 부서 최상위에 두되 **본문 첫 줄 "★ <차수> 일정 씨앗 — 정본 도래 시 「준비 경위」로 흡수 예정, 배치 확정(audit 대기 아님)" 배너** + `para_review` 제거. 정본이 오면 그때 머지·흡수. (배너가 "왜 평면 잔존하나"를 답해 재혼동 방지 — 2026-05-20 제3차 일정 실측.)
     - 근거: 라우팅(어느 부서)과 구성(부서 안 배치)은 별개 축 — 전자만 정의됐을 때 정본·중간본·loose 초안이 부서/ 에 뒤섞여 혼란(2026-06 실측). 이 원칙이 후자를 고정.
   - **동반 노트 본문**: 표준 구조 — `[원본](sources/<para>/<name>/<파일>)` 첫 줄 →
     한 줄 요약 → 핵심 내용 → 내 생각 → `[[관련 노트]]` 링크. 관련 노트는
     `grep -ril <키워드> knowledge/` 로 찾아 wikilink.
   - **인맥 링크**: §2 `contacts` 의 `matched` 인물은 본문 `관련 노트`에 `[[<wikilink>]]` 로 건다.
   - **★ 확정본 vs 중간본 (회의록·문서 시리즈)**: 회의록 등은 *초안→검토→확정* 으로 **여러 번 회람**된다(매번 다른
     thread 라 thread_id dedup 으로 안 걸러짐). **확정된 것만 knowledge 요약**, 초안·준비·자료 중간본은 *source-trail*
     로만 보존(요약 생략) — 안 그러면 knowledge 가 미확정본으로 오염된다(2026-05-26 KARP 제2차 실측 문제).
     1. **시리즈 감지**: `grep -ril "<회의·시리즈 키>" knowledge/` (예 "제2차 의학위원회") 로 기존 정본/형제 노트 탐색.
     2. **확정본 판정**(아래면 final): 회의 *후* 회람된 **최종 회의록**(제목 "회의록" + 확정/회람), 또는 "확정"·"최종" 명시.
        → 표준 full 노트(정본). 이전 중간본 정보는 본문 `## 준비 경위` 타임라인에 **1줄씩 흡수**(날짜·핵심·thread 링크).
        기존 중간본 노트가 있으면 `--superseded-by <이정본>` 로 그쪽을 정본 가리키게(또는 04_archive 이동은 주간 감사).
     3. **중간본 판정**(초안·검토요청·"회의자료"·v.x·역학추가본 등): **full 요약 만들지 말 것.** raw 는 `sources/` 보존
        (캡처는 유지) + 동반 노트는 **얇은 source-trail**(첫 줄 원본 링크 + "초안/준비본 — 정본 [[..]]" 1줄) + `--doc-status interim`.
        정본이 이미 있으면 그 정본 `## 준비 경위` 에 1줄 append(인맥 link-event 와 동일 패턴).
     4. **모호하면 보수적으로 *중간본***(`--doc-status interim`) + `para_review: pending` → 주간 감사가 정본 승급.
        (clutter 방지가 유실보다 우선 — raw 는 어차피 보존됨.)
   - 본문은 임시파일(예: `/tmp/brainify-body.md`)에 쓴다.
4. **commit** — `brainify.py commit "<item>" --para <좌표> --name <slug> --title "<라벨>"
   --tags "t1,t2" --date YYYY-MM-DD --via "<inspect via>" [--confidence low]
   [--doc-status interim] [--superseded-by <정본 stem>] --body-file /tmp/brainify-body.md`.
   helper 가 원본을 `sources/<para>/<name>/` 로 이동하고, `knowledge/<para>/<name>.md` 에
   frontmatter(+ `identifier`, `para_review: pending`, `parse_confidence`, [중간본이면 `doc_status: interim`]) + 본문을 쓴 뒤
   00_inbox 를 비운다. (`--doc-status final` 기본 = 정본·full 요약, 무표식.)
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
- **회의록·문서 시리즈(확정 vs 중간본, §3-★)**: 확정 여부가 헤드리스로 불확실하면 **보수적으로 `--doc-status interim`**
  (source-trail, 요약 생략) + `para_review: pending` → 주간 감사가 정본 승급. 무인이 초안을 정본으로 적재해 knowledge
  오염시키는 것 방지(clutter < 유실, raw 는 보존됨). 명백한 확정본(회의 후 "회의록" 회람·"확정")만 final 요약.
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
   - **`doc_status: interim`**(회의록·문서 중간본, §3-★) → 확정본이 나왔으면: 정본 노트가 그 시리즈를 흡수했는지 확인,
     중간본은 `04_archive/` 이동 또는 정본 `## 준비 경위` 1줄로 강등(source-trail). 잘못 interim 된 *실제 확정본*이면
     full 요약으로 승급(doc_status 제거). 정본 미도래면 그대로 유지.
   - **`new_subfolder_suggested: <경로>`**(무인 실행이 조직/부서 하위폴더 생성을 보류한 것, §1-★) → 대화형 감사에서
     **실제로 그 하위폴더를 생성**하고 노트 + `sources/` 원본을 그리로 이동, `sources:` 경로·`[원본](...)` 링크 repoint,
     플래그 2개(`new_subfolder_suggested`·`para_review`) 제거. 생성 시 신규 폴더 대장(§1-★)에 1줄 기록.
     제안 경로가 부적절하면 적정 경로로 교정 후 이동.
3. **신규 폴더 대장 검토** — `02_areas/brain-system/folder-creation-ledger.md` 의 *지난 7일 신규 항목*을 Dr. Ben 과 함께 점검:
   오생성·중복(유사명 기존 폴더와 갈림)·잘못된 조직 위치(최상위 vs `조직/`)를 교정. 검토 끝난 줄은 `✓` 표시.
4. 감사 요약 보고: 점검 N건 / 좌표 교정 M건 / 재파싱 K건 / 중간본 정리 J건 / 신규 하위폴더 생성 P건 / 남은 플래그.

## 제약

- **정본 vault 는 WSL2 ext4 `~/projects/2nd-brain-vault`** — git 아님(SyncThing 동기), commit 하지 않음.
- 파싱은 **로컬 전용 2nd-brain-parser 컨테이너**(외부 API 0) — 재무·민감 자료 leak 방지.
- 원본은 불변: `sources/` 의 파일은 수정하지 않고 이동만. 생각·요약은 `knowledge/` 의 .md 에.
- Docker 가 없거나 `inspect` 가 `via: error` 면 그 항목은 본문 없이 첨부 보존만 하고
  `parse_confidence: low` 로 표시 후 감사로 넘긴다 (파이프라인을 막지 않는다).
