#!/usr/bin/env python3
"""contacts_photo — 인맥 노트 사진(명함 뒷면·원내 캡처 등) → Google Contacts People API.

인계장 2026-06-23_인맥-contacts-sync-프로토콜화-ai4lt.md 의 R7 코드화 (그동안 contacts_sync.py
docstring 에 "미구현(후속)"으로 남아있던 부분). gog 에 사진 업로드 명령이 없어
access token mint(refresh_token → access_token) 후 People API updateContactPhoto 를 직접 호출한다.

설계 — **성공 확인 후에만 원본 삭제**:
  2026-09-04 KIRAMS 내부 인맥 5명(권우희·서유림·이태걸·전미선·최영민) 캡처 사고의 재발 방지가
  이 스크립트의 존재 이유다. 그 세션은 스크린샷에서 텍스트만 뽑고 사진 업로드 단계 자체를
  실행하지 않은 채 `rm -f` 로 원본을 지워, 사진이 vault·Contacts 어디에도 남지 않았다.
  이 스크립트는 업로드→검증까지 성공했을 때만 원본을 지운다 — 실패하면 원본을 그대로 두고
  에러만 보고하므로 재시도가 항상 가능하다.

  사진 자체는 vault 에 보관하지 않는다(Google Contacts 가 유일한 저장소, 폰 통화 표시용) —
  명함 실물 사진(sources/02_areas/인맥/명함/)과는 성격이 다르다. 업로드 성공 시 노트
  frontmatter `photo: gcontacts` 로만 표시한다.

사용:
  contacts_photo.py <note-stem-or-path> <image-file> [--keep-source]

전제: 노트에 `google_contact_id` 가 이미 있어야 한다(먼저 contacts_sync.py sync --apply 로 생성).
"""
from __future__ import annotations
import argparse
import base64
import json
import os
import pathlib
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

import contacts_sync as cs  # 같은 폴더 — find_note/parse_note/_gog/set_frontmatter_field 재사용


def mint_access_token() -> str:
    """gog 로컬 keyring 의 refresh_token → 단기 access_token(~1h). R7 mint 트릭.
    refresh_token 은 tempdir 안에서만 살고 with 블록 종료 시 자동 삭제 — 시크릿 잔존 방지."""
    with tempfile.TemporaryDirectory() as td:
        tok_path = pathlib.Path(td) / "tok.json"
        r = cs._gog(["auth", "tokens", "export", cs.ACCOUNT, "--out", str(tok_path), "--overwrite"])
        if r.returncode != 0:
            raise RuntimeError(f"gog auth tokens export 실패: {r.stderr.strip()}")
        tok = json.loads(tok_path.read_text(encoding="utf-8"))
        refresh_token = tok.get("refresh_token") or tok.get("refreshToken")
        if not refresh_token:
            raise RuntimeError("refresh_token 없음 — gog auth login 재실행 필요")
        cred_path = pathlib.Path(os.path.expanduser("~/.config/gogcli/credentials.json"))
        cred = json.loads(cred_path.read_text(encoding="utf-8"))
        data = urllib.parse.urlencode({
            "client_id": cred["client_id"],
            "client_secret": cred["client_secret"],
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }).encode("utf-8")
        req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            tok2 = json.loads(resp.read())
        access_token = tok2.get("access_token")
        if not access_token:
            raise RuntimeError(f"access_token 발급 실패: {tok2}")
        return access_token


def upload_photo(cid: str, image_path: pathlib.Path, access_token: str) -> None:
    """PATCH people/{id}:updateContactPhoto. ⚠️ POST 면 HTML 404(라우트 미스, JSON 에러 아님)."""
    photo_bytes = base64.b64encode(image_path.read_bytes()).decode("ascii")
    body = json.dumps({"photoBytes": photo_bytes, "personFields": "photos,names"}).encode("utf-8")
    url = f"https://people.googleapis.com/v1/{cid}:updateContactPhoto"
    req = urllib.request.Request(url, data=body, method="PATCH", headers={
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=60) as resp:
        if resp.status != 200:
            raise RuntimeError(f"updateContactPhoto HTTP {resp.status}")


def verify_photo(cid: str, access_token: str) -> bool:
    """⚠️ gog get 으로 검증 금지 — gog 가 photos 를 readMask 에서 빼 항상 없음으로 오인.
    People API 를 personFields=photos 로 직접 조회해야 실제 상태를 본다."""
    url = f"https://people.googleapis.com/v1/{cid}?personFields=photos"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        d = json.loads(resp.read())
    photos = d.get("photos") or []
    return any(not p.get("default") for p in photos)


def cmd_upload(args) -> int:
    note = cs.find_note(args.note)
    if note is None:
        print(json.dumps({"ok": False, "error": f"인맥 노트 없음: {args.note}"}, ensure_ascii=False))
        return 1
    fm, _sections = cs.parse_note(note)
    cid = (fm.get("google_contact_id") or "").strip()
    if not cid:
        print(json.dumps({"ok": False, "error": "google_contact_id 없음 — 먼저 contacts_sync.py sync --apply 로 Contact 생성"},
                          ensure_ascii=False))
        return 1

    image_path = pathlib.Path(args.image).expanduser()
    if not image_path.exists():
        print(json.dumps({"ok": False, "error": f"이미지 없음: {image_path}"}, ensure_ascii=False))
        return 1

    try:
        access_token = mint_access_token()
        upload_photo(cid, image_path, access_token)
        verified = verify_photo(cid, access_token)
    except (RuntimeError, urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError) as e:
        print(json.dumps({"ok": False, "error": str(e), "source_kept": True}, ensure_ascii=False))
        return 1

    if not verified:
        print(json.dumps({"ok": False, "error": "업로드 후 검증 실패 — photos 필드에 커스텀 사진 없음. 원본 보존.",
                           "source_kept": True}, ensure_ascii=False))
        return 1

    cs.set_frontmatter_field(note, "photo", "gcontacts")
    deleted = False
    if not args.keep_source:
        image_path.unlink()
        deleted = True
    print(json.dumps({"ok": True, "google_contact_id": cid,
                       "note": str(note.relative_to(cs.VAULT)), "source_deleted": deleted},
                      ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="contacts_photo",
                                  description="인맥 노트 사진 → Google Contacts (People API updateContactPhoto)")
    ap.add_argument("note", help="인맥 노트 경로 또는 stem")
    ap.add_argument("image", help="업로드할 이미지 파일 경로")
    ap.add_argument("--keep-source", action="store_true",
                     help="성공해도 원본 이미지를 삭제하지 않음(기본은 성공 확인 후 삭제)")
    ap.add_argument("--account", default="", help="gog 계정 override")
    args = ap.parse_args(argv)
    if getattr(args, "account", ""):
        cs.ACCOUNT = args.account
    return cmd_upload(args)


if __name__ == "__main__":
    sys.exit(main())
