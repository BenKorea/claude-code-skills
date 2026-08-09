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
   dedup 상태(`already_brainified`, `stale`, `update_of`, `message_count` / `filed_message_count`)를 받는다.
   - `already_brainified: true` → 기본 skip. 사용자에게 "이미 있음, 덮어쓸까요?" 만 확인.
   - **★ `stale: true` → skip 하지 말고 *갱신*한다 (2026-07-14 신설).** 같은 `thread_id` 의 노트가
     이미 있지만 **재캡처본에 메시지가 늘었다**(`message_count` > `filed_message_count`)는 뜻이다.
     `update_of` 가 **고칠 노트**를 준다 — **새 노트를 만들지 말 것**(중복 = "한 사안 = 한 정본" 위반).
     > 왜: dedup 이 `thread_id` 단독이던 시절, 스레드에 답장이 오면 재캡처만 쌓이고 노트는 첫 스냅샷에
     > **얼어붙었다**(실측: 7통 중 1통만 반영된 채 인박스에 영구 적체). *중복 방지가 갱신 차단으로 작동*.
     > 에러가 안 나서 모든 진단이 green 인 채 조용히 낡는 게 이 결함의 성질이다.
2. **inspect** — 항목별 `brainify.py inspect "<item>"`. 스레드 본문(`_thread.md`)과
   첨부의 **정제 markdown**, `identifier`, `via` 를 받는다.
   - **`stale` 이면 `existing_note_body`(기존 노트 전문)도 함께 온다.** 새 메시지를 반영하되
     **Dr. Ben 이 손으로 쓴 「내 생각」·수동 링크는 보존해 *병합***한다 (통째 재작성 ✗ — 사람 편집 소실).
     `commit` 은 `update_of` 노트를 **제자리 갱신**하고 `--para`·`--name` 은 무시한다(기존 좌표가 권위).
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
   - **★ xlsx 는 파싱한다 (2026-08-07 개정 — 구 "생략" 정책 폐기)**: 2026-06-07 엔 "명단·시트류는 구조화 데이터 자체가 값이라 full-text 파싱 가치 낮음" 으로 `_parse` 생략을 정했으나, **실측이 반대였다** — vault xlsx 52개 중 50개가 이미 파싱돼 `refined.md` 가 있었고 **노트 51개가 그 풀텍스트를 근거로 쓰였다**. 게다가 `_parse()` 는 `_refined()` 를 먼저 보므로 refined.md 가 있으면 `skipped-xlsx` 분기에 **도달조차 하지 않아**, 정책이 사실상 죽어 있었다. 비용도 근거가 못 된다(xlsx docling 은 수 초 — 방대 PDF 의 30분과 다르다).
     - 따라서 **parser-drain 이 xlsx 를 정상 파싱**하고 brainify 는 그 `refined.md` 를 쓴다.
     - **docling 폴백 = `xlsx_refine.py`** (2nd-brain repo, stdlib only): docling 이 멀쩡한 엑셀을 못 읽는 경우가 실재한다(실측 2건 — `ZeroDivisionError`, `ConversionError`; 둘 다 zip·시트·sharedStrings 정상). 파서 한계이지 파일 결함이 아니므로 `.parse-error` 로 방치하지 않고 stdlib 추출로 `refined.md` 를 만든다(`base_engine: xlsx-stdlib`).
     - `refined.md` 가 아직 없을 때만 `via: skipped-xlsx` 가 나온다 — 이제 그건 *정책*이 아니라 **아직 파싱 전**이라는 뜻이다. 급하면 경량 추출(`zipfile` → `sharedStrings.xml`)로 즉시 파악한다(Read 도구는 xlsx 렌더 못 함).
   - **★ .xls(구형 엑셀)도 파싱한다 (2026-08-07 신설)**: `.xls` 는 **컨테이너를 안 탄다** — docling 이 입력으로 안 받고, 호스트 soffice 는 **libreoffice-calc 미설치**로 `no export filter`, 컨테이너엔 soffice 자체가 없다. apt 설치는 kimbi 만 되고 ai4lt·컨테이너는 조용히 실패하는 비대칭이라, parser-drain 이 hwp 와 같은 **호스트-측 stdlib 경로**(`xls_refine.py` — CFB+BIFF 직독)로 `refined.md` 를 직접 만든다(`base_engine: xls-stdlib`).
     - **확장자가 .xls 라고 다 엑셀이 아니다.** 관공서 웹시스템은 HTML `<table>` 을 그대로 .xls 로 내려준다(실측: 양천구 재산세). 매직바이트로 갈라 HTML 이면 `<table>` 직독(`xls-html-stdlib`). soffice 의 `source file could not be loaded` 는 이 부류에서 **필터 부재가 아니라 진짜로 엑셀이 아니라서** 나온다 — 두 에러 메시지를 구별할 것.
     - frontmatter `refine_confidence: low` + `warning: SST 문자열 N/M 만 복원` 이 보이면 **셀이 조용히 비어 있을 수 있다**(BIFF 의 CONTINUE 경계 처리 한계). 그 노트는 원본 대조 후 쓴다.
   - **★ 방대 reference PDF docling 제외 (backfill 동일, 페이지 우선 2026-06-07 · 이름패턴 하한 2026-08-07)**: **페이지 ≥ 100(우선)** OR **(페이지 미상 시만) 크기 ≥ 20MB** OR **이름패턴**(`초록집·자료집·proceedings·abstract·논문집·카탈로그·book`)**이면서 규모 하한(40p / 8MB)을 넘길 때** → inspect 가 docling fallback 안 하고 `via: skipped-bulk (<reason>)` 반환(*저가치·timeout 회피*). → 노트는 **메타만**(행사·발표 N·본인 발표 위치), 정본 `parse: skipped-bulk`, PDF 보존, **필요 페이지만 on-demand `Read`**(멀티모달 `pages:"120-122"`). 정말 전체 필요 시 `/backfill ... --force-bulk` 또는 수동.
     - **이름패턴은 단독으로 발동하지 않는다 (2026-08-07 개정).** 초판은 파일명만 맞으면 크기·페이지와 무관하게 제외했는데, `AOFNMB Series of Books 관련 Korea chapter 저자 추천.pdf` — **94KB·5페이지** 문서가 "Books" 하나로 걸렸다. 게이트의 취지는 1,400페이지짜리를 GPU 에서 빼는 것이지 제목에 book 이 든 짧은 문서를 버리는 게 아니다. **이름은 힌트, 방대함의 근거는 규모** — 이름패턴은 문턱을 낮춰줄 뿐(경계선 구간)이고 하한을 못 넘으면 발동하지 않는다. `parser-drain` 의 `is_bulk()` 와 **같은 기준이어야 한다**(두 단계가 다른 잣대를 쓰면 그게 버그).
     - ⚠️ **PDF 멱등 검사는 `diff.json` 기준**이다. `docling.json`·`refined.md` 만 손으로 만들어 두면 멱등이 안 걸려 다음 드레인에서 bulk 마커가 **재생성**된다 — 수동 파싱으로 오탐을 우회하려면 게이트 자체를 고쳐야 한다.
   - **★ 첨부 dedup 은 이름이 아니라 내용(sha256) 으로 (2026-08-09 신설)**: **같은 이름·다른 내용의 첨부가 실재한다.** 실측 — KAERI 자문 스레드의 `전문가 인적사항_김병일.hwp` 가 **빈 양식 14KB / 작성 완료본 72KB** 두 개였고, 이사회 203스레드에서도 회의록·회의자료의 **버전 차이 9건**(예: 워크숍 회의록 76KB↔151KB, 3차 회의자료 111KB↔159KB)이 같은 이름으로 왔다.
     - `if 대상경로.exists(): skip` 은 **두 번째를 소리 없이 버린다** — 실패가 안 나고 파일이 "원래 없던 것"이 된다. 반드시 `sha256` 이 같을 때만 skip 하고, 이름이 겹치면 `_1`·`_r1` 접미로 **둘 다 보존**한다.
     - `gmail-label-actions`(자동 캡처)는 이미 `_1` 접미로 옳게 처리한다. 깨지는 건 **임시로 짜는 캡처 스크립트** 쪽이다 — 일회용이라고 이름 dedup 을 쓰지 말 것.
     - **감사할 때도 이름만 보면 안 된다.** `gog gmail thread get -p` 출력이 `attachment⇥이름⇥크기⇥타입⇥ID` 라 **크기까지 대조**하면 재수집 없이 누락을 판정할 수 있다. ⚠️ 다만 접미 정규화용 `_(\d+)$` 제거는 **날짜 접미(`_20150629`·`_150922`)를 먹어 오탐을 만든다** — 실측 4건. 접미 제거는 `_1`~`_9` 같은 한두 자리로 좁힐 것.

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
       (예 의학위원회 메일 → 기존 `의학위원회/`). ② **Drive 폴더 어휘 대조** — [`02_areas/brain-system/drive-folder-vocabulary.md`](../../../../projects/2nd-brain-vault/knowledge/02_areas/brain-system/drive-folder-vocabulary.md) 를 grep. Dr. Ben 이 vault 이전부터 Google Drive 에서 써 온 분류 어휘(3단계 스냅샷)다. **같은 뜻의 폴더가 이미 있으면 그 말을 쓴다** — 새 이름을 지어내지 않는다. 예: Drive 에 `KIRAMS/방사선안전관리` 가 있으면 `방사선안전관리업무`·`방사선안전` 같은 변형을 새로 만들지 않는다. **목적은 머릿속 지도를 한 벌로 유지하는 것** — vault 가 다른 말을 쓰면 Dr. Ben 이 두 어휘를 오가야 하고 그게 인지부하다. ③ 어휘에도 없으면 LLM 추론(그때는 새 이름을 짓되 대장에 기록).
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
       - **★ 사안 명명 규약 (2026-06-07)**: `YYYY-MM-DD_<조직토큰>_<부서>_<사안>`. 구조 구분자 = **`_` 통일**(날짜·조직·부서·사안 경계), 사안 내부는 무구분(예 `27대2차회의`). 사안 예: `27대N차회의`·`27대명단`·`27대N차일정`(씨앗).
         **전역 자기서술 유지** — 조직·부서 토큰을 *반드시 포함*(폴더 경로와 중복돼도): wikilink basename 은 폴더 맥락 없이 전역 고유·인지돼야 함(링크·인박스가 부서 밖에서 참조). 이 중복은 *전역 주소성의 대가*.
         **금지(인지부하·정렬 오류원)**: 날짜년도 중복(`2026-…_2026-제2차` ✗), 구분자 혼용(`_`+`-` ✗), 한 부서 내 형식 불일치(제N차 vs 27대N차 ✗) → **부서 내 한 형식**. (2026-06-07 KARP 의학위원회 3폴더 통일 실측.)
         - 🚫 **`회의록` 으로 끝내지 말 것 — vault 전역 규칙 (CLAUDE.md §회의 생애주기, 2026-07-30 강화)**. 회의는 **이벤트 컨테이너**이고 회의록은 그 안의 산출물 하나일 뿐이라 폴더·노트는 **`…회의`** 로 끝낸다. **메일 제목이 `…제4차 회의록`·`…회의록 회람` 이어도 마찬가지** — "회의록"은 컨테이너 안의 *파일명*으로만 남긴다.
           - 이건 "부서 내 일관성" 문제가 아니라 **전역 불변식**이다. 부서 전체가 `회의록` 으로 통일돼 있어도 위반이다.
           - 과거 회의록 파일을 자가전달한 **문서 캡처도 `…회의`** 로 끝낸다(그 회의를 가리키는 컨테이너이므로). 애매하면 `회의` 로 통일.
           - ⚠️ 실측: 캡처 자동화가 메일 제목을 그대로 폴더명에 써 2026-07-22 방안위 제4차가 `…제4차회의록` 이 됐고, 2026-07-30 에 vault 전체 **13건 일괄 rename**(참조 80파일 갱신)이 필요했다. **이 규칙이 지켜지는 지점은 캡처·배치 시점이다.**
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
- **`stale: true` → 묻지 말고 *갱신***(skip ✗). `inspect` 의 `existing_note_body` 와 새 메시지를 병합해
  `update_of` 노트를 제자리 갱신. 사람 편집(「내 생각」)은 보존. 헤드리스에서도 이 경로는 **자동**이다 —
  진행 중 스레드의 노트가 낡는 게 이 결함의 피해이고, 그건 무인 드레인이 고쳐야 할 몫이다.
- PARA 좌표가 모호 → 묻지 말고 **가장 그럴듯한 좌표로 낙관 배치 + `--confidence` 와 무관하게
  commit**(helper 가 `para_review: pending` 부착). 교정은 주간 감사가.
- `via: error`/markdown 비정상·refined.md 부재로 듀얼검증 필요 → `--confidence low` 로 commit(유실 0).
- **★ 파싱할 대상이 없으면 `low` 가 아니라 `--confidence n/a`** (2026-08-05). `low` 는 *파싱을 시도했는데
  결과가 부실*하다는 뜻이고, 그래야 나중에 `refined.md` 가 생겼을 때 renote 가 집어간다. 첨부가
  0건인 스레드(=`_thread.md` 만 있는 self-forward 등)는 애초에 파싱할 파일이 없어 **영원히 풀리지
  않는 플래그**가 된다 — 실측: IAEA RAS6097 3건이 매 보고마다 "파싱오류"로 떠 숫자를 오염시켰다.
  - 첨부 0 + **본문은 온전** → `--confidence n/a`. 정상이다. 아무것도 잃지 않았다.
  - 첨부 0 + **본문도 비어 있음**(헤더뿐) → `--confidence n/a --source-missing`. 이건 진짜 유실.
  - 첨부 있음 + 파싱 미완·부실 → `--confidence low` (기존 규칙 그대로 — renote 가 나중에 고친다).
- **회의록·문서 시리즈(확정 vs 중간본, §3-★)**: 확정 여부가 헤드리스로 불확실하면 **보수적으로 `--doc-status interim`**
  (source-trail, 요약 생략) + `para_review: pending` → 주간 감사가 정본 승급. 무인이 초안을 정본으로 적재해 knowledge
  오염시키는 것 방지(clutter < 유실, raw 는 보존됨). 명백한 확정본(회의 후 "회의록" 회람·"확정")만 final 요약.
- **인맥 반영 (자동 트랙·무인) — 교류갱신만, 신규 생성 ✗** — `matched` → 본문 `[[링크]]` + `link-event`(멱등) + per-field 추론 갱신
  (provenance 충돌 시 *묻지 말고* `gcontacts_review: flagged (필드 충돌:…)`) + 확정노트면 `contacts_sync --apply`.
  `unmatched`/`no_contact`/`held` → **로그(보고)만** — 자동은 신규 인맥을 만들지 않는다(2026-06-24, 생성은 수동 트랙 전용). `new-person` 자동 호출 ✗.
- 배치 "패턴 확인" 스텝 생략 — 인자로 받은 그 1건만 처리하고 끝낸다(턴당 1항목).

근거: [자동 우선·주간 감사 정책](../../../../projects/2nd-brain-vault/knowledge/02_areas/brain-system/automation-review-policy.md)
— 건별 승인 폐기 = 낙관 배치 + 플래그 + 주간 감사. 헤드리스는 이 정책의 구현이다.

## 모드 4 — 대기실 (`_hold`, 2026-08-07 신설) ★ 손으로 떨어뜨린 자료

**트리거**: "hold 처리해줘" · "_hold 에 넣은 거 브레인화해줘" · "대기실 정리해줘" · "내가 넣은 자료 정리해줘".

`sources/00_inbox/_hold/` 는 **Dr. Ben 이 손으로 떨어뜨리고 지시할 때까지 아무도 건드리지 않는 자리**다.
brain-drain 은 종료 2분 뒤 재발화하므로, 인박스에 그냥 두면 지시를 타이핑하는 사이에 무인 편입돼
맥락 없이 낙관 배치된다(그리고 복사 중인 큰 파일을 잘린 채로 집을 수도 있다). `_hold` 는 그 창을 없앤다.

- **양쪽 드레인이 제외한다** — `brainify.py _items()` 와 `parser-drain.sh candidates()` 둘 다.
  그래서 파싱조차 미리 돌지 않는다.
- **처리는 대기실을 인박스로 지목해서** 한다. 특수 분기 없이 스킬 전체가 그대로 돈다:

```bash
H="$BRAINIFY_VAULT/sources/00_inbox/_hold"        # 기본 vault 면 ~/projects/2nd-brain-vault
BRAINIFY_INBOX="$H" python3 brainify.py scan
BRAINIFY_INBOX="$H" python3 brainify.py inspect "<item>"
BRAINIFY_INBOX="$H" python3 brainify.py commit  "<item>" --para … --name … --body-file …
```

- ★ **`_hold` 에서 `00_inbox` 로 옮기지 말 것.** 옮기는 순간 무인 드레인의 2분 창이 다시 열린다.
  `commit` 이 `_hold` 에서 **최종 PARA 위치로 직행**한다.
- ★ **여기서는 물어봐도 된다.** 헤드리스와 정반대다 — Dr. Ben 이 옆에 있고, 애초에 *맥락을 주려고*
  대기실에 넣은 것이다. PARA 좌표·묶음 단위·제목이 모호하면 낙관 배치하지 말고 **확인**한다.
- 여러 파일을 **한 사안으로** 지시받으면 한 폴더로 묶어 노트 1개로 편입한다(낱개 N개 ✗).
- 처리 후 `_hold` 는 비운다. 남기면 다음 지시 때 뭐가 새 것인지 알 수 없다.
- 방치 감시: 아침 헬스체크의 `인박스 _hold 대기` 항목이 건수·최고령을 보고하고 7일 넘으면 `[!]`.
  드레인이 일부러 안 보는 자리라 **아무도 안 알려주면 그대로 사장되기 때문**이다.

## 모드 3 — 재작성 (`/brainify --renote "<note>"`, 2026-08-05 신설)

**뒤늦게 도착한 풀텍스트로 stub 노트를 다시 맞춘다.** `parse_confidence: low` 는 "노트를 쓸 때
`refined.md` 가 없었다"는 뜻인데(전형: `parse_via: pending-ocr`), extract·refine 이 나중에 성공해도
**노트는 저절로 고쳐지지 않는다** — `scan` 은 `00_inbox` 미처리 항목만 보고 filed 된 노트는 대상이
아니기 때문이다. 그 결과 파싱은 끝났는데 플래그만 영구히 남는다(2026-08-05 규명, 7건).

1. **후보** — `brainify.py renote-scan` → `ready: true`(붙어 있는 `_parse` 전부에 `refined.md` 존재)만 처리.
   `ready: false` 는 아직 refine 대기이므로 **건드리지 말 것**(다음 드레인이 채운다).
2. **재료** — `brainify.py renote-read "<note>"` → 기존 frontmatter·본문 + `refined.md` 전문 + `_thread.md`.
3. **판단 — 세 갈래.** 후보의 편차가 크므로 기계적으로 다시 쓰지 말 것:
   - **본문이 이미 풀텍스트와 부합** (촬영본 source-trail 등 원래 충분했던 노트) → **본문 유지**,
     `renote-write "<note>" --confidence ok` 로 **플래그만 내린다**(`--body-file` 생략).
   - **풀텍스트가 새 사실을 준다** → 요약·핵심을 보강해 `--body-file` 로 교체. **「내 생각」과 사람이 쓴
     문단은 반드시 보존**(병합이지 덮어쓰기가 아니다). `[[wikilink]]`·`sources:` 링크도 유지.
   - **refined.md 가 사실상 빈 텍스트·깨짐** → 다시 쓰지 말고 `--confidence low` 유지로 끝낸다(플래그 존치).
4. **기록** — `renote-write` 가 `renoted: YYYY-MM-DD` 를 붙인다. 같은 노트를 매 틱 다시 태우지 않게 하는 흔적.

헤드리스(`/brainify --headless --renote "<note>"`, brain-drain Phase C)에서도 같다 — 묻지 말고 위 세 갈래로
판단하고 끝낸다. **본문을 지우는 방향의 재작성은 금지**(유실 > clutter). 확신이 안 서면 플래그만 내린다.

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
