# claude-code-skills

Dr. Ben의 Claude Code (WSL2 CLI) 공용 스킬 정의.

## 배치 규칙

각 스킬은 하위 폴더 하나로:
```
skills/
├── 스킬명/
│   ├── SKILL.md              이 스킬의 지침서
│   └── (보조 스크립트·데이터)
```

파일명·폴더명이 스킬 이름이 됨. Claude Code (`~/.claude/skills/`)가 이 폴더를 직접 읽음.

Claude Desktop 쪽 스킬(`skills-plugin`)과는 **별도 체계**. Code 에서만 사용.

## 새 머신 onboarding (WSL2)

기존에 `~/.claude/skills` 가 Google Drive symlink 였다면 끊고 git clone 으로 대체:

```bash
# 1. 기존 symlink 제거 (실제 디렉토리면 백업 후 제거)
rm ~/.claude/skills

# 2. 이 repo 를 직접 clone
git clone https://github.com/BenKorea/claude-code-skills.git ~/.claude/skills
```

검증:
```bash
ls -la ~/.claude/skills          # symlink 가 아닌 디렉토리여야 함
git -C ~/.claude/skills status   # repo 인식 확인
```

## 자매 repo

- [claude-code-commands](https://github.com/BenKorea/claude-code-commands) — `/...` 슬래시 커맨드. 동일 onboarding 절차.

## 관련 자산 (이 repo 밖)

- `~/.claude/CLAUDE.md` — 사용자 전역 지침. 직접 파일로 관리 (symlink·git 미사용).
- `~/.claude/settings.json` — device-specific. Google Drive `claude-config/device/<host>.json` 에서 직접 복사하여 실파일로 사용 (symlink 제거).
