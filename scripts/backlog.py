#!/usr/bin/env python3
"""Vflow 选题池：把「想到的点子」存下来，开工前先从这里挑，不从空白页开始。

热点雷达不做——联网抓热榜要踩平台 ToS，而且现在的问题不是没选题，
是选题太多做不完。这里只做本地池子，几乎零成本。

用法：
    python3 backlog.py add "一个想法" [--type B] [--note "为什么值得做"]
    python3 backlog.py add "一个想法" --source "对标：某条视频的评论区"
    python3 backlog.py list [--status 候选|在做|已发|已毙]
    python3 backlog.py start "关键词" [--slug 20261024-xxx]   转成「在做」，可关联项目
    python3 backlog.py kill "关键词" --why "三问里第二问答不了"
    python3 backlog.py done "关键词"                            标记已发布
    python3 backlog.py revive "关键词"                          从已毙捞回来
    python3 backlog.py review                                   列 30 天没动的候选

设计：
- 一条一行 markdown 表格，人可以直接编辑，脚本负责增删改查。
- 毙掉的必须写原因。半年后回头看「为什么毙」，比看做过什么更有用。
- 状态：候选 / 在做 / 已发 / 已毙。开新项目时 new_project.sh 会自动把同名候选转成在做。

零依赖。
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

ROOT = os.path.abspath(
    os.environ.get("VFLOW_HOME") or os.path.expanduser("~/Vflow"))
BACKLOG = os.path.join(ROOT, "backlog.md")
STATUSES = ["候选", "在做", "已发", "已毙"]

HEADER = """# 选题池

> **开工前先看这里，别面对空白页。** 想法进来先记成候选，不急着做。
> 选题三问（能不能拿走一个动作 / 能不能证明我会做 / 三个月后还有人搜）
> 过了就排在做，过不了就毙掉，**毙的原因要写清楚**——半年后回头看，
> 「为什么毙」比「做过什么」更有用。
>
> 用法：`python3 scripts/backlog.py list` / `add` / `start` / `kill` / `done`

## 池子

| 日期 | 选题 | 类型 | 状态 | 关联项目 | 备注 |
|---|---|---|---|---|---|
"""


def read(p):
    try:
        with open(p, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def ensure():
    if not os.path.isfile(BACKLOG):
        os.makedirs(ROOT, exist_ok=True)
        with open(BACKLOG, "w", encoding="utf-8") as fh:
            fh.write(HEADER)


def parse():
    ensure()
    rows = []
    for line in read(BACKLOG).split("\n"):
        if not line.startswith("|") or "---" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 6 or cells[0] in ("日期",):
            continue
        rows.append({
            "date": cells[0], "title": cells[1], "type": cells[2],
            "status": cells[3], "slug": cells[4], "note": cells[5],
        })
    return rows


def save(rows):
    head = read(BACKLOG)
    idx = head.find("| 日期 |")
    if idx < 0:
        head = HEADER
        idx = head.find("| 日期 |")
    # 保留表格前的说明，重写表格
    prefix = head[:idx]
    if "## 池子" not in prefix:
        prefix = prefix.rstrip() + "\n\n## 池子\n\n"
    lines = ["| 日期 | 选题 | 类型 | 状态 | 关联项目 | 备注 |",
             "|---|---|---|---|---|---|"]
    for r in rows:
        lines.append("| %s | %s | %s | %s | %s | %s |" % (
            r["date"], r["title"], r["type"], r["status"],
            r["slug"] or "—", r["note"]))
    with open(BACKLOG, "w", encoding="utf-8") as fh:
        fh.write(prefix + "\n".join(lines) + "\n")


def find(rows, key):
    exact = [r for r in rows if r["title"] == key]
    if exact:
        return exact[0]
    hits = [r for r in rows if key in r["title"]]
    if len(hits) > 1:
        return {"error": "有 %d 条都匹配「%s」，说具体点：%s" % (
            len(hits), key, "、".join(r["title"] for r in hits))}
    return hits[0] if hits else None


def cmd_add(a):
    rows = parse()
    for r in rows:
        if r["title"] == a.title:
            return {"error": "池子里已有：%s（%s）" % (r["title"], r["status"])}
    rows.insert(0, {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "title": a.title, "type": a.type or "—",
        "status": "候选", "slug": "",
        "note": a.note or a.source or "",
    })
    save(rows)
    return {"ok": True, "title": a.title, "count": len(rows),
            "next": "过了三问就 start，过不了就 kill --why"}


def cmd_list(a):
    rows = parse()
    if a.status:
        rows = [r for r in rows if r["status"] == a.status]
    out = {"total": len(parse()), "filtered": len(rows),
           "by_status": {s: sum(1 for r in parse() if r["status"] == s)
                         for s in STATUSES},
           "rows": rows}
    return out


def cmd_start(a):
    rows = parse()
    r = find(rows, a.title)
    if isinstance(r, dict) and "error" in r:
        return r
    if not r:
        return {"error": "池子里没有：%s。先 add，或者开项目时直接写名。" % a.title}
    if r["status"] == "已毙" and not a.force:
        return {"error": "「%s」已毙（%s）。真要做就 revive 再说，"
                         "别绕过自己当时的判断。" % (r["title"], r["note"])}
    r["status"] = "在做"
    if a.slug:
        r["slug"] = a.slug
    save(rows)
    return {"ok": True, "title": r["title"], "status": r["status"],
            "slug": r["slug"] or ""}


def cmd_kill(a):
    rows = parse()
    r = find(rows, a.title)
    if isinstance(r, dict) and "error" in r:
        return r
    if not r:
        return {"error": "池子里没有：%s" % a.title}
    r["status"] = "已毙"
    why = (a.why or "").strip()
    if why:
        r["note"] = ("毙：" + why + ("；" + r["note"] if r["note"] and
                                    not r["note"].startswith("毙：") else ""))
    save(rows)
    return {"ok": True, "title": r["title"], "why": why,
            "note": "" if why else "没写原因。半年后你会忘了为什么毙掉它"}


def cmd_done(a):
    rows = parse()
    r = find(rows, a.title)
    if isinstance(r, dict) and "error" in r:
        return r
    if not r:
        return {"error": "池子里没有：%s" % a.title}
    r["status"] = "已发"
    if a.slug:
        r["slug"] = a.slug
    save(rows)
    return {"ok": True, "title": r["title"]}


def cmd_revive(a):
    rows = parse()
    r = find(rows, a.title)
    if isinstance(r, dict) and "error" in r:
        return r
    if not r:
        return {"error": "池子里没有：%s" % a.title}
    r["status"] = "候选"
    save(rows)
    return {"ok": True, "title": r["title"],
            "note": "从已毙捞回候选。上次毙的原因还在备注里，看一眼再决定"}


def cmd_review(a):
    rows = parse()
    today = datetime.now()
    stale = []
    for r in rows:
        if r["status"] not in ("候选", "在做"):
            continue
        try:
            d = datetime.strptime(r["date"], "%Y-%m-%d")
        except ValueError:
            continue
        age = (today - d).days
        if age >= a.days:
            stale.append({"title": r["title"], "status": r["status"],
                          "age_days": age, "note": r["note"]})
    stale.sort(key=lambda x: -x["age_days"])
    return {"stale": stale, "count": len(stale),
            "suggestion": "超过 %d 天没动的，要么排期要么毙掉，别一直躺着"
                          % a.days}


def main():
    ap = argparse.ArgumentParser(description="Vflow 选题池")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add")
    p.add_argument("title")
    p.add_argument("--type", choices=["A", "B", "C"])
    p.add_argument("--note"); p.add_argument("--source")
    p.set_defaults(fn=cmd_add)

    p = sub.add_parser("list")
    p.add_argument("--status", choices=STATUSES)
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("start")
    p.add_argument("title"); p.add_argument("--slug")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_start)

    p = sub.add_parser("kill")
    p.add_argument("title"); p.add_argument("--why")
    p.set_defaults(fn=cmd_kill)

    p = sub.add_parser("done")
    p.add_argument("title"); p.add_argument("--slug")
    p.set_defaults(fn=cmd_done)

    p = sub.add_parser("revive")
    p.add_argument("title")
    p.set_defaults(fn=cmd_revive)

    p = sub.add_parser("review")
    p.add_argument("--days", type=int, default=30)
    p.set_defaults(fn=cmd_review)

    args = ap.parse_args()
    json.dump(args.fn(args), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
