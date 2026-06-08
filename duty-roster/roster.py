#!/usr/bin/env python3
"""duty-roster helper — 핵의학과 온콜당직표 xlsx → Google Calendar 멱등 동기.

외부 의존성 0 (stdlib zipfile/xml 로 xlsx 파싱). gog 로 calendar 쓰기.

서브커맨드
  plan  <xlsx> [--name N]                  부작용 없이 추출 결과(JSON plan) 출력
  sync  <xlsx> [--name N] [--account A] [--dry-run]
        해당 월 마커 이벤트 멱등 동기 (기존 마커분 삭제 후 재생성) — 매달 재실행 안전

열 의미 (헤더명으로 매칭 — 열 위치 이동에 견고)
  당직일자   → 날짜(Excel serial)
  당직의사명 → On Call           08:50–11:00
  PET        → PET판독           10:00–17:30
  PET외      → 감마판독          10:00–17:30
  병동       → 병동당직          당일 08:30 ~ 익일 08:30

멱등 마커: private extended property  duty_roster=<YYYY-MM> (+ duty_type=<type>)
"""
import sys, os, json, zipfile, argparse, subprocess
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
DEFAULT_NAME = "김병일"          # Dr. Ben (LinkedIn byung-il-kim, gog kimbi, 사번 1903). 본인 이름 바뀌면 여기만.
DEFAULT_ACCOUNT = "kimbi.kirams@gmail.com"
TZ = "+09:00"

# 업무유형: (헤더명, summary, 시작HH:MM, 종료HH:MM, 익일종료?)
DUTIES = [
    ("당직의사명", "On Call",  "oncall", "08:50", "11:00", False),
    ("PET",       "PET판독",  "pet",    "10:00", "17:30", False),
    ("PET외",     "감마판독", "gamma",  "10:00", "17:30", False),
    ("병동",      "병동당직", "ward",   "08:30", "08:30", True),
]


def _colnum(ref):
    c = "".join(ch for ch in ref if ch.isalpha())
    n = 0
    for ch in c:
        n = n * 26 + (ord(ch) - 64)
    return n


def read_grid(xlsx):
    """xlsx → {row:{col:value}} 그리드 (1-based)."""
    z = zipfile.ZipFile(xlsx)
    sst = []
    try:
        r = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in r.findall(NS + "si"):
            sst.append("".join(t.text or "" for t in si.iter(NS + "t")))
    except KeyError:
        pass
    # 첫 워크시트 경로
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    sheet_path = "xl/worksheets/sheet1.xml"
    ws = ET.fromstring(z.read(sheet_path))
    grid = {}
    for row in ws.iter(NS + "row"):
        rn = int(row.get("r"))
        for c in row.findall(NS + "c"):
            ref, t = c.get("r"), c.get("t")
            v, isn = c.find(NS + "v"), c.find(NS + "is")
            val = ""
            if t == "s" and v is not None:
                val = sst[int(v.text)]
            elif t == "inlineStr" and isn is not None:
                val = "".join(x.text or "" for x in isn.iter(NS + "t"))
            elif v is not None:
                val = v.text
            grid.setdefault(rn, {})[_colnum(ref)] = (val or "").strip()
    return grid


def find_header(grid):
    """'당직일자' + '당직의사명' 이 같은 행에 있는 헤더행을 찾아 (행번호, {헤더:열}) 반환."""
    for rn in sorted(grid):
        cells = grid[rn]
        names = {v: ci for ci, v in cells.items()}
        if "당직일자" in names and "당직의사명" in names:
            return rn, names
    raise SystemExit("헤더행(당직일자·당직의사명)을 찾지 못함 — xlsx 형식 확인 필요")


def serial_to_date(s):
    try:
        n = int(float(s))
    except (ValueError, TypeError):
        return None
    if n < 40000:                      # 2009 이전이면 날짜 셀 아님
        return None
    return date(1899, 12, 30) + timedelta(days=n)


def extract(xlsx, name):
    grid = read_grid(xlsx)
    hrow, hmap = find_header(grid)
    date_col = hmap["당직일자"]
    events, months = [], {}
    for rn in sorted(grid):
        if rn <= hrow:
            continue
        cells = grid[rn]
        d = serial_to_date(cells.get(date_col, ""))
        if d is None:
            continue
        for header, summary, typ, t1, t2, nextday in DUTIES:
            col = hmap.get(header)
            if col is None:
                continue
            if cells.get(col, "") == name:
                end_d = d + timedelta(days=1) if nextday else d
                frm = f"{d.isoformat()}T{t1}:00{TZ}"
                to = f"{end_d.isoformat()}T{t2}:00{TZ}"
                events.append({"summary": summary, "type": typ,
                               "from": frm, "to": to, "day": d.isoformat()})
                months[d.strftime("%Y-%m")] = months.get(d.strftime("%Y-%m"), 0) + 1
    events.sort(key=lambda e: (e["from"], e["summary"]))
    month = max(months, key=months.get) if months else None
    return {"month": month, "name": name, "count": len(events), "events": events}


# ---------- gog calendar I/O ----------

def _gog_env():
    env = dict(os.environ)
    if "GOG_KEYRING_PASSWORD" not in env:
        p = os.path.expanduser("~/.config/gogcli/.keyring-password")
        if os.path.isfile(p):
            env["GOG_KEYRING_PASSWORD"] = open(p).read().strip()
    return env


def _gog(args, account):
    cmd = ["gog", "calendar"] + args + ["-a", account]
    return subprocess.run(cmd, capture_output=True, text=True, env=_gog_env())


def list_marker(month, account):
    """해당 월 마커 이벤트 ID 목록 (--all-pages)."""
    m = datetime.strptime(month, "%Y-%m")
    nm = (m.replace(day=28) + timedelta(days=7)).replace(day=1)
    r = _gog(["list", "primary", "--from", m.strftime("%Y-%m-01"),
              "--to", nm.strftime("%Y-%m-01"),
              "--private-prop-filter", f"duty_roster={month}",
              "--all-pages", "-j", "--results-only"], account)
    if r.returncode != 0:
        raise SystemExit(f"gog list 실패: {r.stderr.strip() or r.stdout.strip()}")
    try:
        data = json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return []
    evs = data if isinstance(data, list) else (data.get("events") or data.get("items") or [])
    return [e.get("id") for e in evs if e.get("id")]


def sync(xlsx, name, account, dry_run):
    plan = extract(xlsx, name)
    month = plan["month"]
    if not month:
        print(json.dumps({"error": "해당 이름의 당직 없음", "name": name}, ensure_ascii=False))
        return 0
    desc = (f"{month} 핵의학과 온콜당직표 기준 자동 생성 "
            f"(출처: {os.path.basename(xlsx)}) — duty-roster skill")

    existing = list_marker(month, account)
    actions = {"month": month, "name": name, "delete": len(existing),
               "create": plan["count"], "dry_run": dry_run, "results": []}

    if dry_run:
        actions["events"] = plan["events"]
        print(json.dumps(actions, ensure_ascii=False, indent=2))
        return 0

    # 1) 기존 마커분 삭제 (멱등 재실행)
    for eid in existing:
        r = _gog(["delete", "primary", eid, "--scope", "all", "--force"], account)
        if r.returncode != 0:
            actions["results"].append({"delete": eid, "ok": False, "err": r.stderr.strip()})
    # 2) 재생성
    ok = 0
    for e in plan["events"]:
        r = _gog(["create", "primary", "--summary", e["summary"],
                  "--from", e["from"], "--to", e["to"],
                  "--private-prop", f"duty_roster={month}",
                  "--private-prop", f"duty_type={e['type']}",
                  "--description", desc, "-p"], account)
        if r.returncode == 0:
            ok += 1
        else:
            actions["results"].append({"create": e["summary"] + " " + e["day"],
                                       "ok": False, "err": r.stderr.strip()})
    actions["created_ok"] = ok
    actions["created_fail"] = plan["count"] - ok
    print(json.dumps(actions, ensure_ascii=False, indent=2))
    return 0 if ok == plan["count"] else 1


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan");  p.add_argument("xlsx"); p.add_argument("--name", default=DEFAULT_NAME)
    s = sub.add_parser("sync");  s.add_argument("xlsx"); s.add_argument("--name", default=DEFAULT_NAME)
    s.add_argument("--account", default=DEFAULT_ACCOUNT); s.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.cmd == "plan":
        print(json.dumps(extract(a.xlsx, a.name), ensure_ascii=False, indent=2))
        return 0
    return sync(a.xlsx, a.name, a.account, a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
