---
name: contact-capture
description: >-
  sources/00_inbox/_hold/ 에 쌓인 사람 사진(명함·KIRAMS 원내 직원검색 스크린샷)을 인맥 노트 +
  Google Contacts(텍스트+사진)로 편입한다. "_hold에 명함/사우정보 있다", "이 사람들 인맥에 등록해줘",
  "셔틀로 캡처한 사우정보 처리해줘", "/contact-capture" 류 트리거. USB 셔틀(원내 직원검색)과 현장 명함
  촬영 둘 다 대상 — 뒷단(중복확인→노트→Contacts 텍스트→사진)은 공통, 원본 처리 정책만 유형별로 갈린다.
allowed_tools: [bash, read, edit, write]
---

# contact-capture — 사람 사진 캡처 → 인맥 노트 + Google Contacts

`sources/00_inbox/_hold/` 에 드롭된 사람 사진 1장당 1건을 처리한다. 두 캡처 유형을 구분해서 읽되,
뒷단 파이프라인은 공통이다.

## 캡처 유형 판별 (이미지를 Read 로 본 뒤 첫 판단)

- **A. KIRAMS 원내 직원검색 스크린샷** — 고정 표 레이아웃(성명·사용자ID·부서·직위·직급·직장전화·직장FAX·휴대폰·메일·직장주소). 파일명이 보통 `<이름>.PNG`(USB 셔틀 `SHUTTLE` `IN\` 경유, vault CLAUDE.md §USB 셔틀 참조). → `affiliation_scope: internal`.
- **B. 명함(현장 촬영)** — 회사 로고·자유 레이아웃, 파일명이 `20260904_153157.jpg` 류 타임스탬프 또는 `명함*.jpg`. → 보통 `affiliation_scope: external`(간혹 원내 동료 명함도 있음 — 조직명으로 판단).

## 절차

### -1. USB 셔틀 반입 (선행, `SHUTTLE\IN\` 에 원본이 있을 때만)

원내 캡처(유형 A)는 보통 `_hold/` 에 바로 있지 않고 `SHUTTLE` USB 에 있다. `_hold/` 스캔(0단계)이 비어 있으면
먼저 이 단계로 셔틀→`_hold` 반입을 시도한다 (vault CLAUDE.md §USB 셔틀 — 컨베이어, 상주 데이터 0 원칙).

1. **볼륨 라벨로 드라이브 문자 확인** (포트마다 문자 바뀜 — 하드코딩 금지):
   ```bash
   powershell.exe -Command "Get-Volume | Where-Object FileSystemLabel -eq 'SHUTTLE' | Select-Object DriveLetter,FileSystemLabel"
   ```
2. **`IN\` 내용물 확인** (한글 파일명 깨짐 방지 — UTF8 출력 인코딩 필수, `$_` 는 bash 확장 방지 위해 반드시 작은따옴표로 감싼 `-Command` 안에 쓴다):
   ```bash
   powershell.exe -Command '[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; Get-ChildItem -Path "<드라이브>:\IN" -Recurse -File | ForEach-Object { $_.FullName }'
   ```
3. **`_hold/` 로 복사** — WSL2 는 임의 드라이브를 자동마운트하지 않고 `/mnt/<문자>` 수동마운트는 sudo 비대화식 인증이 막혀 있으므로, **UNC 경로(`\\wsl.localhost\<배포판>\...`) 로 PowerShell `Copy-Item` 을 직접 쓴다** (배포판 이름은 `powershell.exe -Command "wsl -l -v"` 로 확인):
   ```bash
   powershell.exe -Command 'Copy-Item -Path "<드라이브>:\IN\<파일명>" -Destination "\\wsl.localhost\<배포판>\home\ben\projects\2nd-brain-vault\sources\00_inbox\_hold\<파일명>"'
   ```
4. **복사 검증 후에만 원본 삭제** — `ls sources/00_inbox/_hold/` 로 크기·존재 확인 후 USB 원본을 지운다(상주 0 정책 실행):
   ```bash
   powershell.exe -Command 'Remove-Item -Path "<드라이브>:\IN\<파일명>" -Force'
   ```
   삭제 후 `IN\` 재조회로 빈 것 확인. 검증 없이 먼저 지우지 않는다 — 복사 실패 시 원본이 유일한 사본이다.

이후 0단계부터 정상 진행한다(방금 반입한 파일이 `_hold/` 스캔에 걸린다).

### 0. 스캔

```bash
find sources/00_inbox/_hold -maxdepth 1 -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.heic" \) 2>/dev/null
```
(`.md`/`.txt`/`README.md` 등 비이미지는 무시 — 다른 캡처의 보류함일 수 있음, 손대지 않는다.)

### 1. 이미지별 Read + 필드 추출

Read 도구로 이미지를 본다(Vision). 유형별 추출 필드:

| 필드 | A. 원내 캡처 | B. 명함 |
|---|---|---|
| 이름 | 성명 | 인쇄된 이름 |
| 부서/직위 | 부서·직위·직급 | 직함 |
| 조직 | 한국원자력의학원(고정) | 명함 회사명 |
| 이메일 | 메일 | 명함 이메일 |
| 휴대폰 | 휴대폰 | 명함 휴대폰(있으면) |
| 직장전화(원내) | 직장전화 | 명함 대표/직통번호(있으면) |
| 사원번호 | 사용자ID | (보통 없음) |

### 2. 중복 확인 (쓰기 전 항상)

```bash
find knowledge/02_areas/인맥 -iname "*<이름>*"
gog contacts search "<이름>" --account kimbi.kirams@gmail.com -j --results-only
gog contacts search "<이메일>" --account kimbi.kirams@gmail.com -j --results-only
```

- 기존 노트/Contact 있으면 **동일인 여부 판단** — 소속·전화 다르면 별개 인물(동명이인, [[reference-contacts-sync-create-gotchas]] §3 원칙). 확신 없으면 Dr. Ben 에게 묻는다.
- 동일인이면 노트 갱신(`## 교류 이력` 1줄 + `last_interaction`)만, 신규 Write 금지.

### 3. 인맥 노트 작성/갱신

`knowledge/02_areas/인맥/_template.md` 기준. 전화번호는 **frontmatter 에 E.164 로 저장** (`phone`=휴대폰, `phone_office`=직장전화 — 둘 다 `+82` 로 시작, 자릿수는 지역번호 선행 0 만 제거·유지. 예: `02-3399-5848` → `+82233995848`). 본문 `## 연락처` 섹션엔 사람이 읽는 하이픈 표기 그대로 적어도 된다(그건 어차피 vault 전용).

⚠️ **frontmatter 계산 실수 주의** — 2026-09-07 5건 중 전부 지역번호 자릿수 오류가 났었다(`02-970-1615` → `+82229701615`(오)가 아니라 `+8229701615`(정)). 헷갈리면 python 으로 검산:
```bash
python3 -c "import re; d=re.sub(r'\D','','02-3399-5848'); print('+82'+d[1:])"
```

### 4. Google Contacts 텍스트 동기 — `contacts_sync.py`

```bash
python3 ~/.claude/skills/brainify/contacts_sync.py sync "<노트stem>" 2>&1        # preview 먼저
python3 ~/.claude/skills/brainify/contacts_sync.py sync "<노트stem>" --apply 2>&1
```

`phone`/`phone_office` 를 자동으로 `phoneNumbers`(type mobile/work)에 매핑하고, push 직전 **한국식 하이픈 표기로 변환**(`format_kr_phone`)해서 Google Contacts 앱에 `+821047327570` 같은 원시 E.164가 아니라 `010-4732-7570` 로 보이게 한다 — 2026-09-07 Dr. Ben 지적으로 코드화됨. `google_contact_id` 없으면 create, 있으면 update(기존 비관리 필드는 보존).

### 5. 얼굴 사진 크롭 (유형 A 전용 — 원내 캡처)

Google Contacts 사진 = **얼굴 사진만**(표 전체·글자 X). ⚠️ 2026-09-07 김승현 건에서 스크린샷
전체(673×274, 표+글자 포함)를 그대로 올려버린 실수가 있었다 — 반드시 크롭 후 업로드한다.

1. Read 로 이미지를 본 뒤(원본 픽셀크기는 Read 결과의 "[Image: original WxH...]" 안내로 확인) 얼굴 사진 박스의
   픽셀 좌표(x0,y0,x1,y1)를 육안으로 특정한다 — 보통 표 좌상단, 표 테두리 안쪽.
2. PIL 로 **그 자리에서 원본 파일을 크롭본으로 덮어쓴다**(별도 경로에 저장하면 다음 단계가 원본 대신
   크롭본을 못 지운다 — 반드시 같은 경로 overwrite):
   ```bash
   python3 -c "
   from PIL import Image
   p = 'sources/00_inbox/_hold/<이름>.PNG'
   Image.open(p).crop((x0,y0,x1,y1)).save(p)
   "
   ```
3. Read 로 크롭 결과를 다시 확인 — 얼굴만 깨끗이 담겼는지(표 줄·글자 섞임 없는지) 검증 후에만 6단계 진행.
   애매하면 좌표를 조정해 재시도.

명함(유형 B)은 보통 얼굴 사진이 없으므로 이 단계 생략 — 명함에 사진이 박혀 있는 드문 경우만 동일하게 크롭.

### 6. 사진 업로드 — `contacts_photo.py`

```bash
python3 ~/.claude/skills/brainify/contacts_photo.py "<노트stem>" "<이미지경로>" [--keep-source]
```

- **원내 캡처(유형 A)**: 5단계에서 크롭해 둔 그 경로(`_hold/<이름>.PNG`)를 그대로 넘긴다. `--keep-source` 없이 실행 — **업로드+검증 성공 후에만** 스크립트가 스스로 원본(=크롭본)을 지운다(vault 는 사진을 저장하지 않는 기존 정책, [[project-contacts-two-tier-model]] R7). 실패하면 파일이 그대로 남아 재시도 가능.
- **명함(유형 B)**: 얼굴 사진이 있는 드문 경우만 — 먼저 원본을 `sources/02_areas/인맥/명함/YYYY-MM-DD_<출처>_<이름>_명함.jpg` 로 **영구 보존 이동**(명함은 교환 증거이자 향후 OCR 재검증 대상이라 vault 에 남긴다). 이동 후 그 경로로 `--keep-source` 호출(파일이 이미 sources/ 로 옮겨졌으므로 지울 필요 없음). 얼굴 사진이 없는 보통의 명함은 이 단계 자체를 생략 — 카드 이미지를 Contacts 사진으로 쓰지 않는다.

⚠️ **2026-09-04 KIRAMS 5명 사고 재발 방지가 이 스킬의 핵심 존재 이유** — 그때는 텍스트만 뽑고 사진 단계 없이 원본을 바로 `rm` 해서 사진이 영구 소실됐다. 이 스킬 순서대로면 원본을 지울 방법은 "업로드·검증 성공"뿐이다.

> 만약 이미 크롭 없이(스크린샷 전체로) 업로드해버렸다면 — Google Contacts 의 `photos[].url` 에 `=s0` 를 붙이면 방금 올린 원본 해상도를 그대로 되받을 수 있다(2026-09-07 김승현 건 복구 경로). `_hold` 원본이 이미 지워졌어도 이 경로로 재크롭·재업로드 가능. 단, **다음 캡처부터는 이 복구에 의존하지 말 것** — 원내 캡처(유형 A) 5단계를 매번 반드시 거친다.

### 7. `_hold` 정리 확인

```bash
ls sources/00_inbox/_hold/
```
남은 게 있으면(실패한 항목·아직 판별 못한 파일) 이유를 보고하고 다음 실행까지 그대로 둔다. `.md`/`README.md` 는 무시.

### 8. 요약 보고

이름별 표: 유형(A/B) · 신규/갱신 · Google Contact 결과 · 사진 업로드 결과.

## 참고

- 이 스킬은 vault 노트 작성·PARA 판단·Vision 필드추출은 **Claude 판단**으로, phoneNumbers 매핑·사진 업로드 API 호출 같은 **결정형 부분은 `~/.claude/skills/brainify/{contacts_sync,contacts_photo}.py`** 에 위임한다(`brainify` skill 과 도구 공유 — 별도 구현 아님).
- 병원메일(.eml)이 같은 `_hold`/inbox 에 함께 있으면 이 스킬 대상이 아니다 — `brainify` 로 별도 처리.
- 스키마·명명 규칙 권위 = `knowledge/02_areas/인맥/README.md`(§Stage 1-D 원내 캡처 채널·프론트매터 필드 목록).
