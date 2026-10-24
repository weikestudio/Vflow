#!/usr/bin/env python3
"""内容日历与系列化：把"这条之后发什么"排出来，让系列互相带流量。

为什么需要：单条流水线只能保证"这一条不差"，系列化才能提高**复访率**——
2026 年平台权重第二的就是复访。观众看完一条会去找同系列的其他条，
这需要你在结构上留了引用、在标题上用了同系列词。

用法：
    python3 content_calendar.py series add "AI 工具怎么选" --goal 4 --start 2026-11-02 --end 2026-11-23 --note "判断1+方法2+实录1"
    python3 content_calendar.py series list
    python3 content_calendar.py series kill S1 --why "方向改了"
    python3 content_calendar.py plan "换工具最贵的是重讲业务" --date 2026-11-02 --platform douyin --track 发现轨 --series S1
    python3 content_calendar.py list [--series S1] [--status 待做|已排|已发]
    python3 content_calendar.py week [--offset 0]        本周排期
    python3 content_calendar.py due [--days 3]           到期未完成的
    python3 content_calendar.py start "<关键词>"          从排期开项目，回填 slug
    python3 content_calendar.py done "<关键词>"           标记已发
    python3 content_calendar.py check                    冲突检查（同平台同日多条 / 系列不完整）

数据真源：`calendar.md`（人可以直接编辑）。状态：待做 → 已排（已开项目）→ 已发。

零依赖。
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

ROOT = os.path.abspath(
    os.environ.get("VFLOW_HOME") or os.path.expanduser("~/Vflow"))
CAL = os.path.join(ROOT, "calendar.md")
STATUSES = ["待做", "已排", "已发", "砍掉"]
TRACKS = ["发现轨", "深度轨"]

HEADER = """# 内容日历

> 排期不是为了"逼自己发"，是为了**让系列互相带流量**。
> 同一系列 3–5 条，标题用同一组系列词，正文里互相引用——这是复访率的来源。
>
> 用法：`python3 scripts/content_calendar.py week` 看本周，`content_calendar.py due` 看到期没做的。
> 状态：待做 → 已排（已开项目）→ 已发。砍掉要写原因。

## 系列

| 系列 | 主题 | 目标条数 | 起止 | 状态 | 说明 |
|---|---|---|---|---|---|

## 排期

| 日期 | 平台 | 轨道 | 选题 | 系列 | 状态 | 项目 |
|---|---|---|---|---|---|---|
"""


def read(p):
    try:
        with open(p, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def ensure():
    if not os.path.isfile(CAL):
        with open(CAL, "w", encoding="utf-8") as fh:
            fh.write(HEADER)


def parse_section(text, title):
    m = re.search(r"^## %s\s*$" % re.escape(title), text, re.M)
    if not m:
        return []
    start = m.end()
    nxt = re.search(r"^## ", text[start:], re.M)
    chunk = text[start:start + nxt.start()] if nxt else text[start:]
    rows = []
    for line in chunk.split("\n"):
        if not line.startswith("|") or "---" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        rows.append(cells)
    return rows[1:] if rows else []


def parse():
    ensure()
    text = read(CAL)
    series = []
    for c in parse_section(text, "系列"):
        if len(c) >= 6 and c[0] and c[0] != "系列":
            series.append({"id": c[0], "topic": c[1], "goal": c[2],
                           "range": c[3], "status": c[4], "note": c[5]})
    plans = []
    for c in parse_section(text, "排期"):
        if len(c) >= 7 and c[0] and c[0] != "日期":
            plans.append({"date": c[0], "platform": c[1], "track": c[2],
                          "title": c[3], "series": c[4], "status": c[5],
                          "slug": c[6] if c[6] != "—" else ""})
    return series, plans


def save(series, plans):
    head = read(CAL)
    prefix = head.split("## 系列")[0] if "## 系列" in head else HEADER.split("## 系列")[0]
    lines = ["## 系列", "",
             "| 系列 | 主题 | 目标条数 | 起止 | 状态 | 说明 |",
             "|---|---|---|---|---|---|"]
    for s in series:
        lines.append("| %s | %s | %s | %s | %s | %s |" % (
            s["id"], s["topic"], s["goal"], s["range"], s["status"], s["note"]))
    lines += ["", "## 排期", "",
              "| 日期 | 平台 | 轨道 | 选题 | 系列 | 状态 | 项目 |",
              "|---|---|---|---|---|---|---|"]
    for p in plans:
        lines.append("| %s | %s | %s | %s | %s | %s | %s |" % (
            p["date"], p["platform"], p["track"], p["title"],
            p["series"] or "—", p["status"], p["slug"] or "—"))
    with open(CAL, "w", encoding="utf-8") as fh:
        fh.write(prefix.rstrip() + "\n\n" + "\n".join(lines) + "\n")


def today():
    return date.today()


def parse_date(s):
    for f in ("%Y-%m-%d", "%Y/%m/%d", "%m-%d"):
        try:
            d = datetime.strptime(s, f)
            if f == "%m-%d":
                d = d.replace(year=today().year)
            return d.date()
        except ValueError:
            continue
    return None


def find_plan(plans, key):
    exact = [p for p in plans if p["title"] == key]
    if exact:
        return exact[0]
    hit = [p for p in plans if key in p["title"]]
    if len(hit) > 1:
        return {"error": "有 %d 条都匹配「%s」：%s" % (
            len(hit), key, "、".join(p["title"] for p in hit))}
    return hit[0] if hit else None


def next_series_id(series):
    nums = [int(m.group(1)) for m in
            (re.match(r"^S(\d+)$", s["id"]) for s in series) if m]
    return "S%d" % ((max(nums) + 1) if nums else 1)


# ---------- 系列 ----------

def cmd_series_add(a):
    series, plans = parse()
    for s in series:
        if s["topic"] == a.topic:
            return {"error": "系列已存在：%s（%s）" % (s["id"], s["topic"])}
    sid = next_series_id(series)
    rng = "%s ~ %s" % (a.start or "—", a.end or "—")
    series.append({"id": sid, "topic": a.topic, "goal": str(a.goal or "—"),
                   "range": rng, "status": "进行中", "note": a.note or ""})
    save(series, plans)
    return {"ok": True, "id": sid, "topic": a.topic,
            "next": "排期：calendar.py plan \"选题\" --date ... --series %s" % sid}


def cmd_series_list(_a):
    series, plans = parse()
    out = []
    for s in series:
        mine = [p for p in plans if p["series"] == s["id"]]
        out.append({**s,
                    "planned": len(mine),
                    "published": sum(1 for p in mine if p["status"] == "已发")})
    return {"series": out}


def cmd_series_kill(a):
    series, plans = parse()
    for s in series:
        if s["id"].lower() == (a.id or "").lower():
            s["status"] = "已停"
            if a.why:
                s["note"] = (s["note"] + "；停：" + a.why).strip("；")
            save(series, plans)
            return {"ok": True, "id": s["id"], "status": s["status"]}
    return {"error": "没找到系列：%s" % a.id}


# ---------- 排期 ----------

def cmd_plan(a):
    series, plans = parse()
    d = parse_date(a.date)
    if not d:
        return {"error": "日期格式要 YYYY-MM-DD：%s" % a.date}
    if a.series:
        ids = {s["id"] for s in series}
        if a.series not in ids:
            return {"error": "系列不存在：%s。先 series add" % a.series}
    for p in plans:
        if p["title"] == a.title:
            return {"error": "已排过：%s（%s）" % (p["title"], p["date"])}
    track = a.track or ("深度轨" if a.platform == "xhs" else "发现轨")
    plans.append({"date": d.strftime("%Y-%m-%d"), "platform": a.platform,
                  "track": track, "title": a.title,
                  "series": a.series or "", "status": "待做", "slug": ""})
    plans.sort(key=lambda p: p["date"])
    save(series, plans)
    return {"ok": True, "date": d.strftime("%Y-%m-%d"), "title": a.title,
            "track": track}


def cmd_list(a):
    series, plans = parse()
    rows = plans
    if a.series:
        rows = [p for p in rows if p["series"] == a.series]
    if a.status:
        rows = [p for p in rows if p["status"] == a.status]
    return {"total": len(rows),
            "by_status": {s: sum(1 for p in plans if p["status"] == s)
                          for s in STATUSES},
            "plans": rows}


def cmd_week(a):
    series, plans = parse()
    monday = today() - timedelta(days=today().weekday()) + timedelta(
        weeks=a.offset)
    days = [(monday + timedelta(days=i)) for i in range(7)]
    lo, hi = days[0], days[-1]
    rows = [p for p in plans
            if p["date"] and lo <= (parse_date(p["date"]) or lo) <= hi]
    rows.sort(key=lambda p: p["date"])
    return {"week": "%s ~ %s" % (lo.strftime("%Y-%m-%d"),
                                 hi.strftime("%Y-%m-%d")),
            "count": len(rows), "plans": rows,
            "note": "本周没有排期" if not rows else ""}


def cmd_due(a):
    series, plans = parse()
    limit = today() + timedelta(days=a.days)
    rows = []
    for p in plans:
        if p["status"] in ("已发", "砍掉"):
            continue
        d = parse_date(p["date"])
        if not d:
            continue
        if d <= limit:
            rows.append({**p, "overdue_days": (today() - d).days})
    rows.sort(key=lambda p: p["date"])
    return {"due": rows, "count": len(rows),
            "overdue": sum(1 for r in rows if r["overdue_days"] > 0)}


def run(cmd, env_extra=None):
    env = dict(os.environ)
    env["VFLOW_HOME"] = ROOT
    if env_extra:
        env.update(env_extra)
    return subprocess.run(cmd, capture_output=True, text=True, env=env,
                          timeout=120)


def cmd_start(a):
    series, plans = parse()
    p = find_plan(plans, a.title)
    if isinstance(p, dict) and "error" in p:
        return p
    if not p:
        return {"error": "排期里没有：%s。先 plan 排期，或直接开项目。" % a.title}
    if p["status"] == "已排" and p["slug"]:
        return {"ok": True, "already": True, "slug": p["slug"],
                "note": "这条已经开过项目了"}
    script = os.path.join(ROOT, "scripts", "new_project.sh")
    r = run(["bash", script, a.title])
    if r.returncode != 0:
        return {"error": "开项目失败：%s" % (r.stdout + r.stderr)[-300:]}
    slug = ""
    for line in r.stdout.splitlines():
        if "项目已创建:" in line:
            slug = line.split("项目已创建:")[1].strip().rstrip("/").split("/")[-1]
    p["status"] = "已排"
    p["slug"] = slug
    save(series, plans)
    return {"ok": True, "slug": slug, "date": p["date"],
            "next": "开完跑选题：projects/%s/01-topic.md" % slug}


def cmd_done(a):
    series, plans = parse()
    p = find_plan(plans, a.title)
    if isinstance(p, dict) and "error" in p:
        return p
    if not p:
        return {"error": "排期里没有：%s" % a.title}
    p["status"] = "已发"
    if a.slug:
        p["slug"] = a.slug
    save(series, plans)
    return {"ok": True, "title": p["title"], "date": p["date"],
            "next": "48 小时后复盘：review.py fill %s --platform %s"
                    % (p["slug"] or "<slug>", p["platform"])}


def cmd_check(_a):
    series, plans = parse()
    issues = []
    # 同平台同一天超过一条
    seen = {}
    for p in plans:
        if p["status"] == "砍掉":
            continue
        k = (p["date"], p["platform"])
        seen.setdefault(k, []).append(p["title"])
    for (d, plat), ts in sorted(seen.items()):
        if len(ts) > 1:
            issues.append({"type": "同平台同日多条", "date": d,
                           "platform": plat, "titles": ts})
    # 系列是否达标
    counts = {}
    for p in plans:
        if p["series"] and p["status"] != "砍掉":
            counts.setdefault(p["series"], []).append(p)
    out_series = []
    for s in series:
        if s["status"] != "进行中":
            continue
        try:
            goal = int(s["goal"])
        except ValueError:
            continue
        got = len(counts.get(s["id"], []))
        out_series.append({"id": s["id"], "topic": s["topic"], "goal": goal,
                           "planned": got, "ok": got >= goal})
    # 到期未排
    late = [p for p in plans if p["status"] == "待做"
            and (parse_date(p["date"]) or today()) < today()]
    return {"issues": issues, "series": out_series,
            "late_unstarted": [{"date": p["date"], "title": p["title"]}
                               for p in late],
            "ok": not issues}


def main():
    ap = argparse.ArgumentParser(description="Vflow 内容日历与系列化")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("series")
    sp = p.add_subparsers(dest="sub", required=True)
    q = sp.add_parser("add"); q.add_argument("topic")
    q.add_argument("--goal", type=int); q.add_argument("--start")
    q.add_argument("--end"); q.add_argument("--note")
    q.set_defaults(fn=cmd_series_add)
    q = sp.add_parser("list"); q.set_defaults(fn=cmd_series_list)
    q = sp.add_parser("kill"); q.add_argument("id"); q.add_argument("--why")
    q.set_defaults(fn=cmd_series_kill)

    p = sub.add_parser("plan"); p.add_argument("title")
    p.add_argument("--date", required=True)
    p.add_argument("--platform", choices=["douyin", "xhs"], required=True)
    p.add_argument("--track", choices=TRACKS)
    p.add_argument("--series")
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("list"); p.add_argument("--series")
    p.add_argument("--status", choices=STATUSES)
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("week"); p.add_argument("--offset", type=int, default=0)
    p.set_defaults(fn=cmd_week)

    p = sub.add_parser("due"); p.add_argument("--days", type=int, default=3)
    p.set_defaults(fn=cmd_due)

    p = sub.add_parser("start"); p.add_argument("title")
    p.set_defaults(fn=cmd_start)

    p = sub.add_parser("done"); p.add_argument("title"); p.add_argument("--slug")
    p.set_defaults(fn=cmd_done)

    sub.add_parser("check").set_defaults(fn=cmd_check)

    args = ap.parse_args()
    result = args.fn(args)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
