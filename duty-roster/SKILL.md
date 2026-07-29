---
name: duty-roster
description: >-
  핵의학과 월별 온콜당직표(xlsx)를 읽어 Dr. Ben(김병일)의 당직·판독 일정을 Google Calendar 에
  멱등 동기한다. 당직의사명→On Call(08:50–11:00), PET→PET판독(10:00–17:30),
  PET외→감마판독(10:00–17:30), 병동→병동당직(당일08:30~익일08:30, 전화 온콜·원내 상주 아님).
  "당직표 캘린더에 넣어줘",
  "이번달 온콜 일정 등록해줘", "/duty-roster" 류 트리거. 매달 재실행 안전(해당 월 마커분 삭제 후 재생성).
allowed_tools: [bash, read]
---

# duty-roster — 월별 온콜당직표 → Google Calendar

핵의학과 **월별 온콜당직 및 업무분장표**(`YYYY년_M월_핵의학과_온콜당직표_*.xlsx`)에서
**김병일(=Dr. Ben)** 에게 배정된 칸만 뽑아 캘린더 이벤트로 만든다. 매달 새 표가 오므로
**멱등 재실행**(해당 월 마커분을 지우고 다시 만듦)이 핵심 — 표가 수정·재발송돼도 다시 돌리면 정합.

- **결정형 메커니즘은 `roster.py`** (xlsx 파싱·날짜변환·gog 동기)에 위임. 외부 의존성 0
  (stdlib `zipfile`/`xml` 로 xlsx 직접 파싱 — 이 환경엔 openpyxl·pandas 미설치).
- 이 문서는 **소스 파일 찾기·이름/정책 확인·결과 검증**만 한다.

helper: `python3 ~/.claude/skills/duty-roster/roster.py <plan|sync> <xlsx> [opts]`

## 열 ↔ 업무 매핑 (헤더명으로 매칭 — 열 위치 이동에 견고)

| 헤더(엑셀)   | 업무      | 시간                    | 근무 형태     |
| ------------ | --------- | ----------------------- | ------------- |
| `당직의사명` | On Call   | 08:50 – 11:00           | 원내 상주     |
| `PET`        | PET판독   | 10:00 – 17:30           | 원내 상주     |
| `PET외`      | 감마판독  | 10:00 – 17:30           | 원내 상주     |
| `병동`       | 병동당직  | 당일 08:30 ~ 익일 08:30 | **전화 온콜** |

> ⚠️ **`병동당직` 은 병원 상주가 아니라 전화 온콜 당직**이다 — 전화를 받아 대응하는 형태라
> **물리적 위치를 구속하지 않는다**(자택·출장·이동 중에도 성립). 다른 일정과 겹쳐도
> **위치 충돌로 보고하지 말 것**. 실제 제약은 *통화 가능성* 뿐이라 통신 두절 구간
> (장거리 비행 등)과만 상충한다. 원내 상주가 필요한 건 나머지 3개 업무 쪽.
> (2026-07-29 Dr. Ben 확인 — 그전까지 상주로 오해해 출장 일정에 없는 충돌을 보고한 사례 있음.)

- 날짜 = `당직일자` 열(Excel serial). 한 사람이 하루 여러 업무에 배정될 수 있어 칸마다 별도 이벤트.
- 본인 이름 기본값 `김병일` (`roster.py` 의 `DEFAULT_NAME`). 바뀌면 거기만 수정.
- 계정 기본값 `kimbi.kirams@gmail.com` primary. gog keyring → `GOG_KEYRING_PASSWORD`
  (없으면 `~/.config/gogcli/.keyring-password` 자동 로드, [[reference_gog_keyring_password]]).

## 절차 (`/duty-roster`)

### 1. 소스 xlsx 찾기

당직표는 보통 `sources/00_inbox/` 에 드롭되지만, **brain-drain(brainify) 타이머가 먼저 돌면
`sources/02_areas/한국원자력의학원/<YYYY-MM-DD>_KIRAMS_핵의학과_*당직표*/` 로 이동**돼 있을 수 있다. 둘 다 탐색:

```bash
find ~/projects/2nd-brain-vault/sources -iname "*온콜당직*.xlsx" -o -iname "*핵의학과*당직*.xlsx" | sort
```

여러 월이 나오면 대상 월 확인. 경로에 한글이 있으니 **절대경로**로 helper 에 넘긴다(상대경로+cwd 리셋 주의).

### 2. plan — 부작용 없이 추출 검증

```bash
python3 ~/.claude/skills/duty-roster/roster.py plan "<xlsx 절대경로>"
```

`{month, name, count, events[]}` JSON 출력. `month`·`count`·유형별 분포를 사용자에게 보여
**엉뚱한 이름/달이 아닌지** 확인. count 0 이면 이름 매칭 실패(표의 표기 확인 — 동명이 아닌 풀네임인지).

### 3. sync — 멱등 동기

```bash
# 먼저 dry-run 으로 삭제/생성 건수 확인
python3 ~/.claude/skills/duty-roster/roster.py sync "<xlsx>" --dry-run
# 실제 동기
python3 ~/.claude/skills/duty-roster/roster.py sync "<xlsx>"
```

- 해당 월 마커(`duty_roster=<YYYY-MM>`) 이벤트를 **전부 삭제 → plan 대로 재생성**. 재실행해도 중복 0.
- 각 이벤트엔 private extended property `duty_roster=<월>` + `duty_type=<oncall|pet|gamma|ward>`.
  description 엔 출처 xlsx 명 기록.
- 출력 `{deleted, created_ok, created_fail}`. fail>0 이면 `results` 의 에러 보고.

### 4. 검증

```bash
gog calendar list primary -a kimbi.kirams@gmail.com \
  --from <월초> --to <다음달초> --private-prop-filter duty_roster=<월> --all-pages -p \
  | awk -F'\t' 'NR>1 && $4!=""{print $4}' | sort | uniq -c
```

유형별 건수가 plan 과 일치하는지 확인(list 는 서버 페이지당 10개라 **`--all-pages` 필수**).

## 정책·주의

- **알림(reminder) 없음** — 캘린더 계정 기본값만(2026-06-08 Dr. Ben 결정).
- **다른 의사 일정은 안 만든다** — 본인(김병일) 칸만. 과 전체 표지만 캘린더는 개인 일정.
- **기존 일반 반복 일정과의 충돌**: 2026-06 최초 도입 시 캘린더에 부정확한 *매주 월요일 PET판독*
  반복 series 가 있어 1회성으로 삭제했다(당직표 실제 배정과 불일치). 이건 **스킬의 매달 동작이 아니라
  1회 정리** — 새 달엔 그 series 가 없으므로 sync 는 순수 당직표→캘린더만 한다. 비슷한 일반 반복이
  또 보이면 사용자에게 확인 후 별도 처리.
- **소스 파일 자체의 PARA 편입**(이동·동반 노트)은 이 스킬이 아니라 [[brainify]]/brain-drain 의 일.
  duty-roster 는 *캘린더 동기*만 — 경계 분리.

## 한계 (xlsx 형식 가정)

- 첫 워크시트(`sheet1.xml`)에 `당직일자`+`당직의사명` 헤더가 한 행에 있다고 가정. 형식이 크게 바뀌면
  `find_header` 가 실패(명시적 에러). 그땐 표 구조 확인 후 `roster.py` 의 `DUTIES` 매핑 갱신.
- 날짜 셀은 Excel serial(>40000) 숫자 가정. 텍스트 날짜면 `serial_to_date` 보강 필요.
