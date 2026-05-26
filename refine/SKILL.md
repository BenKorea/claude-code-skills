---
name: refine
description: >-
  2nd-brain-parser 의 post 단계 — extract(parser-drain)가 만든 _parse/{docling,mineru,diff}.json
  을 읽어 단일 권위 풀텍스트 refined.md 를 만든다. verdict=match/single 은 docling 자동승격(LLM 0),
  verdict=diverge 만 두 파서 출력을 원본 PDF 비전검증으로 보정. "파싱 검증해줘", "refined 만들어줘",
  "/refine" 류 트리거. 파싱이 끝난 _parse 를 받아 refined.md 까지가 이 스킬의 경계 — 그 다음 PARA·노트화는 brainify.
allowed_tools: [bash, read, write]
---

# refine — 2nd-brain-parser post (듀얼 파서 → 정제본)

**파싱 파이프라인의 비결정형 후단**. extract(2nd-brain-parser 컨테이너 + parser-drain host timer)가
PDF 를 docling·mineru 로 파싱하고 diff 까지 떠 `_parse/{docling,mineru,diff}.json` 을 남기면,
이 스킬이 **두 출력을 하나의 권위 풀텍스트 `refined.md` 로 정제**한다. 그 뒤 PARA 분류·동반 노트는
[[brainify]] 가 `refined.md` 만 소비해 처리한다 (역할 경계: refine=원본충실 정제, brainify=인지·연결).

- **결정형 메커니즘은 `refine.py`** (스캔·읽기·승격·쓰기)에 위임. 이 문서는 **판단(diverge 시 어느 파서가
  원본에 맞는지 비전검증·보정)** 만 한다.
- 외부 OCR API 0 — 파싱은 로컬 전용 컨테이너(extract)가 이미 끝냈고, refine 은 그 *텍스트 2개*를 비교·보정.
  민감자료 leak 경계는 extract 가 지킴(원본 PDF 를 클라우드에 안 보냄). 보정 판단은 brainify 요약과 동일 신뢰면.

helper 는 `python3 ~/.claude/skills/refine/refine.py <subcommand>` (출력 JSON).

## 절차 (`/refine`)

### 1. scan

`refine.py scan` — `00_inbox/` 아래 `*_parse/` 중 **`refined.md` 없는** 것을 나열. 각 항목의
`verdict`(diff.json)·`needs_llm`·`action` 을 받는다. (`--root <dir>` 로 범위 변경 가능 — 예: 백필.)

- `pending: 0` → "정제할 _parse 없음" 보고 후 종료.
- `status: no-extract` (docling.json 없음) → extract 미완/실패. parser-drain 로그 안내하고 그 항목 skip.

### 2. 항목별 분기 (verdict 게이트)

**a) `match` / `single` → 결정형 승격 (LLM 0).**
`refine.py promote "<parse_dir>"`. docling markdown 을 그대로 `refined.md` 로 승격(두 파서가
임계 내 일치하거나, 비-PDF 라 비교 대상이 없음). 비전검증 생략 — 빠르고 비용 0.

**b) `diverge` → 비전검증 후 보정 (이 스킬의 핵심 판단).**

1. `refine.py read "<parse_dir>"` — `verdict`·`metrics`·`details`(`headings_only_in_a`=docling /
   `headings_only_in_b`=mineru / `numeric_mismatches`) + 두 markdown(`docling.markdown`·`mineru.markdown`)
   + `source_abs`(원본 파일 경로).
2. **diff 가 가리키는 충돌 지점**(불일치 heading·숫자)을 좁혀, 그 부분을 **원본 PDF 를 `Read` 도구로 직접
   비전 해석**해 어느 파서가 맞는지 확인. (Claude Code 의 Read 는 PDF 멀티모달.) 숫자·식별자·표는 *반드시*
   원본 대조 — 파서 오인식(하이픈 누락·셀 오정렬·CJK 글리프)을 여기서 잡는다.
3. **정제본 본문 작성** — 두 출력의 강점만 취한다(보통 구조·표는 docling 이 깔끔, 일부 식별자·이스케이프는
   mineru 가 정확). 원본 PDF 의 *모든* 내용을 담은 풀텍스트 markdown 을 임시파일(예 `/tmp/refined-body.md`)에.
   요약하지 말 것 — refined 는 원본 충실 재현(요약은 brainify 가 동반 노트에서).
4. `refine.py write "<parse_dir>" --base-engine <docling|mineru|merged|vision> --body-file /tmp/refined-body.md
   --correction "<보정사유1>" --correction "<…>" [--confidence low]`.
   helper 가 frontmatter(`source_pdf`·`base_engine`·`corrections`·`generated`·`host`·`refine_confidence`)
   + 본문을 `_parse/refined.md` 에 쓴다.

> verdict=diverge 는 **보수적**이다(임계 heading_overlap≥0.8). 숫자·표가 100% 일치인데 heading 표기
> 차이만으로 diverge 가 흔하다 — 그런 회차는 비전검증으로 *데이터 동일* 확인 후 docling 채택 + corrections
> 에 "heading 표기차, 데이터 일치" 1줄. fan-out 방지: **턴당 1문서**씩.

### 3. 보고

처리 표: parse_dir → verdict → 채택 엔진 → corrections 수 → refined.md 경로. 다음 단계로
`/brainify`(refined.md 소비 → PARA·노트) 안내.

## 모드 — 비전검증 불가/실패

- 원본 PDF 가 스캔 이미지라 두 파서 모두 빈 추출이면 → `Read` 로 페이지를 직접 비전 판독해 핵심만
  재구성, `--base-engine vision` + `--confidence low`. (구 brainify-inbox 가 회계감사보고서 50p 에서 쓴 경로.)
- docling.json 자체가 없으면(extract 실패) refine 불가 — skip 하고 parser-drain 재실행 안내.

## 제약

- **정본 vault 는 WSL2 ext4 `~/projects/2nd-brain-vault`** — git 아님(SyncThing). commit 하지 않음.
- `refined.md` 존재 = refine 완료(멱등 마커). 재실행은 done 을 skip — 덮어쓰려면 `promote --force`.
- 원본·raw JSON 불변: `_parse/{docling,mineru,diff}.json` 과 원본 파일은 건드리지 않고 `refined.md` 만 추가.
- refined.md frontmatter 규약은 **brainify-inbox §3 계승** — 바꾸지 말 것(vault 에 기존 refined.md 다수).

## 관련

- extract(전단): `~/projects/2nd-brain/docker/parser-drain/` + `2nd-brain-parser` 컨테이너.
- 전략·watchdog 경계: `~/projects/2nd-brain/docs/2nd-brain-parser-strategy.md` (Phase 3 = Claude Code, 게이트웨이 밖).
- brainify(후단): `~/.claude/skills/brainify/` — refined.md → PARA·동반 노트.
- 규약 출처: `~/.claude/skills/brainify-inbox/` (구 통합 스킬, refine 로직 원본 — refine+brainify 로 분리됨).
