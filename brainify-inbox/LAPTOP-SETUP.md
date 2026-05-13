# brainify-inbox — 노트북 환경 셋업 가이드

> 2026-05-13 기준. 데스크탑 kimbi 에서 P1.4 까지 완료된 시점에 작성. 노트북에서 동일 단계 재개할 때의 가이드.

## 한 줄 요약

**노트북은 Intel GPU 환경이라 NVIDIA 스택 (`nvidia-container-toolkit`·`cu126`·`--gpus all`·`compose.brain-pdf.gpu.yml`) 을 *전혀 사용하지 않는다*. CPU-only 모드로 운영하며, base `compose.brain-pdf.yml` 만 합성한다.**

## 노트북 사양 (2026-05-13 확인)

| 항목 | 값 | 함의 |
|---|---|---|
| CPU | Intel Core Ultra 7 255H (Arrow Lake-H hybrid) | P+E core. PyTorch CPU inference 충분 |
| RAM | 32 GB physical / 14 GB WSL2 | 빠듯 — 데몬 ✗, ephemeral ✅ |
| GPU | **Intel Arc 140T** (IPEX-LLM 지원) | NVIDIA 아님 — `nvidia-container-toolkit` 불가 |
| Windows 측 RAM | 18 GB | qwen2.5-14B-q4 IPEX-LLM 가속 점유 |
| OS | Ubuntu 24.04.1 LTS (Noble) | 데스크탑 (확인 필요) 보다 신버전 가능 |
| 네트워크 | WSL2 Mirrored Network 모드 | host·WSL 네트워크 namespace 공유. Docker bridge 정상 작동 |
| hostname | 미확인 (`hostname` 으로 확인) | kimbi ✗ — 별도 PC |

## 전략 — 왜 CPU only 인가

### 1. GPU 스택 자체가 다름

데스크탑에서 한 셋업은 NVIDIA 가정:

- `nvidia-container-toolkit` — NVIDIA driver 와 직접 통신, Intel GPU 미지원
- `--gpus all` Docker flag — NVIDIA-specific
- PyTorch `cu126` wheel — CUDA 12.6 (NVIDIA) 컴파일 빌드, 이미지의 ~5 GB CUDA 라이브러리는 Intel GPU 에서 *완전히 무용지물*
- `compose.brain-pdf.gpu.yml` 의 `deploy.resources.reservations.devices.driver: nvidia` — Intel GPU 인식 못함

Intel GPU 를 컨테이너에서 쓰려면 완전히 다른 스택:

- Intel oneAPI Container Toolkit (NVIDIA 와 별개)
- `intel-extension-for-pytorch` (IPEX) — `torch.xpu` device
- `--device /dev/dri` 마운트 + Intel runtime libs
- 이미지 사이즈도 다시 ~5 GB 추가

### 2. qwen 이 GPU 점유

노트북의 Intel Arc 140T 는 Windows 측 qwen2.5-14B-q4 가 IPEX-LLM 으로 사용 중. brain-pdf 가 WSL2 에서 GPU 쓰려면 qwen 과 GPU/VRAM 경합 — 둘 다 느려짐.

### 3. 메모리 압박 회피

14 GB WSL2 안에서:
- sb-claude (NODE_OPTIONS 4 GB heap)
- system overhead (~2 GB)
- brain-pdf CPU 추론 시 RAM 점유 ~3-4 GB
- = 9-10 GB 사용, 4-5 GB 여유

데몬 모드 (`up-brain-pdf`) 로 brain-pdf 를 RAM 상주시키면 다른 작업 어려움. **ephemeral (`run-brain-pdf`)** 가 필수.

### 4. 성능 — 수용 가능

CPU 추론 (Arrow Lake-H 16+ cores) 으로:
- 단일 PDF (10페이지 정도) Docling 변환: ~20-40초 예상
- inbox 5건 batch: ~2-3분
- brainify 가 occasional 사용이라 충분히 수용 가능

GPU 가속 5-10× 는 매력적이지만 위 1-3 의 비용이 더 큼.

## 노트북 셋업 단계

### Phase A — 사전 준비 (다른 작업과 공통)

```bash
# 1. cron 상태 확인 — 데스크탑이 켜놓고 갔다면 노트북은 off 유지 (양쪽 동시 발화 방지)
hostname                       # 노트북 hostname 확인 (kimbi 와 다른지)
/cron status                   # 노트북 cron 상태

# 2. 저장소 동기 — 데스크탑에서 push 한 변경 받기
/git-routine pull              # 데스크탑이 push 했다면 brain-pdf 파일들 수령
                               # 노트북에 brain-pdf-docker 가 최신 상태인지 확인
```

### Phase B — brain-pdf CPU 변형 빌드

데스크탑과 *다른* Dockerfile 또는 다른 wheel 인덱스 사용. 두 가지 옵션:

#### 옵션 1 — 같은 이미지 (간단, 5 GB 디스크 낭비)

```bash
cd ~/projects/2nd-brain-docker

# .env 의 BRAIN_PDF_VERSION 확인 (예: 2026.05.13.cu126.b)
# CUDA 라이브러리 5 GB 가 노트북에서 무용지물이지만 같은 빌드라 단순

make build-brain-pdf           # NOT make build-brain-pdf-gpu
```

#### 옵션 2 — CPU-only 별도 변형 빌드 (추천, ~5 GB 절약)

Dockerfile 의 pip install 인덱스를 `cu126` → `cpu` 로 바꿔 별도 태그로 빌드. 작업:

1. `images/brain-pdf/Dockerfile` 의 pip 인덱스를 `--index-url https://download.pytorch.org/whl/cpu` 로 변경 (또는 build arg 로 토글 가능하게 리팩토링)
2. `BRAIN_PDF_VERSION` 을 `cpu` 접미사 (예: `2026.05.13.cpu.a`) 로 bump
3. `make build-brain-pdf` 실행 — CPU wheel 만 받음

⚠️ 옵션 2 채택 시 **이 변경이 git push 되면 데스크탑에서 다음 `git pull` 후 GPU 빌드가 깨질 수 있음**. 두 환경을 build arg 토글 (예: `BRAIN_PDF_TORCH_INDEX=cu126|cpu`) 로 통합하는 게 더 깨끗 — 노트북 셋업 시 이 리팩토링부터 하는 것도 좋음.

**권고**: 첫 노트북 셋업은 옵션 1 (같은 이미지) 로 빠르게 통과 → P1.4 검증 → 그 다음 옵션 2 (build arg 토글) 로 리팩토링.

### Phase C — P1.4 동일 검증 (노트북)

```bash
# 첫 docling 실행 — HF 모델 다운로드 + CPU 추론
cd ~/projects/2nd-brain-docker

time docker compose -f compose.yml -f compose.brain-pdf.yml run --rm brain-pdf bash -c '
  set -e
  INPUT="/home/user/projects/2nd-brain-vault/sources/00_inbox/한국원자력의학원_수입지출+현황.pdf"
  OUT=/tmp/docling-out
  mkdir -p "$OUT"
  docling "$INPUT" --to md --output "$OUT" 2>&1 | tail -10
  ls -la "$OUT"
  head -50 "$OUT"/*.md
'

# 예상: 데스크탑 57초 → 노트북 90-180초 (GPU 없음, 14GB RAM)
# 출력은 데스크탑과 bit-identical 또는 거의 동일해야 함

# 캐시 hit 재실행
# 예상: 데스크탑 10초 → 노트북 30-60초

# Offline 검증
docker run --rm --network none \
  --user 1000:1000 \
  -v ~/projects/2nd-brain-vault:/home/user/projects/2nd-brain-vault \
  -v 2nd-brain-docker_brain-pdf-models:/home/user/.cache/huggingface \
  -e HF_HOME=/home/user/.cache/huggingface \
  -e TRANSFORMERS_OFFLINE=1 \
  -e HF_HUB_OFFLINE=1 \
  -w /home/user/work \
  2nd-brain/brain-pdf:<version> \
  docling /home/user/projects/2nd-brain-vault/sources/00_inbox/한국원자력의학원_수입지출+현황.pdf --to md --output /tmp/out
```

**중요**: `--gpus all` flag 없음. nvidia-container-toolkit 도 없음.

### Phase D — PROGRESS.md 정리

노트북에서 P1.4 동일 검증 통과 시 PROGRESS.md 의 `§Tasks · P1.4` Notes 에 추가:
- 노트북 (hostname `<x>`) 에서도 검증 통과
- CPU 추론 시간 측정값 (첫 실행·재실행)
- GPU 변형 (cu126.b) 과 CPU 변형 (있다면) 의 이미지 사이즈·동작 차이

이후 P1.5 (MinerU) 진행은 노트북·데스크탑 어느 쪽에서든 OK — 같은 절차.

## 우려사항·체크 포인트

### 첫 빌드 시간

노트북 (Intel Core Ultra 7 + NVMe SSD 가정) 에서 `make build-brain-pdf`:
- 데스크탑 (~7분, 2번째는 ~3분) 보다 *약간 빠를 수 있음* (Arrow Lake-H 가 i7-9700 / 등급에 비해 더 빠른 single-thread)
- 또는 비슷 (apt·pip·docker layer 가 네트워크 의존)

### Mirrored Network 영향

WSL2 Mirrored Network 모드는 host 와 WSL 네트워크 namespace 공유. Docker 컨테이너는 여전히 docker0 bridge 사용 → 영향 없음. 다만 firewall (Windows Defender) 이 docker bridge 통신을 막을 수 있음 — 첫 모델 다운로드 시 timeout 발생하면 Windows Defender·third-party AV 룰 확인.

### Ubuntu 24.04 vs 데스크탑

데스크탑 OS 버전 미확인. 노트북이 Noble (24.04) 이면 일부 패키지 버전 차이 가능. Docker / docker-compose / make 는 안정 인터페이스라 문제 없을 것.

### 메모리 모니터링

brain-pdf 실행 중 다른 메모리 헤비 작업 (sb-claude 에서 큰 컨텍스트, 브라우저, IDE) 병행 시 OOM 가능. `free -h` 또는 `top` 으로 RAM·swap 사용량 관찰. 빌드 중에는 다른 무거운 작업 피하기.

### 모델 캐시는 PC 별 독립

`brain-pdf-models` Docker named volume 은 git/SyncThing 동기 대상 ✗. 노트북에서 첫 실행 시 ~500 MB 다시 다운로드해야 함. 정상 동작.

## 다음 작업

P1.4 노트북 검증 통과 후:
- **P1.5 — MinerU 설치 + 모델 다운로드 + offline 검증** (같은 PDF, 노트북 또는 데스크탑 어디서든)
- P2.1 — Docling CLI 래퍼 (`parse_docling.py` in `entrypoint.py`)
- P2.2 — MinerU CLI 래퍼
- P2.3 — Diff 모듈

§Tasks 진행 순서는 PROGRESS.md 가 권위 원본. 본 가이드는 노트북 특수 사항만 다룸.

## 메타

- 2026-05-13 — 최초 작성. 데스크탑 kimbi 에서 P1.4 마감 시점에, Dr. Ben 의 "노트북에서 이어 작업" 결정 받아 작성.
- 작성자: Dr. Ben + Claude.
- 수정 시: 노트북에서 실제 셋업 통과 후 단계별 시간·이슈 누적. 옵션 2 (CPU build arg) 채택 시 Dockerfile 리팩토링 patch 도 본 문서 또는 PROGRESS.md §Plan 에 기록.
