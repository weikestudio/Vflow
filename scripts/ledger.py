#!/usr/bin/env python3
"""证据台账：观察先攒着，够三条才准改成默认。

用法：
    python3 ledger.py add "观察内容" --slug 20261022-xxx      记一条候选
    python3 ledger.py add "观察内容" --slug 20261022-xxx --again 给已有观察再加一条证据
    python3 ledger.py list                                     看所有候选和证据数
    python3 ledger.py promote <ID>                             够三条才给升级（输出可写进 profile.md 的原文）
    python3 ledger.py retract <ID> --why "后来被推翻的原因"      降级/撤回

三条规则：
1. 一条数据 = 候选，不改默认
2. 三条可比证据才能升级（可比 = 同平台、同类型、同期）
3. 升级必须可逆，反例出现就降级

脚本**不会**自动改 profile.md——改什么是人的判断，脚本只负责拦住不够格的升级。

零依赖。
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime

ROOT = os.path.abspath(
    os.environ.get("VFLOW_HOME") or os.path.expanduser("~/Vflow")
)
LEDGER_MD = os.path.join(ROOT, "ledger", "evidence.md")
PROMOTE_THRESHOLD = 3


DEFAULT_LEDGER = """# 证据台账

> **一条数据不是规律。** 这条内容的完播高，可能是选题好、可能是钩子好、也可能只是运气。
> 台账的作用：把"观察"和"结论"分开，中间设一道门槛。

## 规则（三条，别绕过）

1. **候选不等于结论。** 发完一条记一条观察，它是候选，不改任何默认设置
2. **三条可比证据才能升级。** 可比 = 同平台、同类型、同期。三条都指向同一个结论，才允许写进 `profile.md`
3. **升级必须可逆。** 每次升级要写明：改了什么、因为哪几条数据、怎么退回。**反例出现就降级**，别硬撑

## 记录

| ID | 观察 | 证据数 | 支撑项目 | 状态 |
|---|---|---|---|---|

## 已升级为默认

| ID | 结论 | 证据数 | 支撑项目 | 升级日期 |
|---|---|---|---|---|

## 已撤回

（曾经以为是对的，后来被推翻的——这些同样值钱，别删）
"""


def ensure_file():
    """台账文件不在（比如刚 clone 的仓库）就从内置模板建一个。"""
    if not os.path.isfile(LEDGER_MD):
        os.makedirs(os.path.dirname(LEDGER_MD), exist_ok=True)
        with open(LEDGER_MD, "w", encoding="utf-8") as fh:
            fh.write(DEFAULT_LEDGER)


def read_text(p):
    try:
        with open(p, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def next_id(rows):
    nums = [int(m.group(1)) for m in
            (re.match(r"^E(\d+)$", r["id"]) for r in rows) if m]
    return "E%d" % ((max(nums) + 1) if nums else 1)


def parse(text):
    """解析台账：返回 (候选rows, 已升级rows, 已撤回rows)。"""
    rows, section = {"candidate": [], "promoted": [], "retracted": []}, None
    for line in text.split("\n"):
        if line.startswith("## "):
            t = line[3:].strip()
            section = {"记录": "candidate", "已升级为默认": "promoted",
                       "已撤回": "retracted"}.get(t)
            continue
        if section and line.startswith("|") and "---" not in line:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if not cells or cells[0] in ("ID", ""):
                continue
            row = {"id": cells[0], "text": cells[1] if len(cells) > 1 else "",
                   "count": cells[2] if len(cells) > 2 else "0",
                   "projects": cells[3] if len(cells) > 3 else "",
                   "status": cells[4] if len(cells) > 4 else section}
            if section == "candidate":
                row["status"] = cells[4] if len(cells) > 4 else "候选"
            rows[section].append(row)
    return rows


def render(rows):
    text = read_text(LEDGER_MD)
    lines = text.split("\n")
    out, section, i, n = [], None, 0, len(lines)

    def row_line(r):
        return "| %s | %s | %s | %s | %s |" % (
            r["id"], r["text"], r.get("count", 1), r.get("projects", ""),
            r.get("status", "候选"))

    while i < n:
        line = lines[i]
        if line.startswith("## "):
            t = line[3:].strip()
            section = {"记录": "candidate", "已升级为默认": "promoted",
                       "已撤回": "retracted"}.get(t)
            out.append(line)
            i += 1
            if section is None:
                continue          # 说明性段落，原样保留
            # 跳过本段所有表格行
            while i < n and not re.match(r"^##\s", lines[i]):
                if lines[i].startswith("|"):
                    i += 1
                    continue
                out.append(lines[i])
                i += 1
            while out and out[-1].strip() == "":
                out.pop()
            out.append("")
            if section == "candidate":
                out.append("| ID | 观察 | 证据数 | 支撑项目 | 状态 |")
            elif section == "promoted":
                out.append("| ID | 结论 | 证据数 | 支撑项目 | 升级日期 |")
            else:
                out.append("| ID | 观察 | 证据数 | 支撑项目 | 撤回原因 |")
            for r in rows.get(section, []):
                out.append(row_line(r))
            out.append("")
            continue
        out.append(line)
        i += 1
    return "\n".join(out).rstrip() + "\n"


def save(rows):
    os.makedirs(os.path.dirname(LEDGER_MD), exist_ok=True)
    # 必须先渲染再开文件：open(w) 会立刻截断，先开就读到空内容了
    content = render(rows)
    with open(LEDGER_MD, "w", encoding="utf-8") as fh:
        fh.write(content)


def cmd_add(a):
    rows = parse(read_text(LEDGER_MD))
    cands = rows["candidate"]

    if a.again:
        target = None
        for r in cands:
            if r["id"].lower() == a.again.lower() or a.again in r["text"]:
                target = r
                break
        if not target:
            return {"error": "没找到这条观察：%s" % a.again}
        try:
            target["count"] = str(int(target.get("count", "1")) + 1)
        except ValueError:
            target["count"] = "2"
        target["projects"] = (target.get("projects", "") + "、" + a.slug) \
            if target.get("projects") else a.slug
        save(rows)
        n = int(target["count"])
        return {"ok": True, "id": target["id"], "count": n,
                "ready": n >= PROMOTE_THRESHOLD,
                "next": "够三条了，可以跑 promote %s" % target["id"]
                if n >= PROMOTE_THRESHOLD
                else "还差 %d 条才够升级" % (PROMOTE_THRESHOLD - n)}

    # 看看是不是已经记过类似观察
    for r in cands:
        if r["text"] == a.text:
            return {"error": "这条观察已经有了：%s。要加证据用 --again %s"
                    % (r["id"], r["id"])}

    rid = next_id(cands + rows["promoted"] + rows["retracted"])
    cands.append({"id": rid, "text": a.text, "count": "1",
                  "projects": a.slug, "status": "候选"})
    save(rows)
    return {"ok": True, "id": rid, "count": 1, "ready": False,
            "next": "还差 %d 条才够升级" % (PROMOTE_THRESHOLD - 1)}


def cmd_list(_a):
    rows = parse(read_text(LEDGER_MD))
    out = []
    for r in rows["candidate"]:
        try:
            n = int(r.get("count", "1"))
        except ValueError:
            n = 1
        out.append({"id": r["id"], "observation": r["text"], "evidence": n,
                    "projects": r.get("projects", ""),
                    "ready": n >= PROMOTE_THRESHOLD})
    return {"candidates": out,
            "promoted": rows["promoted"],
            "retracted": rows["retracted"],
            "threshold": PROMOTE_THRESHOLD}


def cmd_promote(a):
    rows = parse(read_text(LEDGER_MD))
    target = None
    for r in rows["candidate"]:
        if r["id"].lower() == a.id.lower():
            target = r
            break
    if not target:
        return {"error": "没找到候选：%s" % a.id}
    try:
        n = int(target.get("count", "1"))
    except ValueError:
        n = 1
    if n < PROMOTE_THRESHOLD:
        return {
            "refused": True, "id": target["id"], "evidence": n,
            "need": PROMOTE_THRESHOLD,
            "reason": "只有 %d 条证据，不够。一条或两条数据说明不了问题——"
                      "可能是选题好、可能是运气。再攒 %d 条同平台同类型的可比数据。"
                      % (n, PROMOTE_THRESHOLD - n),
        }

    today = datetime.now().strftime("%Y-%m-%d")
    target["status"] = today
    rows["candidate"] = [r for r in rows["candidate"] if r["id"] != target["id"]]
    rows["promoted"].append(target)
    save(rows)
    return {
        "promoted": True, "id": target["id"], "evidence": n,
        "write_this_into_profile": "- %s（证据：%s，%s 升级）"
                                  % (target["text"], target.get("projects", ""), today),
        "rollback": "如果出现反例，跑 `python3 scripts/ledger.py retract %s "
                    "--why \"反例说明\"`，并把 profile.md 里对应那行删掉。"
                    % target["id"],
        "note": "脚本没动 profile.md，你自己决定要不要写、怎么写。",
    }


def cmd_retract(a):
    rows = parse(read_text(LEDGER_MD))
    for key in ("candidate", "promoted"):
        for r in rows[key]:
            if r["id"].lower() == a.id.lower():
                r["status"] = a.why or "反例"
                rows[key] = [x for x in rows[key] if x["id"] != r["id"]]
                rows["retracted"].append(r)
                save(rows)
                return {"retracted": True, "id": r["id"], "why": r["status"],
                        "todo": "记得把 profile.md 里对应那行也删掉"}
    return {"error": "没找到：%s" % a.id}


def main():
    ap = argparse.ArgumentParser(description="Vflow 证据台账")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add")
    p.add_argument("text"); p.add_argument("--slug", default="")
    p.add_argument("--again")
    p.set_defaults(fn=cmd_add)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    p = sub.add_parser("promote"); p.add_argument("id")
    p.set_defaults(fn=cmd_promote)
    p = sub.add_parser("retract"); p.add_argument("id")
    p.add_argument("--why"); p.set_defaults(fn=cmd_retract)

    args = ap.parse_args()
    json.dump(args.fn(args), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
