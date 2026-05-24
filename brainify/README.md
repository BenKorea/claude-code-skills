# brainify (Claude Code skill)

00_inbox 유입물 → 파싱 → PARA 분류 → 동반 노트 작성까지의 **브레인화** 스킬.
무거운 LLM 판단(분류·요약·링크)이 필요해 **Claude Code 스킬**로 둔다 (OpenClaw 리액티브
스킬과 구분 — 그쪽은 결정형·소규모용). 단 `brainify.py` 가 결정형 작업을 담당하므로
native OpenClaw·openclaw-docker 의 cron 에서 `python3 brainify.py scan` 식 호출도 가능하다.

## 구조 (단일 스킬 + 결정형 helper)

```
~/.claude/skills/brainify/
├── SKILL.md      ← 오케스트레이션 + LLM 판단(PARA·요약·링크). /brainify, /brainify audit
├── brainify.py   ← 결정형 CLI: scan · inspect · commit · audit (출력 JSON)
└── README.md
```

판단(PARA 좌표·노트 본문)과 메커니즘(파싱·이동·dedup·쓰기)을 한 스킬 안에서 분리했다:
LLM 은 SKILL.md, 결정형은 brainify.py. 다중 스킬로 쪼개지 않은 이유 — 흐름이
scan→inspect→(판단)→commit 한 줄기라 wrapping 오버헤드만 늘기 때문.

## helper 서브커맨드

| 명령 | 하는 일 |
|---|---|
| `scan` | 00_inbox 처리 대상(스레드 폴더·낱개 파일) + dedup 상태 JSON |
| `inspect <item>` | 스레드 본문 + 첨부 2brain-parser 파싱 markdown + 식별자 |
| `commit <item> --para .. --name .. --body-file ..` | 원본 이동 + 동반 노트 작성 + 플래그 + inbox 비움 |
| `audit` | `para_review: pending`·`parse_confidence: low` 노트 나열(주간 감사) |

## 의존

- **2brain-parser** 컨테이너 (`ghcr.io/benkorea/2brain-parser:latest`) — inspect 의 첨부 파싱.
  Docker 없으면 첨부 본문 없이 보존 + `parse_confidence: low`.
- 정본 vault `~/projects/2nd-brain-vault` (env `BRAINIFY_VAULT` 로 변경 가능).

## 환경변수

- `BRAINIFY_VAULT` — 정본 vault (기본 `~/projects/2nd-brain-vault`)
- `BRAINIFY_PARSER_IMAGE` — 파서 이미지 (기본 `ghcr.io/benkorea/2brain-parser:latest`)
- `BRAINIFY_MODELS_VOLUME` — HF 모델 캐시 볼륨 (기본 `2nd-brain-docker_brain-pdf-models`)

## 정책

[자동 우선·주간 감사](https://github.com/.../automation-weekly-audit.md): 건별 사람 승인 없이
낙관적으로 자동 배치하고, `para_review: pending`·`parse_confidence: low` 플래그를 단 뒤
품질은 `/brainify audit` 으로 주 1회 모아 감사한다.

> 구 `brainify-inbox` 스킬은 PDF 전용·대화형 설계였고, 이 `brainify` 가 그 후속
> (전 포맷·자동 우선·결정형 helper 분리). 백업: `/tmp/brainify-inbox.bak.*`.
