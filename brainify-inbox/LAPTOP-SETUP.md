# brainify-inbox — 노트북 환경 셋업 가이드

> 2026-05-14 갱신. 어댑터 패턴 채택 후. 데스크탑·노트북 동일 명령으로 셋업·운영.

## 한 줄 요약

**같은 git 동기 자산 + 같은 `make build-brain-pdf` 명령. `scripts/detect-compose.sh` 가 PC 환경 자동 감지해 분기.** 노트북에서 *수동 분기·옵션 선택·`.env.local`·NVIDIA 스택 설치* 모두 불필요.

## 어댑터 아키텍처 (왜 노트북도 같은 이미지로 작동하는가)

| 레이어 | 어댑터 |
|---|---|
| Docker 이미지 콘텐츠 | 양 PC 동일 (Dockerfile cu126 wheel 그대로) — bit-identical 빌드 가능 |
| 컨테이너 안 PyTorch | `torch.cuda.is_available()` 가 runtime 에 GPU 유무 자동 판단 → CUDA/CPU 백엔드 자동 선택 |
| Docker 의 GPU 노출 | compose 레벨 — `detect-compose.sh` 가 nvidia-smi 통과 시에만 `compose.brain-pdf.gpu.yml` 추가 (`--gpus all`) |
| 운영 명령 | `make build-brain-pdf` / `make run-brain-pdf` — 양 PC 공통 |

**cu126 wheel 의 CPU 환경 작동**: cu126 wheel 은 Python torch 바인딩 + 번들 CUDA `.so` 라이브러리 (~5 GB) 의 합. CPU-only 시스템에서 import 정상, `torch.cuda.is_available() == False`, 자동 CPU fallback. ~5 GB 디스크 낭비는 **의식적 trade-off** — 머신-specific 빌드 회피로 얻는 운영 단순성이 더 큼.

## 노트북 사양 (2026-05-13 확인, hostname 2026-05-14 확정)

| 항목 | 값 | 함의 |
|---|---|---|
| hostname | **`ai4lt`** | `kimbi` (데스크탑) 와 즉시 구분 가능 |
| CPU | Intel Core Ultra 7 255H (Arrow Lake-H hybrid) | P+E core. PyTorch CPU inference 충분 |
| RAM | 32 GB physical / 14 GB WSL2 | 빠듯 — 데몬 ✗, ephemeral ✅ |
| GPU | **Intel Arc 140T** (IPEX-LLM 지원) | NVIDIA 아님 — detect 가 자동 skip |
| Windows 측 RAM | 18 GB | qwen2.5-14B-q4 IPEX-LLM 가속 점유 |
| OS | Ubuntu 24.04.1 LTS (Noble) | — |
| 네트워크 | WSL2 Mirrored Network 모드 | Docker bridge 정상 작동 |

## 노트북 셋업 단계

### 1. git pull (동기)

데스크탑이 push 한 변경 받기. 다중-PC 동기 전략은 vault CLAUDE.md 참조.

```bash
cd ~/projects/2nd-brain-docker && git pull
cd ~/.claude/skills && git pull
# vault 는 SyncThing 자동
```

### 2. .env 셋업 (`.env` 는 gitignored — PC 별 셋업)

```bash
cd ~/projects/2nd-brain-docker
# .env 없으면 example 에서 복사. 있으면 BRAIN_PDF_VERSION 확인/갱신.
[ ! -f .env ] && cp .env.example .env
grep -q '^BRAIN_PDF_VERSION=' .env || echo "BRAIN_PDF_VERSION=2026.05.14" >> .env
# 또는 값 갱신 필요 시: sed -i 's/^BRAIN_PDF_VERSION=.*/BRAIN_PDF_VERSION=2026.05.14/' .env
```

`.env.example` 의 `BRAIN_PDF_VERSION` 이 최신 값으로 갱신되어 동기됨 — 새 PC 셋업 시 `cp .env.example .env` 만으로 작동.

### 3. sanity 확인

```bash
hostname                  # kimbi 와 다른지 확인
docker info | head -3     # docker daemon 정상
which nvidia-smi          # → "no nvidia-smi" 정상 (없어야 함)
./scripts/detect-compose.sh
                          # → "-f compose.yml -f compose.brain-pdf.yml" (gpu.yml 없음 = 정상)
```

### 4. Docker 이미지 빌드 (한 번, ~5-7분)

```bash
make build-brain-pdf
# detect-compose.sh 가 NVIDIA 없음을 감지 → base compose 만 사용
# 결과: 2nd-brain/brain-pdf:2026.05.14 (CPU 모드, cu126 wheel 포함 ~12.5 GB)
```

### 5. 모델 캐시 첫 다운 + 정상 동작 검증

```bash
# 임의 inbox PDF 1개로 첫 실행 — HF 모델 자동 다운로드 (~500 MB)
make run-brain-pdf ARGS="brain-pdf parse-docling /home/user/projects/2nd-brain-vault/sources/00_inbox/<sample>.pdf" > /tmp/test.json
echo "exit=$?"            # 0 이면 성공
python3 -c "import json; d=json.load(open('/tmp/test.json')); print('engine:', d['engine'], 'pages:', d['pages'], 'runtime:', d['runtime_sec'])"

# 버전 확인
make run-brain-pdf ARGS="brain-pdf --version"   # → 0.2.0
```

### 6. 성능 측정 (PROGRESS.md 누적용)

데스크탑 vs 노트북 성능 차이 — **2026-05-14 노트북 (ai4lt) 실측 반영**:

| 명령 | 데스크탑 (kimbi GPU) | **노트북 (ai4lt CPU) 실측** | 자료 |
|---|---|---|---|
| parse-docling | ~8 s | **22.1 s** (2 pages) / **36.8 s** (3 pages) | 한국원자력의학원 자료 |
| parse-mineru | ~30 s | **47.2 s** (2 pages) / **51.1 s** (3 pages) | 동상 |
| diff | <1 s | 1.3 s | — |

LAPTOP-SETUP 초기 추정 (parse-mineru `~80-150 s`) 은 **과대 추정**. 실측 47-51 s 가 정확. parse-docling 추정 (`~20-40 s`) 은 적중. 측정값을 `PROGRESS.md` P1.4 / P1.5 Notes 에 hostname 명시해 누적.

### MinerU formula recognition 운영 메모

- **2026-05-14 오전** (cu126.b 시점, mineru extras 미핀): 노트북 CPU 모드에서 `mineru -f true` (default) 가 MFR (Math Formula Recognition, UnimerSwin) 모델 init 단계의 multiprocessing.spawn deadlock 으로 7+ 분 hang. fast_api `processing_tasks=1` 인 채 무한 대기. fallback 절차: `mineru -p ... -b pipeline -l korean -f false -t true --image-analysis false`. 회계 자료처럼 수식 없으면 충분.
- **2026-05-14 오후** (cu126.d 시점, mineru[pipeline,vlm] 핀 적용 후): 같은 PDF 가 default opts (`-f true`) 로 47.2 s 정상 완료. **운영 제약 일단 해제**. 가설 (vlm extras 의 init 순서 / cu126 wheel 의 thread-local state / multiprocessing race 변동) 검증 ✗ — 회귀 가능성 모니터링.
- **재발 시**: 위 fallback 명령으로 우회. entrypoint.py 의 `parse_mineru()` 수정 (formula opt 노출) 은 별도 작업.

## 우려사항·체크 포인트

### 첫 빌드 시간
노트북 (Arrow Lake-H + NVMe SSD) 에서 `make build-brain-pdf` ~5-7분 (apt + pip cu126 wheel + RAPIDOCR pre-download). cu126 wheel 자체는 PyPI 인덱스에서 다운, GPU 없어도 정상.

### Mirrored Network 영향
WSL2 Mirrored Network 모드는 host 와 WSL 네트워크 namespace 공유. Docker bridge 정상. Windows Defender 가 docker bridge 통신 막을 수 있음 — 첫 모델 다운로드 timeout 시 확인.

### 메모리 모니터링
brain-pdf 실행 중 sb-claude (4 GB heap) + 브라우저 + IDE 병행 시 OOM 가능. `free -h` 또는 `top` 으로 모니터링. ephemeral (`run-brain-pdf`) 만 사용, 데몬 (`up-brain-pdf`) ✗.

### 모델 캐시는 PC 별 독립
`brain-pdf-models` Docker named volume 은 git/SyncThing 동기 대상 ✗. 노트북에서 첫 실행 시 ~500 MB 다시 다운로드. 정상.

### Ubuntu 24.04 vs 데스크탑
Docker / docker-compose / make 는 안정 인터페이스라 문제 없음. apt 버전 차이 영향 0.

## 강제 변형 (드물게 — 디버깅용)

```bash
# 데스크탑에서 의도적으로 CPU 사용 (GPU 점유 작업 충돌 등)
BRAIN_PDF_FORCE_VARIANT=cpu make run-brain-pdf ARGS="brain-pdf parse-docling ..."

# 노트북에서 detect 가 실패 (NVIDIA 가짜 PC) 시 강제 비활성
BRAIN_PDF_FORCE_VARIANT=cpu make run-brain-pdf ...
```

`BRAIN_PDF_FORCE_VARIANT=gpu` 는 NVIDIA 없는 PC 에서 실행하면 docker compose 가 nvidia runtime 못 찾고 실패. 노트북에서 사용 ✗.

## 다음 작업

노트북 셋업 통과 후 `PROGRESS.md` 의 진행 단계 따라가기. Phase 5 (실 inbox 1주 운영) 가 다음 자연스러운 단계.

## 메타

- 2026-05-13 — 최초 작성. 데스크탑 kimbi P1.4 마감 시점. 옵션 1 (같은 이미지) / 옵션 2 (CPU build arg toggle) 분기 제시.
- 2026-05-14 — **어댑터 아키텍처로 전면 갱신**. `scripts/detect-compose.sh` + Makefile auto-detect 도입. 옵션 1/2 분기 폐기 — 단일 절차로 양 PC 공통 셋업. cu126 wheel 의 CPU 환경 작동 / PyTorch runtime adapter / Docker GPU 노출 분리 의 3 층 어댑터 패턴 명문화. 이로써 git push 가 데스크탑·노트북 양쪽에 안전.
- 2026-05-14 (오후) — **노트북 ai4lt 실측 반영**. hostname 확정 (`ai4lt`). Step 6 의 추정값 정정 (parse-mineru `80-150 s` → 실측 `47-51 s`). MinerU formula deadlock 운영 메모 추가 — 오전 발견·오후 해소·재발 시 fallback 명시. 노트북측 vault 인계 README 의 데이터 통합.
- 작성자: Dr. Ben + Claude.
- 수정 시: 노트북에서 실제 셋업 통과 후 단계별 시간·이슈 누적. 어댑터 패턴 위반하는 변경 ✗ (예: Dockerfile cu126 hardcode 제거, machine-specific build arg 등).
