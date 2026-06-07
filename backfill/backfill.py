#!/usr/bin/env python3
"""backfill — 이미 PARA 에 filed 된 사안 폴더를 현 표준으로 *소급 보강*하는 결정형 helper.
판단(어느 thread·diverge vision 보정·누구 링크)은 SKILL.md(에이전트). 여기는 결정형만.
멱등: 전 단계 skip-if-present. 모든 출력 JSON.

서브명령:
  scan   <folder>                 보강 필요 진단(_thread 유무·_parse 누락 소스)
  thread <folder> --thread-id TID 지메일 thread → _thread.md 재구성(gog + build_thread_md)
  parse  <folder> [--engine dual|docling]  소스 ephemeral 파싱(_parse) + 비-diverge refine
재사용: gmail-label-actions/run.py(build_thread_md), brain-pdf(docker), refine.py.
"""
import os, sys, json, subprocess, pathlib, importlib.util, argparse

VAULT = pathlib.Path(os.path.expanduser("~/projects/2nd-brain-vault"))
PARSE_EXT = {".pdf", ".docx", ".doc", ".hwp", ".hwpx", ".pptx", ".ppt"}   # xlsx/xls 제외(정책)
DATA_EXT = {".xlsx", ".xls"}
GLA = os.path.expanduser("~/.openclaw/workspace/skills/gmail-label-actions/run.py")
REFINE = os.path.expanduser("~/.claude/skills/refine/refine.py")
COMPOSE_DIR = os.path.expanduser("~/projects/2nd-brain/docker/2nd-brain-parser")
COMPOSE_FILE = "compose.2nd-brain-parser.yml"
KEYRING_PW = os.path.expanduser("~/.config/gogcli/.keyring-password")
CMNT = "/home/user/projects/2nd-brain-vault"      # 컨테이너 마운트 경로
CONTAINER = "2nd-brain-parser"


def _src_files(folder: pathlib.Path):
    return [f for f in sorted(folder.iterdir())
            if f.is_file() and f.suffix.lower() in PARSE_EXT and not f.name.startswith(".")]


def cmd_scan(args):
    folder = pathlib.Path(args.folder)
    if not folder.is_dir():
        print(json.dumps({"ok": False, "error": f"폴더 아님: {folder}"}, ensure_ascii=False)); return 1
    srcs = _src_files(folder)
    need = [f.name for f in srcs if not (folder / (f.name + "_parse")).exists()]
    xlsx = [f.name for f in folder.iterdir() if f.suffix.lower() in DATA_EXT]
    print(json.dumps({
        "folder": str(folder.relative_to(VAULT)) if folder.is_relative_to(VAULT) else str(folder),
        "_thread.md": (folder / "_thread.md").exists(),
        "sources": [f.name for f in srcs],
        "need_parse": need,
        "xlsx_skipped": xlsx,          # 정책상 _parse 불요
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_thread(args):
    """threadId → gog thread get → build_thread_md → <folder>/_thread.md. 멱등(있으면 skip)."""
    folder = pathlib.Path(args.folder); out = folder / "_thread.md"
    if out.exists() and not args.force:
        print(json.dumps({"ok": True, "skipped": "_thread.md 이미 있음"}, ensure_ascii=False)); return 0
    os.environ["GMAIL_ROUTER_ACCOUNT"] = args.account                 # gla 모듈 import 전 필수
    if os.path.exists(KEYRING_PW) and not os.environ.get("GOG_KEYRING_PASSWORD"):
        os.environ["GOG_KEYRING_PASSWORD"] = open(KEYRING_PW).read().strip()
    sys.argv = ["run.py"]                                            # gla main 가드 회피
    spec = importlib.util.spec_from_file_location("gla", GLA)
    gla = importlib.util.module_from_spec(spec); spec.loader.exec_module(gla)
    res = gla.gog_json("gmail", "thread", "get", args.thread_id, "--full", results_only=False, timeout=60)
    thread = res.get("thread", {}) if isinstance(res, dict) else {}
    if not thread.get("messages"):
        print(json.dumps({"ok": False, "error": "thread 수신 실패(키링/계정/tid 확인)"}, ensure_ascii=False)); return 1
    out.write_text(gla.build_thread_md(thread, args.thread_id), encoding="utf-8")
    print(json.dumps({"ok": True, "note": str(out), "message_count": len(thread["messages"])}, ensure_ascii=False))
    return 0


def _dexec(*a, timeout=900):
    return subprocess.run(["docker", "exec", CONTAINER, *a], capture_output=True, text=True, timeout=timeout)


def _cpath(p: pathlib.Path):
    return f"{CMNT}/{p.relative_to(VAULT)}"


def cmd_parse(args):
    """폴더 소스 ephemeral 파싱: docling[+mineru+diff(pdf,dual)] → 비-diverge 자동 refine.
    diverge PDF 는 refined.md 미작성 → SKILL.md(에이전트)가 vision 보정. 멱등(sentinel 존재 skip)."""
    folder = pathlib.Path(args.folder); srcs = _src_files(folder)
    if not srcs:
        print(json.dumps({"ok": True, "note": "파싱대상 없음(xlsx 등 제외)"}, ensure_ascii=False)); return 0
    env = dict(os.environ, SB_DATA=str(VAULT))
    subprocess.run(["docker", "compose", "-f", COMPOSE_FILE, "up", "-d", CONTAINER],
                   cwd=COMPOSE_DIR, env=env, capture_output=True, text=True)
    results = []
    try:
        for f in srcs:
            pdir = folder / (f.name + "_parse")
            is_pdf = f.suffix.lower() == ".pdf"
            dual = is_pdf and args.engine == "dual"
            sentinel = pdir / ("diff.json" if dual else "docling.json")
            if sentinel.exists():
                results.append({"file": f.name, "status": "skip(이미)"}); continue
            pdir.mkdir(exist_ok=True)
            r = _dexec("brain-pdf", "parse-docling", _cpath(f))
            if r.returncode != 0 or not r.stdout:
                (pdir / ".parse-error").write_text((r.stderr or "")[-500:])
                results.append({"file": f.name, "status": "FAIL docling"}); continue
            (pdir / "docling.json").write_text(r.stdout, encoding="utf-8")
            engines = "docling"
            if dual:
                rm = _dexec("brain-pdf", "parse-mineru", _cpath(f))
                if rm.returncode == 0 and rm.stdout:
                    (pdir / "mineru.json").write_text(rm.stdout, encoding="utf-8"); engines = "docling+mineru"
                    rd = _dexec("brain-pdf", "diff", _cpath(pdir / "docling.json"), _cpath(pdir / "mineru.json"))
                    if rd.returncode == 0 and rd.stdout:
                        (pdir / "diff.json").write_text(rd.stdout, encoding="utf-8")
            # refine: verdict 확인 → match/single 자동 promote, diverge 는 에이전트 몫
            rd = subprocess.run(["python3", REFINE, "read", str(pdir)], capture_output=True, text=True)
            verdict = "single"
            try:
                verdict = json.loads(rd.stdout).get("verdict", "single")
            except Exception:
                pass
            if verdict in ("match", "single"):
                subprocess.run(["python3", REFINE, "promote", str(pdir)], capture_output=True, text=True)
            results.append({"file": f.name, "status": "parsed", "engines": engines,
                            "verdict": verdict, "refined": (pdir / "refined.md").exists(),
                            "needs_vision_refine": verdict == "diverge"})
    finally:
        subprocess.run(["docker", "compose", "-f", COMPOSE_FILE, "down"],
                       cwd=COMPOSE_DIR, env=env, capture_output=True, text=True)
    print(json.dumps({"ok": True, "results": results}, ensure_ascii=False, indent=2)); return 0


def main():
    ap = argparse.ArgumentParser(prog="backfill", description="filed 사안 폴더 소급 보강(결정형)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ps = sub.add_parser("scan"); ps.add_argument("folder")
    pt = sub.add_parser("thread"); pt.add_argument("folder")
    pt.add_argument("--thread-id", required=True); pt.add_argument("--account", default="kimbi.kirams@gmail.com")
    pt.add_argument("--force", action="store_true")
    pp = sub.add_parser("parse"); pp.add_argument("folder")
    pp.add_argument("--engine", choices=["dual", "docling"], default="dual")
    a = ap.parse_args()
    return {"scan": cmd_scan, "thread": cmd_thread, "parse": cmd_parse}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
