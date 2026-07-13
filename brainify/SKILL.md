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
   - **★ 스레드 신선도 (2026-07-13)**: `_thread.md` 의 `gmail_thread_id`+`message_count` 를 gog 현재값과 대조 — 변동(캡처 후 후속, 특히 **내 발신 회신**) 시 재캡처/보강 후 진행. 캡처는 스냅샷이라 소비 시점이 최종 방어(gmail-label-actions sent-poll 은 00_inbox 존재분만 재캡처). gog 실패 시 non-fatal — 그대로 진행(헤드리스 동일).
   - 파싱은 brainify 가 하지 않는다 — extract(parser-drain)+[[refine]] 가 만든 `<원본>_parse/refined.md`
     를 읽는다(`via: refined:<엔진>`). refined.md 가 없으면(파이프라인 미경유 단건) docling 1회 fallback
     (`via: docling`). 즉 **파싱이 끝난 다음부터가 brainify** — 두 파서 비교·보정은 refine 이 이미 끝냄.
   - `via: error` 또는 markdown 이 비정상적으로 짧으면 → commit 시 `--confidence low`.
   - refined.md 가 없고 PDF 가 듀얼 검증이 필요해 보이면 → 먼저 `/refine` 권유(또는 parser-drain 대기).
   - **★ 오디오(m4a·mp3 등 — 폰 음성녹음, 2026-07-13)**: parser-drain 오디오 루프(faster-whisper 로컬 GPU)가
     `<원본>_parse/refined.md`(타임스탬프 전사)를 생산 — brainify 는 그걸 소비만 한다(`via: refined:faster-whisper-*`).
     refined 부재 시 `via: pending-transcription` → docling fallback 금지, parser-drain 대기(전사는 whisper venv 머신=kimbi 전용).
     **선별 게이트**: 폰 녹음은 전사까지 *자동*, PARA 편입은 *이 스킬 실행(=Dr. Ben 지시)* 시점 — 사적·무가치 녹음은 편입 대신 삭제 제안.
     노트 본문에는 전사 전문 덤프 금지(요약·핵심·행동 항목), 전문은 refined.md 가 raw 층으로 보존.
   - **★ xlsx 등 데이터 스프레드시트는 docling `_parse` 생략 (2026-06-07)**: 명단·시트류는 *구조화 데이터 자체가 값* — full-text 파싱 가치 낮음. `_parse` 미동반이 정상(없어도 `via: error` 아님).
     - **파악 경로 = 경량 stdlib 추출** (Read 도구는 xlsx 렌더 못 함 → "그냥 Read" 안 됨): `python3 -c "import zipfile,re; print(re.findall(r'<t[^>]*>([^<]*)</t>', zipfile.ZipFile('<xlsx>').read('xl/sharedStrings.xml').decode('utf-8','ignore')))"` 로 셀 텍스트 즉시 추출(deps·모델·docker 0). 정밀 셀 위치 필요 시만 `xl/worksheets/sheet*.xml` 조인. → 그 내용을 노트 본문 표로 정리. (inspect `via: skipped-xlsx`)
   - **★ 방대 reference PDF docling 제외 (backfill 동일, 페이지 우선 개정 2026-06-07)**: **페이지 ≥ 100(우선) OR 이름패턴**(`초록집·자료집·proceedings·abstract·논문집·카탈로그·book`) OR **(페이지 미상 시만) 크기 ≥ 20MB** → inspect 가 docling fallback 안 하고 `via: skipped-bulk (<reason>)` 반환(*저가치·timeout 회피*). → 노트는 **메타만**(행사·발표 N·본인 발표 위치), 정본 `parse: skipped-bulk`, PDF 보존, **필요 페이지만 on-demand `Read`**(멀티모달 `pages:"120-122"`). 정말 전체 필요 시 `/backfill ... --force-bulk` 또는 수동.
3. **판단 (LLM — 여기가 이 스킬의 핵심)**: inspect 결과를 읽고 결정한다. (`via: skipped-bulk|skipped-xlsx` 면 위 §2-★ 대로 메타/경량추출 처리.)
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
5. **인맥 반영** (commit 후 — 노트 `<name>` 확정됐으므로): §2 `contacts` 의 버킷대로. **이게 인맥 업데이트의 *자동 트리거*** (다른 하나 = Dr. Ben 수동 지정 → contacts_sync, 아래 §인맥 업데이트 2-트리거).
   > **2계층 모델 (2026-06-23 결정 · 2026-06-24 자동=교류갱신전용으로 재개정)**: *디렉토리*(이름·이메일·소속·전화)는 **Google Contacts**(수천 규모 OK·폰 동기),
   > *관계 지식 노트*(`02_areas/인맥/*.md`, 7섹션 CRM)는 **교류 있는 사람 + 내 회의체 구성원**(수백). **등록 기준(2026-06-24)**: ① **내가 속한 회의체(위원회·이사회) 구성원 = 전원 볼트+주소록 멱등 생성**(회람·일정·사전브리핑 필요로 교류로 간주, 직접 1:1 없어도). ② 그 밖 개별 인물 = 교류 있으면 볼트, 없으면 주소록만. "교류"=실제 접촉(만남·교신·회의·통화). **표시명 = `원직장_성명_최고직책`**(회의체 직책 아닌 원직장 최고보직; 회의체 직책은 `secondary_roles`).
   > ⚠️ **자동 트랙(메일 브레인화)은 신규 인맥을 생성하지 않는다** — 기존 인맥(`.md` 보유자)의 *교류갱신만*. 매칭 안 되는 신규 인물은 **보고만**(생성 ✗). 신규 인맥 생성은 **수동 트랙 전용**(§인맥 2-트리거 #2). 멱등 — 재실행해도 중복 갱신 없음.
   > (2026-06-23 의 "자동 생성 게이트 + 잠정 `gcontacts_review: flagged` + 금요일 프루닝" 은 **2026-06-24 취소** — 폭증 위험·복잡도 제거.)
   - **`matched`**(인맥 노트 있음): ① 본문 `관련 노트`에 `[[wikilink]]`. ② `brainify.py link-event "<name>" --contact-id "<contact_id>" --context "<한 줄>"` (related_events 멱등 누적).
     ③ **per-field 추론 갱신** — 메일에서 드러난 정보(직책 변경·새 이메일·소속 변경 등)를 노트 frontmatter/`## 교류 이력`과 *필드별로 비교*해 **차이가 있으면** 갱신.
        기계적 덮어쓰기 ✗ — **출처 신뢰도(provenance) 우선**: 기존 값이 Dr. Ben 수동 입력/고신뢰인데 새 정보가 약하면 *덮어쓰지 말고* `gcontacts_review: flagged (필드 충돌: …)` 로 플래그. 메모(교류이력)는 비교 대상 아님(append; `(날짜+이벤트)` 멱등).
     ④ 갱신했으면(그리고 노트에 `gcontacts_review` flag 가 *없으면*=확정 관계) `python3 ~/.claude/skills/brainify/contacts_sync.py sync "<인맥노트 stem>" --apply` 로 Google Contact 동기(멱등·무변경이면 no-op).
   - **`unmatched`**(contact_id 有·노트 無) / **`no_contact`**(contact_id 도 無=완전 신규) → **보고만, 생성 ✗.** 결과 보고에 "신규 인물(미생성): `<name>` `<email>` [contact_id]" 나열 → Dr. Ben 이 의미 있으면 **수동 트랙**(§인맥 2-트리거 #2)으로 직접 생성. 자동은 신규 인맥을 만들지 않는다(2026-06-24). `new-person` 자동 호출 ✗.
   - **`held`**(동명이인 보류) → **보고만**. 수동/감사가 "기존 인물 새 이메일(병합)" vs "별개 신규" 판단.

   **포워드 메일 처리 (`mail_class`) — 봉투 참여자만으론 부족** ([[project-gmail-forward-3class-policy]]):
   - `native` → 위 4 버킷 그대로 (봉투 = 실제 인맥).
   - `self-forward`(내 KIRAMS 포워드) → 봉투 참여자는 *나라서 비어 있음*. **본문 인용 헤더**(`----- Original Message -----From : 이름 <이메일>To :…Cc :…`)에서 **진짜 상대 추출** → 각 이메일을 `gog contacts search <email>` 로 contact_id 해석 → 위 버킷대로(matched=link-event+per-field 갱신, unmatched/no_contact=보고만).
   - `other-forward`(남이 포워드+코멘트) → **봉투 전달자 = 1순위 인맥**(위 버킷 그대로). 본문 인용 속 인물은 **"via 전달자" 참조만** — 동반 노트 본문에 `참조: 홍길동 (via [[전달자]])` 로 적고 보고만(수동 승격 대상). 액션(할일/일정/회신)은 **전달자 코멘트(본문 상단)** 기준.
6. 처리 결과를 표로 보고: 항목 → PARA → 노트 → 인맥(matched 갱신 N · 신규 인물 보고(미생성) M · held K) → 플래그.

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
- **인맥 반영 (자동 트랙·무인) — 교류갱신만, 신규 생성 ✗** — `matched` → 본문 `[[링크]]` + `link-event`(멱등) + per-field 추론 갱신
  (provenance 충돌 시 *묻지 말고* `gcontacts_review: flagged (필드 충돌:…)`) + 확정노트면 `contacts_sync --apply`.
  `unmatched`/`no_contact`/`held` → **로그(보고)만** — 자동은 신규 인맥을 만들지 않는다(2026-06-24, 생성은 수동 트랙 전용). `new-person` 자동 호출 ✗.
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
4. **인맥 — 신규 인물 보고 검토 + 필드충돌 해소** — 자동 트랙은 신규 노트를 만들지 않으므로(2026-06-24) 프루닝할 잠정 노트는 없다. 대신:
   - **신규 인물(미생성) 보고 목록** — 지난 주 자동 트랙이 "보고만" 한 unmatched/no_contact 를 Dr. Ben 과 본다 → *의미 있으면* **수동 트랙**(§인맥 2-트리거 #2)으로 생성(벨트+Contacts+멱등+맥락).
   - **필드 충돌 flag**(`flagged (필드 충돌:…)`, 기존 노트의 per-field 갱신에서 발생) → 어느 값이 옳은지 판단해 노트 갱신 + flag 제거 + 동기.
   - `held`(동명이인)는 병합/신규 판단.
5. 감사 요약 보고: 점검 N건 / 좌표 교정 M건 / 재파싱 K건 / 중간본 정리 J건 / 신규 하위폴더 생성 P건 / 인맥 확정 Q건·강등 R건 / 남은 플래그.

## 인맥 업데이트 — 2 트리거 (멱등) (2026-06-23 결정)

인맥(`02_areas/인맥/*.md` ↔ Google Contacts)은 **두 트리거**로만 갱신되며 **둘 다 멱등**(재실행 = 고정점, 중복 생성/갱신 없음):

1. **자동 트랙 — 메일 브레인화 중** (위 모드1 §5, 헤드리스 포함) — **기존 인맥 교류갱신 전용, 신규 생성 ✗**. *논블로킹*(절대 멈춰 묻지 않음): `matched` 면 `link-event`(멱등) + per-field 추론 갱신(provenance 우선, 수동값 안 덮음) + 확정노트만 `contacts_sync --apply`. 매칭 안 되는 신규 인물은 **보고만** — 주간 감사/금요일 목록에서 Dr. Ben 이 수동 승격 판단. 자동이 노트·Contact 를 신규 생성하지 않는다(2026-06-24 재개정).
2. **수동 트랙 — Dr. Ben 이 한 인물 지정** (인터랙티브). *블로킹 허용*: 자료가 모자라면 **Dr. Ben 에게 물어** 채운다.
   - 흐름: `python3 ~/.claude/skills/brainify/contacts_sync.py sync "<인맥노트 stem 또는 경로>"` (preview·쓰기 0) →
     출력의 `plan`(create|update|noop)·`desired`(만들 Person JSON)·`missing_required`(빈 필수필드) 확인 →
     `missing_required` 있으면 **그 필드를 Dr. Ben 에게 질문**해 노트 frontmatter 채움(권위=vault 노트) →
     다시 preview 로 확인 → 승인 후 `--apply` 로 Google Contact 동기(R1 update / R3 create→update 2단계 자동).
   - 권위 = **vault 노트**(frontmatter + `## 교류 이력`), Google Contact 은 거울. contacts_sync 는 vault→Contact 단방향 projection.
   - ⚠️ `--apply` 는 비가역·대외(Google Contacts 실제 수정). `gog -n`(dry-run) 은 update 에서 *실제 적용되는 버그*라 **절대 사용 금지** — preview 는 contacts_sync 자체 기능(쓰기 0)을 쓴다.
   - 미구현(후속): enrich(R5 학자 전공·부서 웹검색 — LLM 이 노트에 추론 기입 후 sync), photo(R7 updateContactPhoto).

> contacts_sync.py 의 동기 레시피·함정(etag·unstructuredName·create 2단계)의 자족 스펙 = `handoff/2026-06-23_인맥-contacts-sync-프로토콜화-ai4lt.md`.

## 제약

- **정본 vault 는 WSL2 ext4 `~/projects/2nd-brain-vault`** — git 아님(SyncThing 동기), commit 하지 않음.
- 파싱은 **로컬 전용 2nd-brain-parser 컨테이너**(외부 API 0) — 재무·민감 자료 leak 방지.
- 원본은 불변: `sources/` 의 파일은 수정하지 않고 이동만. 생각·요약은 `knowledge/` 의 .md 에.
- Docker 가 없거나 `inspect` 가 `via: error` 면 그 항목은 본문 없이 첨부 보존만 하고
  `parse_confidence: low` 로 표시 후 감사로 넘긴다 (파이프라인을 막지 않는다).
