---
name: brainify-inbox
description: sources/00_inbox/ 의 PDF 들을 Docling+MinerU 듀얼 파싱·요약하고, Claude 가 두 출력의 diff 를 시각 검증한 뒤 PARA 분류·파일명을 제안 → Dr. Ben 승인 → sources/ 정식 위치로 이동 + knowledge/ 동반 노트 생성하는 인터랙티브 스킬. "인박스 브레인화", "PDF 정리해줘", "오늘 들어온 자료 처리", "/brainify-inbox" 류 트리거.
allowed_tools: [bash, read, write, edit]
status: active
---

# brainify-inbox

`~/projects/2nd-brain-vault/sources/00_inbox/` staging 폴더의 PDF 자료를 듀얼 엔진 (Docling + MinerU) 으로 로컬 파싱하고, Claude 가 두 출력을 시각 검증한 뒤, PARA 분류·파일명·동반 노트 초안을 Dr. Ben 에게 제안. 승인 후 일괄 이동 + 동반 노트 생성. 외부 API 호출 0 (재무자료 leak 방지).

## 거버넌스

이 스킬의 **spec 권위 원본은 같은 디렉토리의 `PROGRESS.md` (mini SDD)**. §Spec·§Plan 변경은 Dr. Ben 승인 후 PROGRESS.md 가 먼저 갱신되고, 본 SKILL.md 는 그 위에서 정렬. 본 SKILL.md 는 *런타임 절차서* 만 담음 (왜·무엇을 만드는가는 PROGRESS.md 참조).

호출 시 모델은 먼저 PROGRESS.md 의 §Tasks 현재 진행 상태를 확인. 미완료 항목 (Phase 0~1) 이 남아 있으면 *구현이 아직 안 됨* 을 보고하고 종료 — `status: design-only` 시그널.

## OpenClaw SKILL_CONTRACT 와의 정렬·예외

본 스킬은 `~/.openclaw/workspace/SKILL_CONTRACT.md` (L1) 를 Claude Code 의미로 재해석해 적용한다 (Dr. Ben 결정 2026-05-13, Q2=a):

### 정렬

- **§1 frontmatter** — 그대로 (`name`·`description`·`allowed_tools` 명시).
- **§4 exit code** — 컨테이너 호출 (`docker compose run brain-pdf ...`) 의 exit code 를 신뢰. 0 이외는 비정상 보고.
- **§5 수동 테스트** — 공유 라이브러리 entrypoint 가 *Claude 매개 없이* 직접 호출 가능해야 함:
  ```bash
  docker compose -f ~/projects/2nd-brain-docker/compose.yaml run --rm brain-pdf parse-docling <pdf>
  docker compose -f ~/projects/2nd-brain-docker/compose.yaml run --rm brain-pdf parse-mineru  <pdf>
  docker compose -f ~/projects/2nd-brain-docker/compose.yaml run --rm brain-pdf diff <docling.md> <mineru.md>
  ```
  (정확한 명령 형식은 P1.3 stack 설계 후 확정.)
- **§8 vault SSOT** — vault 콘텐츠 (knowledge·sources) 가 단일 권위 원본. 스킬은 *읽거나 쓸 수 있지만* vault 의 의미 구조를 자기 안에 중복 정의하지 않는다. CLAUDE.md 의 PARA 분류·파일명 규칙·동반 노트 frontmatter 표준을 그대로 따른다.

### 예외 — L1 §3 (stdout 규칙)

본 스킬은 L1 §3 (빈 stdout → 침묵, 텍스트 → 글자 단위 forward) 을 따르지 않는다.

**이유**: 본 스킬은 *Claude 의 인터랙티브 절차* 다 — Dr. Ben 과 분류 제안·승인을 대화로 주고받는다. OpenClaw 의 stdout 침묵 규칙은 agent forwarding 모델 (run.py 가 결정 로직, agent 는 통로) 을 전제하나, 본 스킬은 Claude 자신이 결정·대화·승인을 수행. 따라서 Claude 는 PROGRESS.md §Spec·§Plan 의 절차에 따라 능동적으로 사용자와 대화한다.

**대신 유지하는 결정성**: 핵심 파싱·diff·이동 *연산* 은 Bash 로 호출한 컨테이너 entrypoint 에 위임 (run.py 의 역할에 해당). Claude 의 reasoning 자유도는 분류 *제안*·시각 *검증*·승인 *대화* 에 한정한다. 표 수치·파일 이동·노트 작성의 결정성은 컨테이너 측 코드가 보장.

### 예외 — L1 §6 (영속 상태 위치)

상태 저장이 필요하면 `~/.openclaw/agents/main/memory/` 대신 `~/.claude/skills/brainify-inbox/state/processed.jsonl` 사용 (Claude Code 의 메모리 layer 가 아님). git 미추적, 머신별 독립. 자세한 형식은 P3.4 에서 결정.

### N/A — L1 §7 (자격증명)

외부 API 사용 ✗ → 자격증명 없음.

## 호출 패턴

Dr. Ben 의 트리거 (자연어 또는 슬래시):

| 사용자 입력 | 절차 분기 |
|---|---|
| "인박스 브레인화", "PDF 정리해줘", "오늘 들어온 자료 처리", "/brainify-inbox" | 전체 절차 (스캔 → 듀얼 파싱 → 시각 검증 → 분류 제안 → 승인 → 이동·노트 생성) |
| "/brainify-inbox status" | `00_inbox/` 의 현재 파일 목록과 처리 이력만 보고, 변경 ✗ |
| "이거 [파일명] 만 브레인화" | 단일 PDF 만 처리 (배치 ✗) |

`design-only` 단계에서는 *어느 트리거든* 미구현 보고 + PROGRESS.md §Tasks 현재 상태 안내 후 종료.

## 절차

> Phase 1~3 마감 (2026-05-14) — 본 절차는 호출 시 실행된다. 디자인 단계로의 회귀가 필요하면 frontmatter `status: active` → `design-only` 로 되돌릴 것.

### 0. 전제 확인

- `~/projects/2nd-brain-vault/sources/00_inbox/` 존재 + PDF 1건 이상.
- `docker compose -f ~/projects/2nd-brain-docker/compose.yaml ps` 으로 brain-pdf 서비스 사용 가능 확인.
- 전제 미충족 시 명시적 메시지 (어느 전제가 미충족인지) 후 종료.

### 1. inbox 스캔

- `ls ~/projects/2nd-brain-vault/sources/00_inbox/*.pdf` 로 PDF 목록 + 파일 크기·mtime 수집.
- 0건이면 "처리할 PDF 없음" 보고 후 종료.
- 1건 이상이면 처리 계획 (몇 건·예상 소요) Dr. Ben 에게 보고.

### 2. 듀얼 파싱 (각 PDF)

각 PDF 에 대해 순차로 (병렬은 GPU 메모리 경합 위험 — Phase 1 = 순차 권장).

**호출 형식**: `~/projects/2nd-brain-docker/` 의 `scripts/detect-compose.sh` 가 PC 환경 (NVIDIA 유무) 을 자동 감지해 적절한 compose 체인 출력. 양 PC 공통.

```bash
# 호스트 임시 디렉토리를 컨테이너 /work 에 마운트 — diff subcmd 가 두 파싱 결과를 한 컨테이너 안에서 읽을 수 있게 함.
WORKDIR=$(mktemp -d -t brainify-XXXXXX)
cd ~/projects/2nd-brain-docker
COMPOSE=$(./scripts/detect-compose.sh)   # auto: desktop=gpu / laptop=cpu
INBOX_CONTAINER=/home/user/projects/2nd-brain-vault/sources/00_inbox

for pdf in <inbox PDFs>; do
  stem="${pdf%.pdf}"
  docker compose $COMPOSE run --rm -v "$WORKDIR:/work" brain-pdf brain-pdf parse-docling "$INBOX_CONTAINER/$pdf" > "$WORKDIR/$stem.docling.json"
  docker compose $COMPOSE run --rm -v "$WORKDIR:/work" brain-pdf brain-pdf parse-mineru  "$INBOX_CONTAINER/$pdf" > "$WORKDIR/$stem.mineru.json"
  docker compose $COMPOSE run --rm -v "$WORKDIR:/work" brain-pdf brain-pdf diff "/work/$stem.docling.json" "/work/$stem.mineru.json" > "$WORKDIR/$stem.diff.json"
done
```

성능 차이: 데스크탑 GPU = parse-mineru ~30 초, 노트북 CPU = parse-mineru ~80-150 초 예상 (Arrow Lake-H CPU 추론). 컨테이너 이미지·코드 동일, PyTorch 가 runtime 에 CUDA/CPU 백엔드 자동 선택.

### 3. Diff 검증 + 정제본 (refined.md) 작성

각 PDF 의 `diff.json` 을 Read 로 읽어:

- **일치 (임계값 이내)** → 두 엔진 중 하나 (Docling 우선) 의 출력을 채택. 시각 검증 생략.
- **불일치 (임계값 초과)** → 차이 발생 페이지 번호 추출. Claude 가 원본 PDF 의 해당 페이지를 Read 도구로 시각 해석. 두 출력 중 *어느 쪽이 원본에 더 부합하는지* + *왜* 를 1줄 사유로 결정. 사유는 동반 노트 본문에 기록.

검증 후 **정제본 작성** — Claude 가 raw 두 markdown 의 강점만 취하고 시각 검증으로 보정한 결과를 `_parse/refined.md` 에 작성:

```yaml
---
source_pdf: sources/<PARA>/<새stem>.pdf
base_engine: docling           # 또는 mineru — 채택한 raw 엔진
corrections:                   # 보정 사유 (불일치 발생 시)
  - "예: heading 'X' 누락 인식 — docling 채택"
  - "예: 표 셀 '54,250' MinerU 오인식 → PDF 시각 검증 후 docling 채택"
generated: YYYY-MM-DD
host: <hostname>
---

<본문 — 정제된 풀텍스트 markdown>
```

- 일치 회차: base_engine 의 markdown 그대로 + `corrections: []` 빈 list
- 불일치 회차: 시각 검증 사유에 따라 본문 보정 + corrections 에 변경 기록
- refined.md 의 본문은 PDF 의 모든 내용을 담은 풀텍스트 — 동반 노트의 §핵심내용 (요약) 과 역할 분리. 동반 노트는 인지·관찰, refined.md 는 원본 충실 재현.

### 4. 중복·연결 검사 (CLAUDE.md §0)

각 PDF 의 추출 메타 (제목·저자·날짜·핵심 키워드) 로:

```bash
grep -ril "<핵심 키워드>" ~/projects/2nd-brain-vault/knowledge/
```

히트 3~5개만 Read 로 확인. 유사·관련 노트 발견 시 분류 제안 시 `[[wikilink]]` 후보로 제시. 모호 시 "이거 이미 있지 않나요?" Dr. Ben 에게 확인.

### 5. PARA 분류·파일명·동반 노트 제안

각 PDF 에 대해 표 형식으로 제안:

| 원본 | 제안 분류 | 제안 파일명 | 동반 노트 요약 | 관련 노트 후보 |

CLAUDE.md 의 파일명 규칙 (`YYYY-MM-DD_출처_내용.ext` 이벤트 / `저자_연도_주제.ext` 학술) 준수.

### 6. Dr. Ben 일괄 승인

"이대로 진행해도 될까요?" — 같은 출처·유사 형식은 패턴 승인. 새 출처·이질적 자료는 개별 승인. Dr. Ben 이 분류·파일명·노트 내용 수정 요청 시 즉시 반영.

### 7. 이동·노트 생성 + 파싱 원본 보존

승인 받은 PDF 별로 순차:

1. `mv ~/projects/2nd-brain-vault/sources/00_inbox/<원파일> ~/projects/2nd-brain-vault/sources/0X_.../<새이름>.<ext>`
2. **파싱 원본 보존** — 원본 PDF 와 같은 디렉토리에 `<새stem>/_parse/` sub-folder 생성:
   ```bash
   PARSE_DIR=~/projects/2nd-brain-vault/sources/0X_.../<새stem>/_parse
   mkdir -p "$PARSE_DIR"
   mv "$WORKDIR"/{<원stem>.docling.json,<원stem>.mineru.json,<원stem>.diff.json} \
      "$PARSE_DIR"/{docling.json,mineru.json,diff.json}
   ```
   - `_parse/` 접두어 `_` 는 Obsidian 탐색 시 정렬 최하단 + vault 검색 잡음 최소화 의도
   - 파일명은 단순화 (`<stem>.docling.json` → `docling.json`) — 폴더가 이미 stem 으로 식별
   - 3개 JSON 내용 (entrypoint 의 stdout JSON 그대로):
     - `docling.json` — markdown + doctags + json_structure + pages + runtime_sec
     - `mineru.json` — markdown + json_structure (middle.json) + pages + runtime_sec. **MinerU sub-artifacts (layout.pdf, span.pdf, images/) 는 entrypoint 의 tempdir cleanup 시 손실 — Phase 2 future work**
     - `diff.json` — 구조적 비교 metrics + thresholds + verdict + details
   - **Obsidian 비교 편의용 추가 파일** (§7-2-extra):
     - `docling.md` — `docling.json` 의 `markdown` 필드만 추출 (`python3 -c "import json; print(json.load(open('docling.json'))['markdown'])" > docling.md`)
     - `mineru.md` — 동일 패턴으로 `mineru.json` 의 markdown 필드 추출
     - **`refined.md`** — §3 에서 작성한 정제본 (Claude 가 raw 둘을 보정한 풀텍스트, frontmatter + 본문)
3. `~/projects/2nd-brain-vault/knowledge/0X_.../<새이름>.md` 작성:
   - frontmatter (CLAUDE.md 표준 — `title`·`source`·`date`·`tags`·`sources:` 상대경로 + **`parse:` 상대경로**)
     ```yaml
     sources: sources/0X_.../<새stem>.<ext>
     parse:   sources/0X_.../<새stem>/_parse/
     ```
   - 본문 첫 줄: `[원본 PDF](sources/0X_.../<새stem>.<ext>)`
   - 한 줄 요약 / 핵심 내용 / 내 생각 / `[[관련 노트]]` 링크
   - 듀얼 파싱 채택 엔진 + 사유 (불일치 시) 기록
4. 실패 시 즉시 중단·보고 (이미 이동된 파일은 그대로 두고 어디서 멈췄는지 명시).

### 8. 마무리

- `00_inbox` 비어짐 확인 (`ls`).
- WORKDIR (`/tmp/brainify-XXXXXX/`) — §7-2 에서 `_parse/` 로 mv 한 후 빈 디렉토리만 남음. `rmdir "$WORKDIR"` 로 정리.
- 처리 이력 `state/processed.jsonl` 에 append (SHA·원본 경로·정착 경로·`parse_dir` 경로·diff 채택 사유).
- 요약 보고 (처리 건수·소요 시간·시각 검증 발생 건수·`_parse/` 정착 디렉토리 목록).

## Acceptance examples

(spec-driven 의 핵심 — 구현 전에 명시. 실제 검증은 Phase 4 에서.)

### 예시 1 — 0건 회차

**입력**: `00_inbox/` 비어 있음. 사용자 "인박스 브레인화"
**기대 출력**: "처리할 PDF 없음. `00_inbox/` 가 비어 있습니다." 후 종료.

### 예시 2 — 정상 1건 (의학논문, 영문)

**입력**: `00_inbox/Kim_2024.pdf` 1건. 사용자 "/brainify-inbox"
**기대 절차**:
1. 처리 계획 보고 ("1건 처리 예정, 예상 ~30초")
2. 듀얼 파싱 → diff 임계값 이내 → Docling 채택
3. 중복 검사 → `[[Lee_2023]]` 유사 후보 발견
4. 제안: `sources/03_resources/PET/Kim_2024.pdf` + 동반 노트
5. 승인 후 이동·노트 생성 → 완료 보고

### 예시 3 — diff 발생 (회계보고서, 한글 표)

**입력**: `00_inbox/2026-04-21_karp_영수증.pdf`
**기대 절차**: §3 에서 표 수치 diff 발생 → Claude Read 도구로 영수증 페이지 시각 해석 → MinerU 채택 (한글 표 정확) + 사유 "MinerU 가 금액 컬럼 정렬 정확, Docling 은 1행 오정렬" → 동반 노트에 사유 기록.

### 예시 4 — 미구현 단계 호출 (현재)

**입력**: 사용자 "/brainify-inbox" (Phase 0~1 미완료 상태)
**기대 출력**: "본 스킬은 현재 `status: design-only` 입니다. PROGRESS.md §Tasks 의 현재 진행 상태: Phase 0 P0.2 진행 중. 구현 완료 전 호출 불가." 후 종료.

## Manual test commands

호스트 cwd 가 `~/projects/2nd-brain-docker/`. Makefile 타겟이 `detect-compose.sh` 통해 PC 환경 자동 감지 — 양 PC (데스크탑 RTX 3060 / 노트북 Intel Arc) 에서 같은 명령으로 작동.

```bash
# 컨테이너 빌드 — 양 PC 공통. 데스크탑은 자동 GPU 활성, 노트북은 자동 CPU.
make build-brain-pdf

# 버전 확인
make run-brain-pdf ARGS="brain-pdf --version"   # → 0.2.0

# 단일 PDF 파싱 (Docling)
make run-brain-pdf ARGS="brain-pdf parse-docling /home/user/projects/2nd-brain-vault/sources/00_inbox/<sample>.pdf" > /tmp/a.json

# 단일 PDF 파싱 (MinerU)
make run-brain-pdf ARGS="brain-pdf parse-mineru /home/user/projects/2nd-brain-vault/sources/00_inbox/<sample>.pdf" > /tmp/b.json

# Diff (두 파싱 결과 — 컨테이너 안에서 두 파일이 보여야 하므로 동일 -v 마운트 사용)
WORKDIR=$(mktemp -d) && cp /tmp/{a,b}.json "$WORKDIR/"
COMPOSE=$(./scripts/detect-compose.sh)
docker compose $COMPOSE run --rm -v "$WORKDIR:/work" brain-pdf brain-pdf diff /work/a.json /work/b.json

# Offline 검증 (네트워크 차단 — docker compose run 은 --network 미지원이라 raw docker run 사용)
# GPU 있는 PC: --gpus all 추가. 없는 PC: 그 flag 제외. detect-compose.sh 우회라 수동 분기.
docker run --rm --network none $([ "$(./scripts/detect-compose.sh | grep -c gpu.yml)" -eq 1 ] && echo "--gpus all") -u 1000:1000 \
  -v "$HOME/projects/2nd-brain-vault:/home/user/projects/2nd-brain-vault" \
  -v "2nd-brain-docker_brain-pdf-models:/home/user/.cache/huggingface" \
  2nd-brain/brain-pdf:2026.05.14 \
  brain-pdf parse-docling /home/user/projects/2nd-brain-vault/sources/00_inbox/<sample>.pdf

# 강제 변형 (디버깅):
BRAIN_PDF_FORCE_VARIANT=cpu make run-brain-pdf ARGS="brain-pdf --version"   # NVIDIA 있는 PC 에서 강제 CPU
BRAIN_PDF_FORCE_VARIANT=gpu make run-brain-pdf ARGS="brain-pdf --version"   # 감지 misfire 시 강제 GPU
```

호출 형식의 `brain-pdf brain-pdf` 중복은 의도 — 앞은 compose **서비스명**, 뒤는 컨테이너 안 **CLI binary**. ENTRYPOINT 미설정 (daemon `sleep infinity` CMD 와 공존 위함) 의 결과.

## 외부 의존

- **Docker** + **2nd-brain-docker** repo (`~/projects/2nd-brain-docker/`) 의 `brain-pdf` 서비스. P1.3 에서 추가.
- **Vault** (`~/projects/2nd-brain-vault/`) — sources·knowledge 읽기·쓰기.
- **Docling 모델 가중치** + **MinerU 모델 가중치** — Docker volume 또는 host-mount 캐시에 영속. 첫 실행 시 1회 다운로드.

## 관련 자산 포인터

- `PROGRESS.md` (이 디렉토리) — mini SDD. §Spec·§Plan·§Tasks·§Checklist 권위 원본.
- `~/projects/2nd-brain-vault/CLAUDE.md` — vault 운영 매뉴얼. PARA·파일명·frontmatter 표준 권위 원본.
- `~/projects/2nd-brain-vault/knowledge/02_areas/brain-system/workflows/openclaw-skill-dev.md` — 스킬 dev/prod 분리 워크플로우 (Phase 5 OpenClaw 승격 시 참조).
- `~/.openclaw/workspace/SKILL_CONTRACT.md` — OpenClaw L1 계약. 본 스킬이 재해석해 적용한 invariant 의 원본.
- `~/projects/2nd-brain-docker/` (P1.3 에서 brain-pdf 서비스 추가될 곳).

## 메타

- 2026-05-13 — 최초 작성 (P0.2). PROGRESS.md (P0.1) 직후. Dr. Ben 결정 Q1=YES (mini SDD) + Q2=a (SKILL_CONTRACT 재해석 적용) + P1.1=b + P1.2=Docker 반영.
- 2026-05-14 — **활성화** (`status: design-only` → `active`). Phase 1~3 (P1.1~P3.4) 모두 마감. 4 PDF (학회 참석확인증 3 + 회계공시 1) 로 절차 전체 검증 통과. Manual test commands 와 §2 호출 형식을 P1.3/P2.x 확정 후의 실제 form 으로 갱신 (compose overlay 3종·WORKDIR 마운트·`brain-pdf brain-pdf` 이중 호출 명시). brain-pdf 이미지는 `2026.05.14` (VERSION 0.2.0).
- 2026-05-15 — **파싱 원본 보존 도입**. §7 에 `sources/<PARA>/<새stem>/_parse/{docling,mineru,diff}.json` sub-folder 생성 단계 추가. 동반 노트 frontmatter 에 `parse:` 필드 표준화. §8 에 WORKDIR rmdir 명시 + processed.jsonl 에 `parse_dir` 필드 추가. Dr. Ben 의 "파싱 원본도 보존되어야 한다" 피드백 — 동반 노트는 요약만이라 추후 재처리·재요약 시 raw 가 필요. MinerU sub-artifacts (layout.pdf·span.pdf·images/) 는 entrypoint.py 의 tempdir cleanup 에서 손실 → Phase 2 future work. 기존 5건 (한국원자력의학원 2 + 대한핵의학회 3) 노트북에서 백채움. 추가로 Obsidian 비교 편의용 docling.md / mineru.md (JSON의 markdown 필드 추출본) 도 `_parse/` 에 함께 저장.
- 2026-05-15 (오후) — **정제본 (refined.md) 도입**. Dr. Ben 의 "두 차이 보정한 최종 정제본도 저장하자" 피드백 — 가장 가치 있는 자료. §3 에 정제본 작성 단계 추가 (frontmatter: source_pdf·base_engine·corrections·generated·host + 본문 풀텍스트). §7 의 `_parse/` 내용에 `refined.md` 포함. 역할 분리 명확화 — 동반 노트 = 요약·관찰·연결, `refined.md` = 원본 충실 재현 풀텍스트.
- 작성자: Dr. Ben + Claude.
- 수정 시: §Spec·§Plan 변경은 PROGRESS.md 가 권위 — 본 SKILL.md 는 절차 정렬만.
