---
name: webmail-demo
description: KIRAMS webmail 자동로그인을 headed 브라우저로 시연한다(교육용). "kirams webmail 자동로그인 시연해줘", "웹메일 로그인 데모 보여줘", "/webmail-demo" 류 트리거. prod 타이머 정지 → 프로필 권한 → headed bootstrap(toml ID/PW/OTP 자동주입) → 타이머 복구를 한 번에 처리. Game Bar 등으로 화면 녹화 가능.
---

# webmail-demo — KIRAMS 자동로그인 시연

교육과정에서 "자동화가 외부 forwarding/IMAP 이 막힌 기관 webmail 에 자동으로 로그인하는" 모습을 headed 브라우저로 시연한다. 실행 본체는 `webmail-watch` 의 `--bootstrap`(로그인까지만, 실제 메일 forward/move 없음)이고, 본 스킬은 그 시연을 한 번에 돌리는 래퍼다.

## 트리거

"kirams webmail 자동로그인 시연해줘", "웹메일 로그인 데모 보여줘", "/webmail-demo" 등.

## 실행

래퍼 스크립트를 **백그라운드로** 실행한다 (headed 창이 떠서 시연 — 사람이 창을 닫을 때까지 유지되므로 foreground 로 돌리면 턴이 블록됨):

```bash
bash ~/.openclaw/workspace/skills/webmail-watch/scripts/demo-auto.sh
```

스크립트가 4단계를 자동 처리:

1. prod webmail 타이머(`openclaw-webmail-sidecar.timer`) 정지 — 시연 중 자동발화·프로필 root 재생성 방지
2. `chrome-profile/kirams` 권한을 uid 1000 으로 (NOPASSWD `sudo chown`)
3. headed bootstrap — toml ID/PW/OTP 자동주입 → 로그인 → 받은편지함 도달. **실제 메일 forward/move 없음**
4. 창 닫히면(또는 에러) prod 타이머 복구 (`trap` 으로 보장)

실행 후 Dr. Ben 에게: 창이 뜨면 자동로그인이 진행되며, 화면 녹화는 Game Bar 로, 끝나면 창을 닫으면 타이머가 자동 복구된다고 안내.

## 전제 (머신마다 1회 셋업)

`sudo chown` 을 비대화식(스킬·cron)에서 돌리려면 그 한 명령만 비번 면제하는 NOPASSWD 규칙이 필요하다:

```
# /etc/sudoers.d/webmail-demo  (chmod 440)
ben ALL=(root) NOPASSWD: /usr/bin/chown -R 1000\:1000 /home/ben/.openclaw/skills/webmail-watch/chrome-profile/kirams
```

- 딱 이 chown 명령만 비번 면제 — 다른 sudo 는 그대로 비번 요구(보안 위험 작음).
- 없으면 2단계에서 sudo 비번 프롬프트 → 스킬(비대화식) 실패. 이 경우 Dr. Ben 이 **대화형 터미널에서 직접** `demo-auto.sh` 실행(비번 입력 가능).
- 이 규칙은 머신로컬(`/etc/sudoers.d/`) — 동기 안 됨. 노트북 등 다른 PC 에서 시연하려면 그 PC 에 1회 설치.

## 녹화

headed 창이라 화면 녹화로 캡처:
- **Game Bar**: Chrome 창 활성화 후 `Win+Alt+R` (단일 창). 결과 `C:\Users\<user>\Videos\Captures\*.mp4`
- **Win11 캡처도구**: 영역 지정 녹화 — 터미널 로그 + 브라우저를 함께 담을 때
- **자동 webm**: `run.py` 의 `open_context`(run.py:160)에 `record_video_dir` 추가 시 Playwright 가 자동 녹화

## 주의

- **시연 품질**: 직전 발화로 세션 쿠키가 살아있으면 로그인 폼 대신 받은편지함이 바로 뜰 수 있다 — ID/PW 자동주입 장면을 꼭 보이려면 fresh 프로필 필요.
- **prod 무결성**: 시연 동안 prod webmail 이 멈춰있고(4단계 trap 복구로 시연 끝나면 자동 재개). 시연이 비정상 종료해도 trap 이 타이머를 되살림.
- **권위**: webmail-watch 본체 = `~/.openclaw/workspace/skills/webmail-watch/SKILL.md`. 본 스킬은 그 `--bootstrap` 의 교육 시연 래퍼일 뿐.
