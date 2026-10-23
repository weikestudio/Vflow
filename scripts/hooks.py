#!/usr/bin/env python3
"""钩子库管理：记录每次用了哪个钩子，攒够数据后告诉你好用哪个。

用法：
    python3 hooks.py list              列出全部钩子和使用次数
    python3 hooks.py best              按有效次数排序，推荐该用哪个
    python3 hooks.py use <H编号> <项目slug> [--platform douyin]
    python3 hooks.py fill <H编号> <项目slug> --ret3 42 --finish 28 --verdict 有效

设计：
- 记录双写：hooks.md 里的表格（人看）+ 项目 .vflow.json 的 hooks 字段（机器读）
- best 排序先看"有效"次数，有效数相同再看用没用过（没用过的优先，鼓励试新）
- 一条数据不出结论，规则在 ledger/evidence.md

零依赖。
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.abspath(
    os.environ.get("VFLOW_HOME") or os.path.expanduser("~/Vflow")
)
HOOKS_MD = os.path.join(ROOT, "assets", "hooks.md")
PROJECTS = os.path.join(ROOT, "projects")
STATE = os.path.join(ROOT, "scripts", "vflow_state.py")


def read_text(p):
    try:
        with open(p, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def parse_hooks():
    """解析 hooks.md，返回 [(id, name, rows)]。"""
    text = read_text(HOOKS_MD)
    out = []
    cur = None
    for line in text.split("\n"):
        m = re.match(r"^##\s+(H\d+)\s+·\s+(.+)$", line)
        if m:
            cur = {"id": m.group(1), "name": m.group(2).strip(),
                   "template": "", "rows": []}
            out.append(cur)
            continue
        if cur is None:
            continue
        if line.startswith("**模板**"):
            cur["template"] = line.split("：", 1)[-1].strip()
        elif line.startswith("|") and "---" not in line and "项目" not in line:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 5:
                cur["rows"].append({
                    "project": cells[0], "platform": cells[1],
                    "ret3": cells[2], "finish": cells[3],
                    "verdict": cells[4],
                })
    return out


def write_rows(hook_id, rows):
    """把某个钩子的记录行写回 hooks.md：保留表头，替换数据行。"""
    lines = read_text(HOOKS_MD).split("\n")
    out, i, n = [], 0, len(lines)
    while i < n:
        line = lines[i]
        m = re.match(r"^##\s+(H\d+)\s+·", line)
        if m and m.group(1) == hook_id:
            out.append(line)
            i += 1
            header = None
            while i < n and not re.match(r"^##\s+", lines[i]):
                cur_line = lines[i]
                if cur_line.startswith("|"):
                    if "---" not in cur_line and header is None \
                            and "项目" in cur_line:
                        header = cur_line
                    i += 1          # 表头和数据行都跳过，最后统一写
                    continue
                out.append(cur_line)
                i += 1
            while out and out[-1].strip() == "":
                out.pop()
            out.append("")
            if header:
                out.append(header)
                out.append("|---|---|---|---|---|")
            for r in rows:
                out.append("| %s | %s | %s | %s | %s |" % (
                    r["project"], r["platform"], r["ret3"],
                    r["finish"], r["verdict"]))
            out.append("")
            continue
        out.append(line)
        i += 1
    with open(HOOKS_MD, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out).rstrip() + "\n")


def reset_hook_rows(hook_id):
    """清空某个钩子的记录（写坏了时用）。"""
    write_rows(hook_id, [])


def touch_project(slug, hook_id):
    """把用到的钩子记进项目 .vflow.json。"""
    sp = os.path.join(PROJECTS, slug, ".vflow.json")
    if not os.path.isfile(sp):
        return
    try:
        st = json.loads(read_text(sp))
    except json.JSONDecodeError:
        return
    st.setdefault("hooks", [])
    if hook_id not in st["hooks"]:
        st["hooks"].append(hook_id)
    with open(sp, "w", encoding="utf-8") as fh:
        json.dump(st, fh, ensure_ascii=False, indent=2)


def cmd_list(_a):
    hooks = parse_hooks()
    return {"hooks": [{
        "id": h["id"], "name": h["name"],
        "used": len(h["rows"]),
        "effective": sum(1 for r in h["rows"] if r["verdict"] == "有效"),
        "template": h["template"],
    } for h in hooks]}


def cmd_best(_a):
    hooks = parse_hooks()
    stat = []
    for h in hooks:
        eff = sum(1 for r in h["rows"] if r["verdict"] == "有效")
        bad = sum(1 for r in h["rows"] if r["verdict"] == "无效")
        stat.append({
            "id": h["id"], "name": h["name"], "used": len(h["rows"]),
            "effective": eff, "invalid": bad,
            "score": eff * 2 - bad + (1 if not h["rows"] else 0),
            "template": h["template"],
        })
    stat.sort(key=lambda x: -x["score"])
    return {"ranking": stat}


def cmd_use(a):
    hooks = parse_hooks()
    target = None
    for h in hooks:
        if h["id"].lower() == a.hook.lower():
            target = h
            break
    if not target:
        return {"error": "没有这个钩子：%s" % a.hook}
    for r in target["rows"]:
        if r["project"] == a.slug:
            return {"error": "这个项目已经记过 %s 了" % a.hook}
    target["rows"].append({
        "project": a.slug, "platform": a.platform,
        "ret3": "—", "finish": "—", "verdict": "待回填",
    })
    write_rows(target["id"], target["rows"])
    touch_project(a.slug, target["id"])
    return {"ok": True, "hook": target["id"], "name": target["name"],
            "project": a.slug,
            "todo": "复盘时回填数据：python3 scripts/hooks.py fill %s %s "
                    "--ret3 42 --finish 28 --verdict 有效" % (
                        target["id"], a.slug)}


def cmd_fill(a):
    hooks = parse_hooks()
    target = None
    for h in hooks:
        if h["id"].lower() == a.hook.lower():
            target = h
            break
    if not target:
        return {"error": "没有这个钩子：%s" % a.hook}
    for r in target["rows"]:
        if r["project"] == a.slug:
            if a.ret3 is not None:
                r["ret3"] = a.ret3
            if a.finish is not None:
                r["finish"] = a.finish
            if a.verdict:
                r["verdict"] = a.verdict
            write_rows(target["id"], target["rows"])
            return {"ok": True, "row": r}
    return {"error": "这个项目没记过 %s，先跑 use" % a.hook}


def main():
    ap = argparse.ArgumentParser(description="Vflow 钩子库")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    sub.add_parser("best").set_defaults(fn=cmd_best)
    p = sub.add_parser("use")
    p.add_argument("hook"); p.add_argument("slug")
    p.add_argument("--platform", default="douyin")
    p.set_defaults(fn=cmd_use)
    p = sub.add_parser("fill")
    p.add_argument("hook"); p.add_argument("slug")
    p.add_argument("--ret3"); p.add_argument("--finish")
    p.add_argument("--verdict", choices=["有效", "一般", "无效", "待回填"])
    p.set_defaults(fn=cmd_fill)

    args = ap.parse_args()
    json.dump(args.fn(args), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
