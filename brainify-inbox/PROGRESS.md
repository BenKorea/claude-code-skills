# brainify-inbox — PROGRESS

> spec-kit 의 4파일 (spec / plan / tasks / checklist) 을 한 파일에 압축한 mini SDD. webmail-watch 의 거버넌스 패턴을 차용. Claude Code 스킬의 첫 사례 — 패턴이 안정되면 `~/.claude/skills/` 용 별도 SKILL_CONTRACT 추출 검토.

## 세션 재개 패턴

Dr. Ben 이 "brainify-inbox 재개" 또는 "PDF 파싱 스킬 진행" 류 지시를 주면, 모델은 다음 절차를 따른다.

1. 이 파일 (`PROGRESS.md`) 을 읽음
2. **현재 PC 의 hostname 확인** — 데스크탑 `kimbi` (NVIDIA RTX 3060) 와 노트북 (Intel Arc 140T) 의 GPU 스택이 완전히 다름. 노트북에서 재개 시 **반드시 `LAPTOP-SETUP.md` 부터 Read** 해 차이·전략 인지.
3. **§Tasks** 의 첫 미완료 (`- [ ]`) 항목으로 이동
4. 그 항목의 **What / Done when** 만 보고 작업 시작 (그 위 항목은 이미 완료된 것으로 신뢰)
5. 작업 완료 후 **Done when** 충족 시 `[x]` 로 변경 + Notes 갱신 (발견 정보·결정사항 누적)
6. 다음 미완료 항목으로 자동 진행 ✗ — 한 항목 끝낼 때마다 Dr. Ben 보고 + 다음 항목 진행 여부 확인

체크리스트 항목 자체의 추가/삭제/분해는 Dr. Ben 승인 후만. 모델은 현재 진행 중인 항목의 **Done when** 정밀화 또는 **Notes** 누적만 자율 수행.

**관련 파일** (이 디렉토리):
- `SKILL.md` — 런타임 절차서 (`status: design-only`)
- `LAPTOP-SETUP.md` — 노트북 환경 셋업 가이드 (Intel Arc / CPU only 전략)
- 메모리: [[user-machines-spec]] (두 PC 의 GPU·RAM 비대칭)

---

## §Spec — 무엇을 만드는가

**Goal**: `sources/00_inbox/` 에 드롭된 PDF 들을 **Docling + MinerU 듀얼 파싱** 으로 구조화 (마크다운+JSON) 하고, 두 출력의 diff 를 Claude 가 시각 검증 (원본 페이지를 Read 도구로 직접 보고 정확한 쪽 선택) 한 뒤, PARA 분류·파일명 제안 → Dr. Ben 승인 → `sources/0X_.../` 정식 위치 이동 + `knowledge/` 동반 노트 생성까지 일괄 수행하는 **Claude Code 인터랙티브 스킬**.

**Why**:

- 회계보고서 (한글, 표 정밀·다단·종종 스캔) 와 의학논문 (영문 academic, 수식·표·그림 캡션) 양쪽을 처리해야 함.
- Read 도구 (Claude 멀티모달 PDF) 단독으론 회계 표의 정확한 수치 정렬 보장 어려움.
- 단일 오픈소스 엔진은 도메인별 약점 — Docling 은 학술논문 강세, MinerU 는 CJK·표 강세. 듀얼 + diff 검수가 단일보다 견고.
- 외부 API 사용 시 재무자료 leak 위험 → 두 엔진 모두 로컬 추론.

**Success criteria** (운영 정상의 정의):

1. `~/.claude/skills/brainify-inbox/` 안 SKILL.md 를 Claude Code 가 직접 읽고 트리거됨 ("/brainify-inbox" 또는 "인박스 브레인화" 류 자연어).
2. `sources/00_inbox/` 안 PDF N개에 대해 각각:
   - Docling 마크다운 1개 + MinerU 마크다운 1개 생성
   - 두 출력의 구조적 diff (heading·표 셀·문단 수·핵심 수치) 자동 산출
   - diff 가 임계값 초과 시 Claude 가 Read 도구로 원본 페이지 시각 검증 → 정확한 쪽 명시 선택 (사유 기록)
   - PARA 분류 + 표준 파일명 (`YYYY-MM-DD_출처_내용.ext` 또는 `저자_연도_주제.ext`) 제안
3. Dr. Ben 의 *1회 일괄 승인* 후:
   - 원본 PDF → `sources/0X_.../` 정식 위치 이동 (rename 포함)
   - 동반 노트 → `knowledge/0X_.../<같은이름>.md` 생성. CLAUDE.md 의 frontmatter 표준 (sources 상대경로) + 본문 첫 줄 `[원본 PDF](sources/...)` 링크 + 요약·내 생각·관련 노트 링크 슬롯 포함
   - `sources/00_inbox/` 비어짐
4. **외부 API 호출 0** — Docling·MinerU 모델 가중치는 로컬 캐시, 추론도 로컬 (네트워크 차단 상태에서도 작동).
5. 분류 전 vault 안 **중복/연결 검사** (CLAUDE.md §0 ) 자동 수행 — 관련 노트 발견 시 `[[wikilink]]` 제안에 포함.

**Out of scope** (Phase 1):

- 자동 분류·자동 이동 (모두 인터랙티브 — Dr. Ben 승인 필수)
- OpenClaw 알림 사이드잡 (Phase 2 별도)
- 스캔 PDF (텍스트 레이어 없는 이미지 PDF) — Phase 1 은 디지털 텍스트 PDF 우선. OCR 분기는 Phase 2.
- 한·영 외 언어 (Phase 1 은 ko/en 자료만)
- 비-PDF 자료 (xlsx·docx·이미지) — 별도 스킬 또는 후속 Phase
- 다중 PDF 의 자동 그룹핑 (예: 한 논문의 본문+supplementary 묶음)

---

## §Plan — 어떻게 만드는가 (확정·검토 사항)

| 결정 | 내용 | 상태 |
|---|---|---|
| 스킬 위치 | `~/.claude/skills/brainify-inbox/` (= `BenKorea/claude-code-skills` repo 새 디렉토리) | 확정 |
| 거버넌스 | mini SDD = 본 PROGRESS.md. 별도 spec doc·test 파일 ✗ | 확정 |
| L1 계약 | OpenClaw SKILL_CONTRACT 를 Claude Code 의미로 재해석해 SKILL.md 에 반영 (Q2=(a)) | 확정 |
| 파싱 엔진 | **Docling + MinerU 듀얼**. 둘 다 오픈소스·로컬 추론 | 확정 |
| 외부 API | **금지**. 재무자료 leak 방지 | 확정 |
| 공유 라이브러리 위치 | **`~/projects/2nd-brain-docker/` 안 모듈** (Dr. Ben 결정 2026-05-13, P1.1=b). 도커 실행환경과 한 저장소. Claude Code 본 스킬 + 미래 OpenClaw 스킬 양쪽이 컨테이너 entrypoint 로 호출 | 확정 |
| 실행 환경 | **Docker 컨테이너** (Dr. Ben 결정 2026-05-13, P1.2). 2nd-brain-docker 안 신규 `brain-pdf` 서비스 (`images/brain-pdf/Dockerfile` + `compose.brain-pdf.yml` 오버레이). PyTorch·CUDA 호스트 오염 회피, 격리·재현 강함. compose.gog.yml 의 opt-in 오버레이 패턴 일치 | 확정 |
| 모델 캐시 위치 | Docker named volume `brain-pdf-models:/home/user/.cache/huggingface`. SyncThing 동기 대상 ✗ (PC 별 독립, 첫 실행에서 1회 다운로드) | 확정 (P1.3 에서 compose 정의 완료) |
| 실행 모드 (데몬 vs ephemeral) | **Phase 1 기본 = ephemeral `docker compose run --rm`**. opt-in 데몬 모드도 동시 지원 (`make up-brain-pdf`). Dr. Ben 노트북 kimbi WSL2 14 GB + sb-claude (NODE 4 GB heap) 합산 메모리 압박 회피. 권고 #1 (데몬) 에서 수정 — 14 GB 정보 받은 후 재평가 (2026-05-13) | 확정 |
| 단일 vs 분리 컨테이너 | **단일 `brain-pdf`** — Docling + MinerU 같은 이미지. 의존성 충돌 시 분리로 후퇴 | 확정 |
| 베이스 이미지 | `python:3.12-slim` + PyTorch CPU wheel 별도 설치 (`--index-url https://download.pytorch.org/whl/cpu`). pytorch official 이미지 ~7 GB 회피 | 확정 |
| GPU 지원 | **Phase 1 = CPU only** (WSL2 GPU passthrough 제한 + Windows 측 GPU 는 qwen2.5-14B-q4 점유). 운영 후 재검토 | 확정 |
| Entrypoint CLI | Python argparse `brain-pdf parse-docling <pdf>` / `parse-mineru <pdf>` / `diff <a> <b>` → stdout JSON | 확정 (P1.3 stub 작성, P1.4·P1.5·P2.x 에서 실제 로직) |
| Makefile 타겟 | `build-brain-pdf` / `up-brain-pdf` / `down-brain-pdf` / `shell-brain-pdf` / `run-brain-pdf ARGS="..."` | 확정 (P1.3 완료) |
| 이미지 태깅 | `2nd-brain/brain-pdf:${BRAIN_PDF_VERSION}` 핀. `.env` 의 `BRAIN_PDF_VERSION` 으로 관리 (예: 날짜 `2026.05.13`). `latest` 금지 — 기존 claude-cli 패턴 일치 | 확정 |
| 네트워킹 | 기본 default network (첫 실행 모델 다운로드). offline 검증 시 `--network none` 옵션 또는 compose env `TRANSFORMERS_OFFLINE=1` toggle | 확정 |
| Diff 전략 | 두 마크다운의 구조적 비교 — heading 트리 / 표 셀 수치 / 문단 수 / 영역별 토큰 수. 임계값 (TBD — P2.3 에서 정함) 초과 시 시각 검증 강제 | **P2.3 에서 정밀화** |
| 시각 검증 | Claude Code 의 Read 도구 (PDF 페이지 단위 멀티모달 해석). 검증 후 *어느 엔진 출력을 채택했는지* + *왜* 를 동반 노트에 기록 | 확정 |
| 분류 제안 | Claude 가 파싱 결과 (제목·발신자·날짜·표 키워드) + 파일명 hint + 기존 vault 검색 결과를 종합해 PARA 폴더 + 표준 파일명 제안 | 확정 |
| 승인 패턴 | CLAUDE.md "첫 1~2개 패턴 확인 후 일괄". 같은 출처·유사 형식은 패턴 승인 후 일괄 처리. 새 출처·이질적 자료는 개별 승인 | 확정 |
| 동반 노트 표준 | CLAUDE.md 의 frontmatter (sources 상대경로) + 본문 첫 줄 `[원본 PDF](sources/...)` + 요약·내 생각·관련 노트 링크 | 확정 |
| 영속 상태 | (필요 시) `~/.claude/skills/brainify-inbox/state/processed.jsonl` — 처리 이력 (SHA·원본 경로·정착 경로·diff 채택 사유). git 미추적 | **P3.4 에서 결정** |
| 자격증명 | 없음 (외부 API 미사용) | 확정 |
| 호출 형식 | Claude Code 가 SKILL.md 를 직접 로드. Dr. Ben 이 자연어로 트리거 ("/brainify-inbox" 또는 "인박스 브레인화") → Claude 가 SKILL.md 절차 수행 | 확정 |
| 수동 테스트 | 공유 라이브러리는 CLI 로 단독 호출 가능해야 함 — `python3 -m brain_pdf_pipeline.parse <pdf>` → stdout 에 두 엔진 결과 + diff 보고. Claude 매개 없이 검증 가능 | 확정 |
| OpenClaw 승격 경로 | Phase 1 안정 후 Phase 2 에서 `~/.openclaw/workspace/skills/inbox-watch/` 신설. 동일 공유 라이브러리 호출. 자동 분류는 정형 케이스 (영수증 등) 만 점진 도입 | 확정 (방향만) |

---

## §Tasks — 체크리스트

각 항목: **What** (작업) · **Owner** (담당) · **Depends on** (선행) · **Done when** (검증) · **Notes** (발견·결정 누적).

### Phase 0 — 설계 (진행 중)

- [x] **P0.1 PROGRESS.md 초안** · Owner: model · Done when: §Spec·§Plan·§Tasks·§Checklist 골격 완성 + Dr. Ben 검토 회부 · Notes: 본 파일.
- [x] **P0.2 SKILL.md 초안 (OpenClaw SKILL_CONTRACT 재해석)** · Owner: model · Depends on: P0.1 · Done when: frontmatter + 호출 패턴 + 절차 + 예외 선언 명시 · Notes: 2026-05-13 작성. `status: design-only` 명시 (구현 완료 전 호출 차단). 예외 선언 2개: L1 §3 (stdout 규칙) — Claude 인터랙티브 절차라 침묵 규칙 미적용, 결정성은 컨테이너 entrypoint 측 코드가 보장. L1 §6 (영속 상태 위치) — `~/.claude/skills/brainify-inbox/state/` 로 재해석. Acceptance examples 4건 + Manual test commands 명시.
- [x] **P0.3 Dr. Ben 의 §Spec·§Plan 검토** · Owner: Dr. Ben · Depends on: P0.1, P0.2 · Done when: TBD 항목 결정 + Out of scope 합의 · Notes: 2026-05-13 "그대로 OK" 승인. Success criteria 5개·Out of scope 5개·호출 형식·Phase 5 시점 모두 검토 통과. Phase 0 마감.

### Phase 1 — 인프라 결정·셋업

- [x] **P1.1 공유 라이브러리 위치 확정** · Owner: Dr. Ben · Done when: 위치 결정. Notes: **2026-05-13 결정 — `~/projects/2nd-brain-docker/` 안 모듈** (Q1.1=b). `repos.md` 인벤토리는 기존 `2nd-brain-docker` 항목만 유지 (새 repo 추가 ✗). 모듈 디렉토리명·위치는 P1.2 의 stack 구조 결정 시 정밀화.
- [x] **P1.2 실행 환경 확정 (uv vs Docker)** · Owner: Dr. Ben · Done when: 실행 환경 결정. Notes: **2026-05-13 결정 — Docker 컨테이너**. 2nd-brain-docker 안 신규 stack (예: `brain-pdf/` 서비스). 후속 작업: (a) stack 위치·서비스명·이미지 베이스 정의, (b) vault 마운트 (sources·knowledge RW) + 모델 캐시 마운트, (c) UID 매핑 (`${UID}:${GID}`), (d) entrypoint CLI 형식 (`docker compose run brain-pdf parse <pdf>` 또는 단일 컨테이너 명령).
- [x] **P1.3 2nd-brain-docker stack 추가 — brain-pdf 서비스 정의** · Owner: model + Dr. Ben · Depends on: P1.2 · Done when: 새 서비스 추가됨 + `make build-brain-pdf-gpu` 통과 + 컨테이너에서 GPU 인식. Notes:
  - **2026-05-13 완료**. 총 7개 파일 신규/편집:
    - `images/brain-pdf/Dockerfile` (신규, 최종 cu126 wheel + 단일 pip install)
    - `images/brain-pdf/entrypoint.py` (신규, NotImplementedError stub — P1.4/P1.5/P2.x 에서 구현)
    - `images/brain-pdf/requirements.txt` (신규, `docling` + `mineru` unpinned)
    - `compose.brain-pdf.yml` (신규, base 오버레이)
    - `compose.brain-pdf.gpu.yml` (신규, GPU 액세스 옵션 — 데스크탑 kimbi 전용)
    - `Makefile` (편집, 8개 타겟: build/up/down/shell/run + gpu variants)
    - `.env.example` (편집, `BRAIN_PDF_VERSION` 항목)
  - **GPU 통합 (예상보다 한 단계 더)**: WSL2 의 RTX 3060 을 컨테이너에서 사용 가능하게 만들기 위해 nvidia-container-toolkit 설치 (Dr. Ben 직접 sudo 실행) + Docker daemon 의 nvidia runtime 등록 (`nvidia-ctk runtime configure`). 검증: `docker run --gpus all nvidia/cuda:12.0.0-base nvidia-smi` ✅, brain-pdf 컨테이너 안 nvidia-smi ✅, torch.cuda.is_available()=True ✅, GPU matmul 실연산 통과.
  - **빌드 정정 1회**: 초기 빌드 (2026.05.13 태그) 가 cu130 wheel 받아 driver 12.6 과 불일치 → CUDA available False. Dockerfile 의 `pip install` 인덱스를 `cu126` 으로 변경 + 단일 install 로 consolidate 후 재빌드 (2026.05.13.cu126 태그) — 통과. broken 이미지 디스크 정리됨.
  - **최종 이미지**: `2nd-brain/brain-pdf:2026.05.13.cu126`, 12.3 GB. torch 2.12.0+cu126, docling 2.93.0, mineru 3.1.12.
  - **메모리 학습**: kimbi 는 데스크탑 (이전 메모리 잘못 — `user_machines_spec.md` 로 정정). 데스크탑·노트북 비대칭 인지.
- [x] **P1.4 Docling 설치 + 모델 1회 다운로드 + offline 작동 확인** · Owner: model · Depends on: P1.3 · Done when: 컨테이너 안에서 `docling sample.pdf` 통과 + 모델 캐시 영속 + 네트워크 차단 상태 작동. Notes:
  - **2026-05-13 완료**. 회계 자료 (`한국원자력의학원_수입지출+현황.pdf`) 로 검증.
  - **첫 실행** 57초 (HF 모델 ~500 MB 다운로드 + GPU 모델 로드 + 파싱). **두 번째 실행** 10초 — 5.7× 가속 (캐시 hit 증명).
  - **`--network none` 엄밀 검증**: 9.4초, 출력 bit-identical (83 lines, 10080 bytes), curl=000 (네트워크 진짜 차단됨). True offline 확인.
  - 모델 캐시: `2nd-brain-docker_brain-pdf-models` Docker named volume, 506 MB. 마운트 경로 `/home/user/.cache/huggingface/`. 재빌드 시에도 영속.
  - **빌드 정정 1회** (P1.4 도중 발견): docling 의 OCR 엔진 RapidOCR 이 site-packages 안에 모델을 쓰려다 PermissionError → Dockerfile 의 build 시점 (root) 에 `python3 -c "from rapidocr import RapidOCR; RapidOCR()"` 실행해 모델 사전 다운로드. 이미지 태그 `cu126` → `cu126.b` 로 bump.
  - **출력 품질**: 한국어 회계 표 — 6년 × 항목별 컬럼 정렬, 빈 셀 (`-`) 정확, 천 단위 콤마 보존 (54,250 / 56,655 등), 메타정보 (담당자·전화번호) 표로 인식. Docling 단독으로도 회계 자료 파싱 품질 매우 우수.
  - **다음**: P1.5 MinerU 동일 검증.
- [ ] **P1.5 MinerU 설치 + 모델 1회 다운로드 + offline 작동 확인** · Owner: model · Depends on: P1.3 · Done when: 동일 샘플 PDF 가 MinerU 결과로 산출. 네트워크 차단 검증 통과.

### Phase 2 — 파싱 핵심

- [ ] **P2.1 Docling CLI 래퍼** (`parse_docling.py`) · Owner: model · Depends on: P1.4 · Done when: `docker compose run brain-pdf parse-docling <pdf>` → stdout JSON `{markdown, doctags, json_structure, pages, runtime_sec}`. 컨테이너 안 모듈로 호출 가능.
- [ ] **P2.2 MinerU CLI 래퍼** (`parse_mineru.py`) · Owner: model · Depends on: P1.5 · Done when: 동일 형식 JSON 출력. `docker compose run brain-pdf parse-mineru <pdf>` 통과.
- [ ] **P2.3 Diff 모듈** (`diff_outputs.py`) · Owner: model · Depends on: P2.1, P2.2 · Done when: 두 마크다운 입력 → 구조적 diff 보고서 (heading 트리 비교, 표 셀 수치 diff, 문단 수 차이, 영역별 분기 — *어떤 페이지에서 두 엔진이 갈라졌는지* 명시). 임계값 정의 (예: heading 트리 동일성·표 셀 수치 일치율 ≥ 95% 이면 일치 판단).

### Phase 3 — 분류·승인 흐름 (Claude 측 절차)

- [ ] **P3.1 inbox 스캔 + 듀얼 파싱 호출 + diff 산출** · Owner: model · Depends on: P2.3 · Done when: SKILL.md 절차에 따라 Claude 가 `00_inbox` 의 PDF 목록 → 각 파일에 두 엔진 호출 → diff 보고서 수집.
- [ ] **P3.2 차이 발생 페이지 시각 검증** · Owner: model · Depends on: P3.1 · Done when: diff 임계값 초과 페이지에 대해 Claude 가 Read 도구로 해당 페이지 시각 해석 → 두 엔진 중 정확한 쪽 선택 + 사유 1줄 기록.
- [ ] **P3.3 PARA 분류·파일명 제안** · Owner: model · Depends on: P3.2 · Done when: 각 PDF 에 대해 (1) 정착 PARA 폴더, (2) 표준 파일명, (3) 동반 노트 본문 초안, (4) `[[wikilink]]` 후보 목록 제안. CLAUDE.md §0 중복/연결 검사 통합.
- [ ] **P3.4 Dr. Ben 승인 → 이동·노트 생성** · Owner: model · Depends on: P3.3 · Done when: 승인 후 (1) `sources/00_inbox/<원파일>` → `sources/0X_.../<새이름>` 이동, (2) `knowledge/0X_.../<새이름>.md` 생성, (3) `00_inbox` 비어짐 확인. 영속 이력 기록 여부 결정.

### Phase 4 — 실자료 검증

- [ ] **P4.1 회계보고서 1건 처리** (한글, 표) · Done when: 표 수치 동반 노트에 정확히 반영. 두 엔진 중 채택 사유 기록.
- [ ] **P4.2 의학논문 1건 처리** (영문 academic) · Done when: Abstract·표·그림 캡션 동반 노트에 구조 보존. 수식 누락 여부 보고.
- [ ] **P4.3 영수증/명세서 1건 처리** (간단 양식) · Done when: 1회 호출에 분류·이동·노트 일괄 통과 (latency 기록).

### Phase 5 — 운영·승격

- [ ] **P5.1 실 inbox 1주 운영** · Owner: Dr. Ben · Done when: 1주간 자연 발생 PDF 들을 본 스킬로 처리 + 실패·이상 케이스 누적.
- [ ] **P5.2 OpenClaw 사이드잡 검토** · Owner: Dr. Ben + model · Depends on: P5.1 · Done when: `inbox-watch` (cron 알림 only) 또는 `inbox-autotriage` (정형 케이스 자동 분류) 의 도입 여부·범위 결정.

---

## §Checklist — 운영 사이클 검증

`/brainify-inbox` 호출 1회의 sanity check.

- [ ] `00_inbox` 0건 회차에서 "처리할 PDF 없음" 명시 후 종료 (오작동 ✗)
- [ ] PDF binary 손상 시 graceful 보고 + 다른 PDF 처리 계속
- [ ] Docling·MinerU 둘 다 실패 시 fallback 메시지 (Read 도구만으로 분류 제안)
- [ ] 두 엔진 결과 일치 (diff 임계값 이내) 시 시각 검증 단계 생략 (latency·context 절약)
- [ ] 차이 시 Claude 가 *어느 엔진 출력을 채택했는지* + *왜* 를 동반 노트 본문에 1줄 기록
- [ ] 분류 제안 시 vault 중복 검사 결과 함께 제시 ("이거 이미 [[Kim_2024]] 와 유사 — 별도 노트 vs 통합?" 류)
- [ ] 승인 전 변경 없음 (rollback 가능 상태 유지)
- [ ] 이동 후 `sources/00_inbox/` 비어짐 + 정착 파일 권한 정상
- [ ] 동반 노트 frontmatter: `sources:` 상대경로 / `date` 오늘 / `tags` 추출 / 본문 첫 줄 `[원본 PDF](sources/...)`
- [ ] 외부 네트워크 호출 0 (`tcpdump` 또는 firewall 로 확인 가능해야 함)
- [ ] 처리 후 동일 PDF 재드롭 시 중복 감지 (SHA 비교) — 이미 있음을 Dr. Ben 에게 보고하고 처리 skip

---

## 메타

- 2026-05-13 — 최초 작성. webmail-watch/PROGRESS.md 의 spec-kit 압축 거버넌스를 Claude Code 스킬에 첫 적용. Dr. Ben 결정 Q1=YES (mini SDD 채택) + Q2=(a) (OpenClaw SKILL_CONTRACT 재해석으로 적용) 직후.
- 작성자: Dr. Ben + Claude.
- 수정 시: §Spec·§Plan 변경은 Dr. Ben 승인 후. §Tasks 항목 추가/삭제도 동일. 모델은 진행 중 항목의 Done when 정밀화·Notes 누적만 자율.
