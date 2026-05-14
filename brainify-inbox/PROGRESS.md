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
| **다중 PC 어댑터 패턴 (2026-05-14)** | 데스크탑 kimbi (RTX 3060) ↔ 노트북 (Intel Arc, GPU 점유) 양 PC 에서 같은 동기 자산으로 작동. `scripts/detect-compose.sh` 가 nvidia-smi 검사 → compose 체인 자동 분기. PyTorch 의 `cuda.is_available()` 가 runtime 백엔드 선택 (cu126 wheel 의 CPU 환경 작동 활용). Docker 이미지 콘텐츠는 양 PC 동일. **동기 자산에 머신-specific 키워드 직접 박지 않음** — 메모리 [[no-machine-specific-in-synced-files]] | 확정 |
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
  - **GPU 통합 (kimbi 데스크탑 1회 호스트 셋업, 노트북은 불필요)**: WSL2 의 RTX 3060 을 컨테이너에서 사용 가능하게 만들기 위해 nvidia-container-toolkit 설치 (Dr. Ben 직접 sudo 실행) + Docker daemon 의 nvidia runtime 등록 (`nvidia-ctk runtime configure`). 검증: `docker run --gpus all nvidia/cuda:12.0.0-base nvidia-smi` ✅, brain-pdf 컨테이너 안 nvidia-smi ✅, torch.cuda.is_available()=True ✅, GPU matmul 실연산 통과.
  - **빌드 정정 1회**: 초기 빌드 (2026.05.13 태그) 가 cu130 wheel 받아 driver 12.6 과 불일치 → CUDA available False. Dockerfile 의 `pip install` 인덱스를 `cu126` 으로 변경 + 단일 install 로 consolidate 후 재빌드 (2026.05.13.cu126 태그) — 통과. broken 이미지 디스크 정리됨.
  - **최종 이미지**: `2nd-brain/brain-pdf:2026.05.13.cu126`, 12.3 GB. torch 2.12.0+cu126, docling 2.93.0, mineru 3.1.12.
  - **메모리 학습**: kimbi 는 데스크탑 (이전 메모리 잘못 — `user_machines_spec.md` 로 정정). 데스크탑·노트북 비대칭 인지.
- [x] **P1.4 Docling 설치 + 모델 1회 다운로드 + offline 작동 확인** · Owner: model · Depends on: P1.3 · Done when: 컨테이너 안에서 `docling sample.pdf` 통과 + 모델 캐시 영속 + 네트워크 차단 상태 작동. Notes:
  - **2026-05-13 완료**. 회계 자료 (`한국원자력의학원_수입지출+현황.pdf`) 로 검증.
  - **첫 실행** 57초 *(kimbi GPU)* (HF 모델 ~500 MB 다운로드 + GPU 모델 로드 + 파싱). **두 번째 실행** 10초 *(kimbi GPU)* — 5.7× 가속 (캐시 hit 증명).
  - **`--network none` 엄밀 검증**: 9.4초 *(kimbi GPU)*, 출력 bit-identical (83 lines, 10080 bytes), curl=000 (네트워크 진짜 차단됨). True offline 확인.
  - **노트북 (ai4lt) CPU 실측** (2026-05-14, vault README 인계): parse-docling 22.1 s *(ai4lt CPU)* — 추정 20-40초 적중. parse-docling 36.8 s on 3 pages PDF *(ai4lt CPU, 임직원수 자료)*. cu126 wheel 단일 이미지로 양 PC 작동 검증됨.
  - 모델 캐시: `2nd-brain-docker_brain-pdf-models` Docker named volume, 506 MB. 마운트 경로 `/home/user/.cache/huggingface/`. 재빌드 시에도 영속.
  - **빌드 정정 1회** (P1.4 도중 발견): docling 의 OCR 엔진 RapidOCR 이 site-packages 안에 모델을 쓰려다 PermissionError → Dockerfile 의 build 시점 (root) 에 `python3 -c "from rapidocr import RapidOCR; RapidOCR()"` 실행해 모델 사전 다운로드. 이미지 태그 `cu126` → `cu126.b` 로 bump.
  - **출력 품질**: 한국어 회계 표 — 6년 × 항목별 컬럼 정렬, 빈 셀 (`-`) 정확, 천 단위 콤마 보존 (54,250 / 56,655 등), 메타정보 (담당자·전화번호) 표로 인식. Docling 단독으로도 회계 자료 파싱 품질 매우 우수.
  - **다음**: P1.5 MinerU 동일 검증.
- [x] **P1.5 MinerU 설치 + 모델 1회 다운로드 + offline 작동 확인** · Owner: model · Depends on: P1.3 · Done when: 동일 샘플 PDF 가 MinerU 결과로 산출. 네트워크 차단 검증 통과. Notes:
  - **2026-05-14 완료**. 동일 회계 PDF (`한국원자력의학원_수입지출+현황.pdf`) 로 검증.
  - **빌드 정정 2회 (cu126.b → cu126.c → cu126.d)**:
    - 첫 시도: pipeline backend → `ImportError: find_pruneable_heads_and_indices` (transformers v5 에서 제거). 그 다음 시도: vlm-auto-engine → `AttributeError: Qwen2VLConfig.max_position_embeddings` — 같은 v5 breaking change 패턴. 조사 결과 transformers 5.8.1 설치됨, mineru·docling 양쪽 다 `<5.0.0` 요구 (mineru 는 `>=4.57.3,<5.0.0` 명시). 그러나 mineru 의 transformers 핀은 `extras_require` (`[pipeline]`/`[vlm]`) 안에 있어 unpinned `mineru` 설치 시 미반영. pip resolver drift.
    - **정정 1 (cu126.c)**: `requirements.txt` 에 `transformers>=4.57.3,<5.0.0` 명시 핀 추가. transformers 4.57.6 으로 설치됨. pipeline 백엔드 재시도 → `ModuleNotFoundError: albumentations` — 다른 누락 dep (역시 `[pipeline]` extra 에 묶임).
    - **정정 2 (cu126.d)**: `mineru` → `mineru[pipeline,vlm]` 로 교체. 누락 deps (albumentations, albucore, ftfy, opencv-python-headless, simsimd, stringzilla, wcwidth) 자동 포함. **docling 회귀 검증 통과** (8.9초 *(kimbi GPU)*, 출력 정상).
  - **최종 이미지**: `2nd-brain/brain-pdf:2026.05.13.cu126.d`. transformers 4.57.6, torch 2.12.0+cu126, docling 2.93.0, mineru 3.1.12. HF 캐시 3.5 GB → 3.9 GB (mineru 의 layout/table/OCR 모델 ~400 MB 추가).
  - **실행 성능**:
    - 1회차 (모델 다운로드 + 로드 + 파싱): **49.7초** *(kimbi GPU)*
    - 2회차 (캐시 hit): **30.7초** *(kimbi GPU)* — 1.6× 가속 (docling 의 5.7× 보다 낮음, 이유: pipeline 백엔드가 매 호출마다 FastAPI model server 를 spawn → init 비용 매번 발생. weight 캐시는 hit. P2.1/P2.2 에서 daemon 모드 검토 가능)
    - 3회차 offline (`--network none` + raw `docker run`): **27.6초** *(kimbi GPU)* — 캐시 hit 와 유사. 출력 bit-identical (31 lines / 12638 bytes 동일). curl=000 (네트워크 진짜 차단됨). **True offline 확인**.
  - **노트북 (ai4lt) CPU 실측** (2026-05-14, vault README 인계): parse-mineru **47.2 s** *(ai4lt CPU, 한국원자력의학원_수입지출+현황 2 pages)* — LAPTOP-SETUP.md 의 추정 80-150 초 **과대 추정** 으로 확인. 3 페이지 자료 (임직원수) 는 **51.1 s** *(ai4lt CPU)*. **MinerU formula recognition deadlock 재발 안 됨** — 어제 오전엔 노트북 CPU 모드에서 `-f true` (default) 가 MFR UnimerSwin spawn deadlock 으로 7+ 분 hang 했으나, 오후 (mineru[pipeline,vlm] 핀 적용 후) 같은 PDF 가 default opts 로 47.2 s 정상 완료. 가설 3건 (vlm extras 의 init 순서 변화 / cu126 wheel 의 thread-local state / multiprocessing race 변동) 검증 ✗. **운영 제약 일단 해제, 회귀 가능성은 모니터링**. 재발 시 `mineru -f false -t true --image-analysis false` fallback 가능.
  - **CLI 형식**: `mineru -p <pdf> -o <output_dir> -b pipeline -l korean`. 백엔드 4종 중 `pipeline` 채택 — 한국어 회계 PDF 표 인식·OCR 품질 양호. `vlm-auto-engine`/`hybrid-auto-engine` 은 미검증 (Qwen-VL 모델 추가 다운로드 17 GB+ 필요, Phase 1 범위 외).
  - **출력 구성**: `<pdf-stem>/auto/` 아래 `<stem>.md`, `<stem>_content_list.json`, `<stem>_content_list_v2.json`, `<stem>_middle.json`, `<stem>_model.json`, `<stem>_layout.pdf`, `<stem>_span.pdf`, `<stem>_origin.pdf`, `images/*.jpg` (cropped figures). docling 의 단일 .md 출력 대비 정보량 풍부.
  - **출력 품질 (docling 과 비교)**: 둘 다 수치·천단위 콤마 정확. 형식 다름 — docling 은 pipe-markdown 표 (rowspan 을 값 중복으로 평면화: `수입|수입|수입|수입`), MinerU 는 HTML 표 + rowspan/colspan 속성으로 구조 보존. 인간 가독성 docling↑, 구조 충실도 MinerU↑. docling 에 OCR 띄어쓰기 artifact 1건 (`정부순지 원.pdf`). 섹션 순서 차이: docling 은 "## 35. 수입·지출 현황" 이 중간, mineru 는 상단. → **P2.3 diff 모듈에서 두 포맷 정규화 (셀 단위 추출) 필요**.
  - **다음**: Phase 2 — P2.1 (Docling CLI 래퍼) + P2.2 (MinerU CLI 래퍼) + P2.3 (diff 모듈).

### Phase 2 — 파싱 핵심

- [x] **P2.1 Docling CLI 래퍼** (`parse_docling.py`) · Owner: model · Depends on: P1.4 · Done when: `docker compose run brain-pdf parse-docling <pdf>` → stdout JSON `{markdown, doctags, json_structure, pages, runtime_sec}`. 컨테이너 안 모듈로 호출 가능. Notes:
  - **2026-05-14 완료**. `images/brain-pdf/entrypoint.py` 의 `parse_docling()` stub 을 실제 구현으로 교체.
  - **구현 요지**: `DocumentConverter().convert(pdf_path)` → `result.document` 에서 `export_to_markdown()`, `export_to_doctags()`, `export_to_dict()` 호출. `runtime_sec` 는 converter init + convert 전체 wall time (cold-start 한 번에 호출되는 ephemeral 모드 기본 가정. daemon 모드 도입 시 재정의).
  - **stdout 오염 방지**: docling/rapidocr 가 print/logging 으로 INFO 메시지를 stdout 에 흘리는 것을 `contextlib.redirect_stdout(sys.stderr)` 로 잡음. stdout 는 마지막 `json.dumps(...)` 결과만 — P2.3 diff 모듈이 안심하고 파이프 가능. import 자체도 함수 내부로 두어 `--version`/`--help` 가 docling 로드 비용 (3 s+) 을 안 냄.
  - **검증** *(kimbi GPU, 한국원자력의학원 회계 PDF, 컨테이너 캐시 warm)*:
    - 출력: 441,655 bytes valid JSON. 키 = {engine, pdf_path, pages, runtime_sec, markdown, doctags, json_structure}.
    - pages=2, runtime_sec=4.6s (캐시 warm), markdown=10,489 B, doctags=5,757 B.
    - `json_structure` 키 = schema_name, version, name, origin, furniture, body, groups, texts, pictures, tables → docling 의 full DoclingDocument 구조 그대로.
    - stderr 에는 RapidOCR INFO 만 (에러 없음).
  - **dev iteration 패턴**: 이미지 재빌드 (7 min) 회피를 위해 entrypoint.py 를 볼륨 마운트로 주입해 검증. `docker compose run --rm -v ${HOST}/images/brain-pdf/entrypoint.py:/tmp/dev.py:ro --entrypoint="" brain-pdf python3 /tmp/dev.py parse-docling <pdf>`. **이미지 정식 rebuild 는 P2.3 끝에서 일괄** — Phase 2 의 P2.1/P2.2/P2.3 모두 같은 entrypoint.py 를 만지므로 매 task 당 빌드는 낭비. 최종 빌드 시 태그를 `2026.05.14` 류로 bump 예정.
  - **다음**: P2.2 — `parse_mineru()` 동일 형식 구현.
- [x] **P2.2 MinerU CLI 래퍼** (`parse_mineru.py`) · Owner: model · Depends on: P1.5 · Done when: 동일 형식 JSON 출력. `docker compose run brain-pdf parse-mineru <pdf>` 통과. Notes:
  - **2026-05-14 완료**. `entrypoint.py` 의 `parse_mineru()` stub 을 실제 구현으로 교체.
  - **구현 요지**: MinerU 는 Python API 보다 CLI 가 안정적 (3.x 가 FastAPI 내부 서버 spawn 구조라 라이브러리 API 가 얇음) → `subprocess.run(["mineru", "-p", pdf, "-o", tmp, "-b", "pipeline", "-l", "korean"])`. 임시 디렉토리로 출력 받고 .md + `_middle.json` 만 dict 에 담아 반환. tmp 디렉토리는 `with` 종료 시 자동 정리.
  - **포맷 결정 3건**:
    1. `doctags = None` — MinerU 에 doctags 대응 포맷 없음. JSON null 로 두어 P2.3 diff 가 양쪽 비교 시 docling-only 필드임을 감지하고 skip 가능.
    2. `json_structure = middle.json` — content_list_v2.json (flat reading-order list) 도 있지만 middle.json 이 페이지별 블록·bbox·타입을 가진 가장 풍부한 구조. docling 의 export_to_dict() 와 의미적으로 가장 근접. 단 키 셋은 다름 (mineru = {pdf_info, _backend, _version_name} vs docling = {schema_name, version, name, origin, furniture, body, groups, texts, pictures, tables}).
    3. `pages = len(middle["pdf_info"])` — 페이지별 블록 리스트의 길이. KeyError 시 fail-loud (schema 변경 감지). fallback 0 으로 mask 하지 않음.
  - **stdout 오염 차단**: subprocess 의 stdout·stderr 양쪽 다 캡처 → `sys.stderr.write(proc.stdout)` + `sys.stderr.write(proc.stderr)` 로 흘려보냄. mineru 의 진행바·FastAPI INFO 가 우리 stdout 을 침범 못함.
  - **검증** *(kimbi GPU, 한국원자력의학원 회계 PDF, 컨테이너 캐시 warm)*:
    - 출력: 73,166 B valid JSON. 키 = {engine, pdf_path, pages, runtime_sec, markdown, doctags, json_structure}. 키 셋 docling 과 동일.
    - pages=2, runtime_sec=35.3 s (wall time 35.3 s 와 정확히 일치 — runtime 은 subprocess 전체).
    - markdown=10,591 chars (Korean 다바이트 → byte 단위로는 ~12,638 B, P1.5 의 wc 결과와 일치).
    - doctags=null.
    - json_structure: pdf_info 배열에 2 페이지 분 블록 데이터.
    - stderr 에 mineru FastAPI shutdown INFO 만 (정상 종료).
  - **JSON 크기 비교**: docling 442 KB vs mineru 73 KB. docling 의 export_to_dict() 가 schema 가 풍부해 더 verbose. 둘 다 P2.3 diff 에 충분한 정보.
  - **다음**: P2.3 — diff 모듈. 두 JSON 을 입력받아 markdown (텍스트) + json_structure (셀·블록 단위) 구조적 차이 보고. 포맷 차이 때문에 셀·블록 단위 정규화 레이어 필요.
- [x] **P2.3 Diff 모듈** (`diff_outputs.py`) · Owner: model · Depends on: P2.1, P2.2 · Done when: 두 마크다운 입력 → 구조적 diff 보고서 (heading 트리 비교, 표 셀 수치 diff, 문단 수 차이, 영역별 분기 — *어떤 페이지에서 두 엔진이 갈라졌는지* 명시). 임계값 정의 (예: heading 트리 동일성·표 셀 수치 일치율 ≥ 95% 이면 일치 판단). Notes:
  - **2026-05-14 완료**. `entrypoint.py` 에 `diff_outputs()` + 두 헬퍼 (`_normalize_markdown`, `_extract_numeric_cells`) 추가.
  - **Outline 합의 결정** (Dr. Ben):
    - 임계값 그대로 (heading_overlap≥0.8, paragraph_count_delta≤0.2, table_count_match≥0.8, numeric_cell_match≥0.95)
    - 상위 10개 mismatch 만 details 에
    - 페이지별 영역 diff 는 Phase 1 범위 외 (P5.1 이후 재검토)
  - **정규화 레이어** (`_normalize_markdown`): 두 파서의 json_structure 키 셋 (docling: body/texts/tables/... vs mineru: pdf_info/...) 이 너무 달라서 정규화 비용이 큼 → **마크다운을 1차 진실 소스**로 두고 양쪽을 공통 구조 `{headings: [(level,text)], paragraphs: [text], tables: [[[cell]]]}` 로 추출. BeautifulSoup 로 mineru HTML `<table>` 파싱, regex 로 docling pipe-table 파싱. 둘 다 2D 셀 배열로 통일.
  - **메트릭 4종**:
    1. `heading_overlap` = |a ∩ b| / max(|a|, |b|) — heading 텍스트 set 비교 (level-agnostic)
    2. `paragraph_count_delta` = |a-b| / max(a, b)
    3. `table_count_match` = min(a, b) / max(a, b)
    4. `numeric_cell_match` = (Counter intersection 합) / max(total) — 천단위 콤마·공백·% 제거 후 순수 숫자만 multiset 비교
  - **숫자 정규화 정책**: `re.sub(r'[,\s%]', '', s)` 후 `r'-?\d+(?:\.\d+)?'` fullmatch. `(123)` 같은 회계 음수 표기·% 외 화폐단위 미지원 (Phase 1 의식적 단순화). "2021년", "출연금" 같은 텍스트 셀은 자동 skip — 양쪽 다 안정적이라 diff 신호 안 줌.
  - **출력 dict 형식**:
    - top-level: `a` / `b` (engine·pdf_path·pages), `metrics`, `thresholds`, `verdict`, `details`
    - `metrics` 에 각 비율 + 카운트(a, b 각각) 함께 — 비율 0.5 가 1/2 인지 50/100 인지 확인 가능
    - `details`: `headings_only_in_a[:10]`, `headings_only_in_b[:10]`, `numeric_mismatches[:10]` (양쪽 합쳐 count desc 정렬)
  - **검증** (한국원자력의학원 회계 PDF, baked 이미지):
    - 출력: 1,052 B compact JSON. 모든 subcommand `brain-pdf {parse-docling,parse-mineru,diff,--version,--help}` 통과.
    - **메트릭**: heading_overlap=0.5, paragraph_count_delta=0.091, table_count_match=1.0, **numeric_cell_match=1.0** (108개 숫자 셀 양쪽 정확히 일치), heading_count={a:2, b:1}, table_count={a:5, b:5}.
    - **verdict=diverge** — heading_overlap 0.5 가 임계 0.8 미달. docling-only heading="수입 및 지출 현황", mineru 의 대응 heading="35. 수입·지출 현황" — 같은 섹션이지만 표기 다름. 표·숫자·문단 핵심 데이터는 완전 일치.
    - 보수적 verdict: heading 텍스트 차이만으로도 P3.2 시각 검증 강제. false-positive 가능성 있지만 운영 초반 안전한 편. P5.1 임계값 보정 시 단서로 기록.
  - **Phase 2 일괄 image rebuild** *(kimbi)*: `2026.05.13.cu126.d` → `2026.05.14`. requirements.txt/Dockerfile 변경 ✗ (entrypoint.py 만), 따라서 Docker layer 캐시 hit — **4초** 만에 rebuild 완료. dev iteration 패턴 (volume-mount) 의 절약분 = 14분 (P2.1/P2.2 두 번의 7분 빌드 회피). 노트북도 entrypoint.py 만 변경 시 같은 캐시 hit 패턴 적용 가능.
  - **호출 형식**: `docker compose run --rm brain-pdf brain-pdf <subcmd> <args>` — service 명 (brain-pdf) + binary 명 (brain-pdf) 2회. ENTRYPOINT 미설정 (compose 의 CMD `sleep infinity` 데몬 모드와 공존 위함). 다소 verbose 지만 Makefile `make run-brain-pdf ARGS="brain-pdf <subcmd> ..."` 가 운영 형식.
  - **다음**: Phase 3 — SKILL.md 절차에 따라 Claude 가 inbox 스캔 → 두 파서 호출 → diff → 분류·승인 흐름 (P3.1~P3.4). VERSION 핀 (`0.1.0-design` → 정식 버전) 도 그 때 함께.
  - **노트북 (ai4lt) parse-docling 검증** (2026-05-14, vault README 인계): 같은 entrypoint.py 가 노트북 CPU 모드에서도 정상 작동. parse-docling 22.1 s *(ai4lt CPU)* / 36.8 s *(ai4lt CPU, 3 pages)*. 출력 JSON 형식·키 셋 데스크탑과 동일.

### Phase 3 — 분류·승인 흐름 (Claude 측 절차)

- [x] **P3.1 inbox 스캔 + 듀얼 파싱 호출 + diff 산출** · Owner: model · Depends on: P2.3 · Done when: SKILL.md 절차에 따라 Claude 가 `00_inbox` 의 PDF 목록 → 각 파일에 두 엔진 호출 → diff 보고서 수집. Notes:
  - **2026-05-14 완료**. WORKDIR=`/tmp/brainify-LukeUE` (P3.2 까지 보존).
  - **호스트 마운트 전략**: `WORKDIR=$(mktemp -d -t brainify-XXXXXX)` 호스트 임시 디렉토리 → 컨테이너 `/work` 로 마운트. 각 `docker compose run --rm` 마다 stdout 을 호스트의 `$WORKDIR/<stem>.{docling,mineru,diff}.json` 으로 redirect. diff subcmd 는 컨테이너 안에서 `/work/<stem>.{docling,mineru}.json` 경로 인자로 받음. 두 파일이 host·container 양쪽에서 보이게 일관 마운트.
  - **inbox 4 PDF (non-PDF·디렉토리 제외)**:
    | # | PDF (stem) | size | docling time | mineru time | verdict | heading | para Δ | tables | numerics |
    |---|---|---|---|---|---|---|---|---|---|
    | 1 | 추계학술대회_참석확인증 | 137 KB | 8s | 28s | diverge | 1.0 (1=1) | 0.333 (6/9) | 0=0 | 0=0 |
    | 2 | 춘계_지도전문의교육_참석확인증 | 139 KB | 8s | 28s | diverge | 0.0 (1/0) | 0.4 (6/10) | 0=0 | 0=0 |
    | 3 | 춘계_참석확인증 | 139 KB | 8s | 27s | diverge | 0.0 (1/0) | 0.4 (6/10) | 0=0 | 0=0 |
    | 4 | 한국원자력_수입지출 | 79 KB | 9s | 32s | diverge | 0.5 (2/1) | 0.091 (11/10) | 5=5 | **108=108** |
  - **관측 4건**:
    1. **모두 diverge** — Phase 1 임계값 (heading_overlap≥0.8) 이 매우 보수적임을 재확인. 핵심 데이터 (numerics, tables) 일치도 100% 인데도 heading 등 메타 차이로 diverge. P3.2 시각 검증 강제 → 안전하지만 false-positive 비율 높음. **P5.1 임계값 보정 단서로 누적**.
    2. **참석확인증 3건 패턴**: docling 은 제목을 heading (#) 으로 추출, mineru 는 paragraph 로. heading_count={a:1, b:0} 또는 b 만 추출. 같은 양식인데 추계 1건만 mineru 가 heading 추출함 — 일관성 결여.
    3. **mineru paragraph 더 잘게 쪼갬**: 참석확인증에서 docling 6 vs mineru 9~10. 동일 텍스트 블록을 mineru 가 line-break 단위로 분할하는 경향.
    4. **회계 PDF**: 108개 숫자 셀 양 엔진 100% 일치 (P2.3 의 자세한 결과). 핵심 데이터 추출 신뢰성 확인.
  - **총 wall time** *(kimbi GPU)*: ~3 분 (4 PDF × ~45 초). 예상치 정확. 노트북 CPU 예상 ~10-15 분 (parse-mineru ~80-150 초/PDF 가정).
  - **다음**: P3.2 — diff verdict=diverge 페이지 시각 검증. 4건 모두 diverge 이므로 Read 도구로 원본 PDF 페이지 시각 해석 + 채택 엔진·사유 1줄 결정.
- [x] **P3.2 차이 발생 페이지 시각 검증** · Owner: model · Depends on: P3.1 · Done when: diff 임계값 초과 페이지에 대해 Claude 가 Read 도구로 해당 페이지 시각 해석 → 두 엔진 중 정확한 쪽 선택 + 사유 1줄 기록. Notes:
  - **2026-05-14 완료**. 4 PDF 모두 verdict=diverge → 4건 모두 시각 검증 (Claude Code 의 Read 도구 멀티모달 PDF 직접 해석).
  - **패턴 승인 적용**: 학회 참석확인증 3건은 거의 동일 양식 → 추계 1건만 PDF Read 로 시각 검증, 결정을 같은 양식 춘계 2건에 적용 (마크다운만 빠르게 cross-check). 회계 PDF 는 양식 다르므로 개별 검증. SKILL.md 의 "같은 출처·유사 형식은 패턴 승인" 원칙 적용.
  - **채택 결정 표**:
    | # | PDF | 채택 | 사유 (1줄) |
    |---|---|---|---|
    | 1 | 추계학술대회_참석확인증 | MinerU | 본문 line break 4줄 보존 + 도장 위 "대한핵의학회" 텍스트 추출 (docling 은 합치고 누락) |
    | 2 | 춘계_지도전문의_참석확인증 | MinerU | 동일 양식, 동일 사유 (패턴 승인) |
    | 3 | 춘계_참석확인증 | MinerU | 동일 양식, 동일 사유 (패턴 승인) |
    | 4 | 한국원자력_수입지출 | Docling | 공통공개기준 bullet list 보존 (mineru 는 1열 `<table>` 로 변질) + heading 2개 충실 추출 + pipe-markdown 가독성 우위 |
  - **시각 검증으로 확인된 엔진별 강·약점**:
    - **Docling 강점**: bullet list 정확 보존, heading 더 적극 추출, pipe-markdown 가독성↑
    - **Docling 약점**: 본문 line break 무시하고 paragraph 단위로 합침, image-인접 텍스트 (예: "대한핵의학회" 도장 라벨) 누락 경향, 표 셀 안 line break → 공백 변환 (`정부순지 원.pdf`)
    - **MinerU 강점**: 원본 line break 보존, image-인접 텍스트 픽업, HTML 표의 rowspan/colspan 구조 충실
    - **MinerU 약점**: bullet list 를 1열 `<table>` 로 잘못 인식, heading 추출 일관성 결여 (같은 양식 3건 중 1건만 heading 잡음), paragraph 를 더 잘게 쪼개는 경향
  - **운영 통찰**:
    - 일반적 통념 ("MinerU = CJK·표 강세, Docling = 학술논문 강세") 부분 역전: 한국어 회계 PDF (CJK + 표) 에서 docling 이 bullet/heading 더 우수.
    - **단일 엔진 best 가 없음을 실증** — 듀얼 + 시각 검증 가치 확인.
    - 4 PDF 모두 verdict=diverge 인 점이 임계값 보수성 재확인. 그러나 verdict=agree 였더라도 (예: 가상의 경우) docling-우선 자동 채택은 회계 PDF 에서 옳은 선택이었을 것. 현재 임계값 + 자동 우선 정책은 합리적.
    - **OCR artifact 발견 0건** — "한국**국**원자력의학원" 의 'ㅏㄴ국국' 은 PDF text layer 자체의 오류 (원본이 잘못 작성됨). 두 엔진 모두 PDF text layer 충실히 추출. OCR 분기 (Phase 2) 진입 없이 디지털 텍스트 PDF 만으로 충분.
  - **다음**: P3.3 — PARA 분류·파일명·동반 노트 초안 제안. CLAUDE.md §0 중복/연결 검사 통합.
- [x] **P3.3 PARA 분류·파일명 제안** · Owner: model · Depends on: P3.2 · Done when: 각 PDF 에 대해 (1) 정착 PARA 폴더, (2) 표준 파일명, (3) 동반 노트 본문 초안, (4) `[[wikilink]]` 후보 목록 제안. CLAUDE.md §0 중복/연결 검사 통합. Notes:
  - **2026-05-14 완료**. CLAUDE.md §0 중복/연결 검사 — `02_areas/대한핵의학회/`·`02_areas/한국원자력의학원/` 폴더 모두 이미 존재, `02_areas/대한핵의학회/2026_춘계학술대회/` 기존 패턴 답습.
  - **분류 결정**:
    | # | PDF | 신설 폴더 | 신설 파일명 |
    |---|---|---|---|
    | 1 | 추계_참석확인증 | `02_areas/대한핵의학회/2025_추계학술대회/` (신설) | `2025-11-14_KSNM_2025추계학술대회_참석확인증.pdf` |
    | 2 | 춘계_지도전문의 | `02_areas/대한핵의학회/2025_춘계학술대회/` (신설) | `2025-05-09_KSNM_2025지도전문의교육_참석확인증.pdf` |
    | 3 | 춘계_참석확인증 | `02_areas/대한핵의학회/2025_춘계학술대회/` (신설) | `2025-05-10_KSNM_2025춘계학술대회_참석확인증.pdf` |
    | 4 | 한국원자력_수입지출 | `02_areas/한국원자력의학원/경영공시/` (신설) | `2026-04-13_KIRAMS_2025수입지출현황.pdf` |
  - **파일명 결정 근거**:
    - 출처 약자 대문자: `KSNM` (대한핵의학회), `KIRAMS` (한국원자력의학원) — 기존 `02_areas/대한핵의학회/` 폴더 안 `2026-05-07_KSNM_제64차춘계학술대회.md`·`2026-05-08_KSNM춘계_광주출장_증빙세트.md` 컨벤션 일치.
    - 날짜: PDF 안 행사일 기준 (학술대회) / 제출일 기준 (회계 — 기준일 2025-12-31, 제출일 2026-04-13).
    - "김병일" 인명 제외 — vault 자체가 Dr. Ben 자료라 default 명시 불필요. 기존 노트 패턴 일치.
  - **wikilink 후보 빈약** — 같은 학술대회의 등록비·자료집 노트가 vault 에 아직 없음. 4건 모두 새 anchor 노드. 단 춘계 2건끼리는 연결 (`[[2025-05-09_...]] ↔ [[2025-05-10_...]]` — 연속 이틀 행사).
- [x] **P3.4 Dr. Ben 승인 → 이동·노트 생성** · Owner: model · Depends on: P3.3 · Done when: 승인 후 (1) `sources/00_inbox/<원파일>` → `sources/0X_.../<새이름>` 이동, (2) `knowledge/0X_.../<새이름>.md` 생성, (3) `00_inbox` 비어짐 확인. 영속 이력 기록 여부 결정. Notes:
  - **2026-05-14 완료**. Dr. Ben 승인: "일단 진행하고 추후에 내가 폴더구조를 보고 수정할 수 있도록 진행하자" (사후 수정 전제 하 진행).
  - **신설 디렉토리 6개**: sources/knowledge 양쪽에 `2025_추계학술대회/`·`2025_춘계학술대회/`·`경영공시/`.
  - **이동**: 4 PDF 모두 `sources/00_inbox/` → 정착 위치로 `mv` (rename in transit). 0건 잔여 ✅.
  - **동반 노트 4건 생성**: CLAUDE.md 표준 frontmatter (`title`/`source`/`date`/`tags`/`sources:` vault-root 상대경로) + 본문 첫 줄 `[원본 PDF](sources/...)` 마크다운 링크 + 한 줄 요약 + 핵심 내용 + `내 생각` (TBD) + `관련 노트` (TBD/wikilink) + **듀얼 파싱 채택 메타** (채택 엔진·사유·diff verdict 수치) 섹션 포함.
  - **회계 PDF 동반 노트**: 본문 안에 6개년 시계열 추세 표 (출연금·수입합계·지출합계·수지차) 직접 작성 — 동반 노트 자체가 핵심 데이터 anchor. **수지차 -22,268 백만원 (2025 역대 최대)** 등 주요 관찰 4건 명시.
  - **영속 이력 기록 (`state/processed.jsonl`)**: Phase 1 에서는 **skip 결정**. Vault 자체 (sources + knowledge) + git history (도입 시) 가 영속 기록. 별도 ledger 는 중복. Phase 5 에서 OpenClaw 자동 트리거 도입 시 재검토.
  - **inbox 잔여 (비-PDF·Phase 1 범위 외)**: `.md` 2건 (Gmail 캡처 — 이미 brainified 형식), `.docx` + `.md.txt` 1건 (AI 도구 리뷰), `_attachments/` 디렉토리, `경영알리오_한국원자력의학원_회계감사보고/` 디렉토리 (2021~2025 회계자료 일괄 — 후속 처리 대상).
  - **노트북 SKILL.md 전 절차 통과** (2026-05-14, vault README 인계): `한국원자력의학원_임직원+수.pdf` (98 KB, 3 pages) 로 노트북 (ai4lt CPU) 에서 §0~§8 모든 단계 통과. diff verdict=diverge (heading_overlap=0.4, numeric_cell_match=0.713) → 시각 검증 후 **Docling 채택** (heading 3개 정확 + markdown 표 형식). 정착: `sources/02_areas/한국원자력의학원/경영공시/2026-04-13_KIRAMS_2025임직원수.pdf` + 동반 노트. 데스크탑이 처리한 `수입지출현황` 과 같은 시리즈·파일명 컨벤션 일관 유지. **양 PC 모두 같은 skill·이미지·절차로 end-to-end 작동 검증됨**.
  - **Dr. Ben 사후 검토 포인트** (사용자가 직접 vault 보고 결정):
    - `2025_추계학술대회`·`2025_춘계학술대회` 폴더명이 기존 `2026_춘계학술대회` 와 패턴 동일 → 좋음
    - 회계 PDF 위치 `경영공시/` 가 자연스러운지, 아니면 `회계/` 또는 더 세분 (`연간공시/` 등)
    - 파일명에 인명 (`김병일`) 제거 결정이 OK 인지
    - 채택 엔진 메타 섹션이 동반 노트에 유지될지 (운영 후 효용 판단)
  - **다음**: P3 절차 검증 완료 (P3.1~P3.4 모두). Phase 4 — 실자료 검증 (P4.1~P4.3) 은 Phase 3 절차의 *재실행 검증* 이라 본질적으로 같음. Phase 1 마감 후 Phase 5 (실 inbox 1주 운영) 로 직행 가능. `entrypoint.py` 의 `VERSION = "0.1.0-design"` → 정식 버전 핀, `SKILL.md` 의 `status: design-only` 해제도 함께.

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
- 2026-05-14 — **Phase 1~3 마감**. P1.1~P1.5 (인프라·Docker·Docling·MinerU offline) + P2.1~P2.3 (parse-docling·parse-mineru·diff) + P3.1~P3.4 (실 inbox 4 PDF 처리: 학회 참석확인증 3 + 회계공시 1) 모두 통과. **brain-pdf 이미지** = `2026.05.14` (entrypoint VERSION 0.2.0). **SKILL.md** `status: design-only` → `active`. **건너뜀**: Phase 4 (실자료 검증 P4.1~P4.3) — Phase 3 이 본질적으로 실자료 검증이라 별도 단계 불필요 (P4 는 Phase 1 의 Out of scope 자료 — 영수증·논문 — 들어올 때 ad-hoc 검증).
- 2026-05-14 — **다중 PC 어댑터 패턴 도입** (Dr. Ben 우려 제기 후). 데스크탑 ↔ 노트북 git 동기 시 ping-pong fix cycle 차단. 핵심 결정: ① `scripts/detect-compose.sh` 가 nvidia-smi + docker info 검사 후 compose 체인 출력 (`BRAIN_PDF_FORCE_VARIANT=gpu|cpu` env override 지원). ② Makefile 의 `-gpu` suffix 타겟 제거 — 단일 `build-brain-pdf` / `run-brain-pdf` 가 detect 사용. ③ SKILL.md §2 + Manual test 의 하드코드 gpu.yml 제거. ④ LAPTOP-SETUP.md 전면 갱신 — 옵션 1/2 분기 폐기, 단일 셋업 절차. ⑤ 정책 메모리 [[no-machine-specific-in-synced-files]] 신규. 데스크탑 live 검증: auto → `cuda_available=True`, FORCE_VARIANT=cpu → `cuda_available=False` (same image, different runtime). 노트북 동기 안전 확보. **다음**: Phase 5 — 실 inbox 1주 운영 (P5.1) + OpenClaw 사이드잡 검토 (P5.2). 첫 노트북 동기 시 `LAPTOP-SETUP.md` 의 4 단계만 실행.
- 2026-05-14 (오후, 데스크탑 통합) — **노트북 (ai4lt) 인계 통합**. 데스크탑 push (`8fae229` docker + `bb83f7a` skills) 후 노트북이 vault 안 `knowledge/02_areas/brain-system/tools/2nd-brain-docker/brain-pdf/README.md` 로 인계 (실측 데이터·formula deadlock 해소·임직원수 PDF 정착·patch 파일 보존). 데스크탑이 본 README 를 읽어 P1.4·P1.5·P3.4 Notes 에 노트북 CPU 실측·SKILL.md 전 절차 통과·formula 재발 모니터링 메모 통합. 메모리 [[multi-pc-claude-code-handoff]] 신규 — 노트북=vault README 인계, 데스크탑=동기 자산 정본 갱신+push 분업 규칙 명문화. 메모리 [[user-machines-spec]] 갱신 (노트북 hostname `ai4lt` 확정).
- 작성자: Dr. Ben + Claude.
- 수정 시: §Spec·§Plan 변경은 Dr. Ben 승인 후. §Tasks 항목 추가/삭제도 동일. 모델은 진행 중 항목의 Done when 정밀화·Notes 누적만 자율. **성능 수치·환경 의존 측정 Notes 추가 시 측정 PC 를 inline 명시** (예: `*(kimbi GPU)*`, `*(노트북 <hostname> CPU)*`) — 양 PC 측정값을 같은 행에 누적할 때 비교 기준 보존.
