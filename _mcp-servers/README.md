# _mcp-servers — User-scope MCP inventory

`~/.claude.json` 의 *user-scope* `mcpServers` 를 양 PC (ai4lt·kimbi) 사이 GitHub 동기하는 인벤토리.

## 왜 user scope + GitHub 인가

vault `.mcp.json` (project scope) 도 SyncThing 으로 양 PC 동기되지만, 모든 MCP 가 vault 작업과 결합하는 건 아니다 — *vault 밖 ad hoc 분석* (외부 hwp 파일 즉시 보기 등) 에서도 사용하려면 user scope 가 자연스럽다. Skill 동기 채널(GitHub)에 통합하면 *Skill 류 = GitHub, 데이터 = SyncThing* 의 단순 모델로 정렬된다.

상세 근거 → 메모리 [[project_mcp_server_registration_pattern]].

## 구조

```
~/.claude/skills/_mcp-servers/
├── registry.json   ← 서버 정의 single source of truth (git-tracked)
├── apply.sh        ← registry → ~/.claude.json user-scope mcpServers writeback (멱등)
└── README.md       ← 이 파일
```

## 동기 흐름

```
ai4lt 에서 registry.json 갱신
    → git commit & push (BenKorea/claude-code-skills)
        → kimbi 에서 git pull
            → bash apply.sh (자동 — /git-routine pull 안에 통합)
                → kimbi 의 ~/.claude.json user-scope 정합
```

→ Skill 의 *디스크 파일 = 자동 등록* 모델을 *MCP 의 키 writeback* 으로 한 단계 매개. 사용자 체감상 자동.

## 운영

### MCP 추가

1. `registry.json` 의 `mcpServers` 에 새 entry
2. `git commit -m "mcp: add <name>"` + push
3. 자기 PC 에서 `bash apply.sh` (또는 `/git-routine pull` 안에 자동)
4. `claude mcp list` 로 확인

### MCP 갱신

registry.json 의 spec 만 수정 → apply.sh 가 자동 *remove + re-add* (멱등).

### MCP 삭제

1. registry.json 에서 entry 제거 → push
2. 다른 PC 에서 apply.sh 가 *orphan 경고* 출력 (수동 제거 권장 — `claude mcp remove <name>`)
3. 자동 제거 안 함 (안전 원칙 — 일시 등록 mcp 가 우발 제거되지 않도록)

## apply.sh 동작

- **target** (registry 의 서버) 순회:
  - user-scope 에 없음 → `claude mcp add-json --scope user <name> <json>` (✓ added)
  - 있음 + spec 동일 → skip (= unchanged)
  - 있음 + spec 다름 → remove + re-add (↻ updated)
- **current** (user-scope) 순회:
  - registry 에 없는 서버 → orphan 경고만 (자동 제거 X)
  - `claude.ai *` 패턴 (Anthropic OAuth connector) → skip

## scope 분류 가이드

| MCP 성격 | scope |
|---|---|
| **vault 작업 결합** (예: vault 전용 검색 인덱스) | vault `.mcp.json` (project) |
| **범용·어디서나** (hwp-mcp·hwp-thesis-mcp·검색·DB) | **user (이 registry)** |

## 양 PC 셋업 (새 머신 첫 도입 시)

```bash
# /git-routine 등으로 ~/.claude/skills 동기 후
bash ~/.claude/skills/_mcp-servers/apply.sh
claude mcp list
```

## Prereq — 머신별 런타임

`.mcp.json` 과 마찬가지로 *registry.json* 자체는 동기되지만, *각 MCP 의 런타임 prereq* 는 머신마다 설치.

### Linux/WSL2 측 MCP (예: `hwp-mcp`)

- `uvx` (Python MCP) — `curl -LsSf https://astral.sh/uv/install.sh | sh`

### Windows COM MCP (향후 도입 시 참고)

WSL2 의 interop 을 통해 Windows 측 실행 파일을 직접 호출 가능. 일반 패턴:

1. Windows 측 **한컴오피스** 설치 가정
2. Windows 측 **Python 3.10+** (Dr. Ben 환경 = scoop python312)
3. **`pip install <hwp-mcp-package>`** 로 console_script 진입점 PATH 등록
4. registry.json 에 `{"command":"bash","args":["-c","exec <name>.exe 2>&1"]}` 형태 등록
   - `bash -c "... 2>&1"` wrapper 가 필요한 패키지: MCP 서버가 stdout 이 아닌 stderr 로 JSON-RPC 응답 보내는 케이스 (예: `hwp-thesis-mcp` v1.27.2)
   - 정상 패키지는 wrapper 불필요 — `{"command":"<name>.exe"}` 단순

prereq 누락 시 `claude mcp list` 에 spawn 실패 표시 → 그 머신에만 설치.

> ⚠️ Windows COM MCP 도입 전 *패키지가 실제 용도에 부합하는지* 도구 명세 확인 필수. 예: `hwp-thesis-mcp` 는 *학위논문 전용* (도구 = `convert_thesis`, preset = `ssu_masters/phd`), R&D 기획보고서 양식 등 *일반 양식 부적합*. 2026-05-30 시행착오 → 변경이력 참조.

## 변경 이력

- 2026-05-30 — 신설. hwp-mcp 가 vault project (`.mcp.json`) 에서 user scope 로 이전. 결정 근거 → 메모리 [[project_mcp_server_registration_pattern]] (서브섹션 *Skill 모델 vs MCP 의 구조적 차이*).
- 2026-05-30 — **hwp-thesis (Windows COM MCP) 추가 후 같은 날 제거**. WSL2 interop + Windows scoop python312 + bash wrapper (stderr→stdout) 로 연결 검증 ✓. 그러나 도구 명세 실측 결과 *학위논문 전용* (`convert_thesis`, preset = `ssu_masters/phd`, schema = 숭실대 논문 규격) — R&D 기획보고서 양식 (KIRAMS·KSNM·KARP 등) 에 부적합. 인프라(WSL2 interop·wrapper 패턴)는 *유효한 자산* — 향후 *범용 한컴 MCP* (예: hwpapi 기반 직접 작성) 도입 시 같은 패턴 재사용. 회고 → 메모리 [[project_mcp_server_registration_pattern]] §Windows COM MCP 시행착오.
