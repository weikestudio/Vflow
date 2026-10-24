#!/usr/bin/env python3
"""声明-证据台账：稿子里每个对外数字/功能/结论，都要能说清来源、口径、什么时候核过的。

为什么单独做：项目级证据台账（ledger）管的是"方法规律"，这份管的是
"这条内容里的每一个事实"。前者防"一条数据改方法"，后者防"一个数字说错毁掉可信度"。
你的差异化是"可信"，可信必须能被检查。

用法：
    python3 claims.py add "49.5%" --source "IDC 2026-06 报告" --caliber "大模型服务市场份额" --slug <slug>
    python3 claims.py list [--slug <slug>] [--status 待核|已核|已过时]
    python3 claims.py scan <slug>             扫稿件里出现但没登记的声明
    python3 claims.py verify C3 [--date 2026-10-24]
    python3 claims.py stale --days 90          超过 N 天没核的
    python3 claims.py report <slug>            这个项目的声明清单

规则：
- 数字（含百分比）、版本号、"官方/据称/数据显示"类表述，算声明，要登记。
- 登记要写来源和口径。口径不同不能互相引用（"万播 5–10 元"是行业测算，不是平台公布）。
- 超过 90 天没核的标"已过时"，发布前要复核。

零依赖。
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import vflow_state as VS          # noqa: E402

ROOT = VS.ROOT
CLAIMS = os.path.join(ROOT, "claims.md")
STATUSES = ["待核", "已核", "已过时"]

HEADER = """# 声明-证据台账

> 这条内容里对外说的每个**数字、版本、功能、结论**，都要能回答三个问题：
> 从哪来的、什么口径、什么时候核过的。
>
> 为什么较真：账号的差异化是"可信"。一个数字说错，观众不会记住你九句对的，
> 只会记住那一句错的。这份台账就是发布前的最后一道事实关。
>
> 用法：`python3 scripts/claims.py add "49.5%" --source "IDC 2026-06" --caliber "大模型服务市场份额"`
> 扫描未登记：`python3 scripts/claims.py scan <slug>`

## 声明

| ID | 项目 | 声明 | 来源 | 口径 | 核验日期 | 状态 |
|---|---|---|---|---|---|---|
"""

# 什么算"声明"：数字 / 百分比 / 版本号 / 引用类措辞
CLAIM_PATTERNS = [
    (r"\d+(?:\.\d+)?\s*%", "百分比"),
    (r"\d[\d,\.]*\s*(?:亿|万|千|百|元|块|美元|天|月|年|小时|分钟|秒|次|人|条|款|个)",
     "数量"),
    (r"(?:据.{0,8}报道|数据显示|报告显示|媒体转述|行业测算|据测算)", "来源措辞"),
    (r"(?:v|V)\d+(?:\.\d+)+", "版本号"),
]
STOP = {"第", "页", "秒", "条", "个", "号"}


def now_date():
    return datetime.now().strftime("%Y-%m-%d")


def read(p):
    return VS.read_text(p)


def ensure():
    if not os.path.isfile(CLAIMS):
        os.makedirs(ROOT, exist_ok=True)
        with open(CLAIMS, "w", encoding="utf-8") as fh:
            fh.write(HEADER)


def parse():
    ensure()
    rows = []
    for line in read(CLAIMS).split("\n"):
        if not line.startswith("|") or "---" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 7 or cells[0] in ("ID",):
            continue
        rows.append({"id": cells[0], "slug": cells[1], "claim": cells[2],
                     "source": cells[3], "caliber": cells[4],
                     "verified": cells[5], "status": cells[6]})
    return rows


def save(rows):
    head = read(CLAIMS)
    idx = head.find("| ID |")
    prefix = head[:idx] if idx >= 0 else HEADER
    if "## 声明" not in prefix:
        prefix = prefix.rstrip() + "\n\n## 声明\n\n"
    lines = ["| ID | 项目 | 声明 | 来源 | 口径 | 核验日期 | 状态 |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append("| %s | %s | %s | %s | %s | %s | %s |" % (
            r["id"], r["slug"] or "—", r["claim"], r["source"] or "—",
            r["caliber"] or "—", r["verified"] or "—", r["status"]))
    with open(CLAIMS, "w", encoding="utf-8") as fh:
        fh.write(prefix + "\n".join(lines) + "\n")


def next_id(rows):
    nums = [int(m.group(1)) for m in
            (re.match(r"^C(\d+)$", r["id"]) for r in rows) if m]
    return "C%d" % ((max(nums) + 1) if nums else 1)


def norm(s):
    return re.sub(r"[\s，。！？、,.!?%％]", "", str(s or ""))


def cmd_add(a):
    rows = parse()
    claim = a.claim.strip()
    if not claim:
        return {"error": "声明不能为空"}
    for r in rows:
        if norm(r["claim"]) == norm(claim) and (r["slug"] or "") == (a.slug or ""):
            return {"error": "已登记过：%s（%s）" % (r["id"], r["status"])}
    rid = next_id(rows)
    status = "已核" if a.verified else "待核"
    rows.append({"id": rid, "slug": a.slug or "", "claim": claim,
                 "source": a.source or "", "caliber": a.caliber or "",
                 "verified": a.verified or "", "status": status})
    save(rows)
    out = {"ok": True, "id": rid, "status": status}
    if not a.source:
        out["warn"] = "没写来源。发布前补上，否则这条声明不能算数"
    if not a.caliber:
        out["caliber_hint"] = "没写口径。同一件事不同口径的数字不能互相引用"
    return out


def cmd_list(a):
    rows = parse()
    if a.slug:
        rows = [r for r in rows if r["slug"] == a.slug]
    if a.status:
        rows = [r for r in rows if r["status"] == a.status]
    return {"total": len(rows),
            "by_status": {s: sum(1 for r in parse() if r["status"] == s)
                          for s in STATUSES},
            "claims": rows}


def extract_claims(text):
    """从稿件正文抽出疑似声明，返回 [(原文片段, 类型)]。"""
    body = text
    m = re.search(r"^##\s*逐字稿\s*$", text, re.M)
    if m:
        start = m.end()
        nxt = re.search(r"^##\s+", text[start:], re.M)
        body = text[start:start + nxt.start()] if nxt else text[start:]
    body = re.sub(r"^\|.*$", "", body, flags=re.M)
    body = re.sub(r"【[^】]*】", "", body)          # 画面提示（停留 3 秒等）
    body = re.sub(r"^\s*>?\s*\*\*[^*]+\*\*\s*$", "", body, flags=re.M)
    body = re.sub(r"（[^）]*秒[^）]*）", "", body)
    body = re.sub(r"\d+\s*秒", "", body)          # 时间标注不是事实声明
    out = []
    for pat, kind in CLAIM_PATTERNS:
        for mm in re.finditer(pat, body):
            frag = mm.group(0).strip()
            if len(frag) <= 1:
                continue
            # 排除页序号、时间标注这类
            ctx = body[max(0, mm.start() - 6):mm.end() + 6]
            if re.search(r"第\s*[\d.]+\s*页", ctx) or \
                    re.search(r"^\s*P\d+", ctx):
                continue
            out.append((frag, kind, ctx.strip()))
    # 去重（按片段）
    seen, uniq = set(), []
    for frag, kind, ctx in out:
        key = norm(frag)
        if key in seen:
            continue
        seen.add(key)
        uniq.append((frag, kind, ctx))
    return uniq


def cmd_scan(a):
    slug = a.slug
    text = read(os.path.join(VS.slug_dir(slug), "03-script.md"))
    if not text.strip() or VS.TEMPLATE_MARK in text:
        return {"error": "03-script.md 还是空模板"}
    found = extract_claims(text)
    registered = [r for r in parse() if r["slug"] == slug]
    reg_norm = {norm(r["claim"]) for r in registered}
    unregistered = []
    for frag, kind, ctx in found:
        if norm(frag) not in reg_norm and not any(
                norm(frag) in norm(r["claim"]) or norm(r["claim"]) in norm(frag)
                for r in registered):
            unregistered.append({"claim": frag, "type": kind, "context": ctx})
    return {
        "slug": slug, "found": len(found), "registered": len(registered),
        "unregistered": unregistered,
        "count": len(unregistered),
        "verdict": "全部已登记" if not unregistered
                   else "%d 处数字/引用未登记来源" % len(unregistered),
        "next": "python3 scripts/claims.py add \"<声明>\" --source \"...\" "
                "--caliber \"...\" --slug %s" % slug,
    }


def cmd_verify(a):
    rows = parse()
    for r in rows:
        if r["id"].lower() == a.id.lower():
            r["verified"] = a.date or now_date()
            r["status"] = "已核"
            save(rows)
            return {"ok": True, "id": r["id"], "verified": r["verified"],
                    "status": r["status"]}
    return {"error": "没找到：%s" % a.id}


def cmd_stale(a):
    rows = parse()
    cutoff = (datetime.now() - timedelta(days=a.days)).strftime("%Y-%m-%d")
    out = []
    for r in rows:
        v = r["verified"]
        if not v or v == "—":
            out.append({"id": r["id"], "claim": r["claim"], "why": "从未核验"})
            continue
        if v < cutoff:
            out.append({"id": r["id"], "claim": r["claim"],
                        "why": "核于 %s，超过 %d 天" % (v, a.days)})
    return {"stale": out, "count": len(out), "cutoff": cutoff,
            "note": "发布前复核，复核后跑 claims.py verify <ID>"}


def cmd_report(a):
    slug = a.slug
    rows = [r for r in parse() if r["slug"] == slug]
    if not rows:
        return {"markdown": "这个项目还没有登记任何声明。"}
    lines = ["# 声明清单 · %s" % slug, "",
             "| ID | 声明 | 来源 | 口径 | 核验 | 状态 |",
             "|---|---|---|---|---|---|"]
    for r in rows:
        lines.append("| %s | %s | %s | %s | %s | %s |" % (
            r["id"], r["claim"], r["source"] or "—",
            r["caliber"] or "—", r["verified"] or "—", r["status"]))
    pending = [r for r in rows if r["status"] != "已核"]
    lines += ["", "待核 %d 条。**没核过的事实不许进成片。**" % len(pending)]
    return {"markdown": "\n".join(lines), "count": len(rows),
            "pending": len(pending)}


def main():
    ap = argparse.ArgumentParser(description="Vflow 声明-证据台账")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add")
    p.add_argument("claim"); p.add_argument("--source"); p.add_argument("--caliber")
    p.add_argument("--slug"); p.add_argument("--verified")
    p.set_defaults(fn=cmd_add)

    p = sub.add_parser("list")
    p.add_argument("--slug"); p.add_argument("--status", choices=STATUSES)
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("scan"); p.add_argument("slug")
    p.set_defaults(fn=cmd_scan)

    p = sub.add_parser("verify"); p.add_argument("id"); p.add_argument("--date")
    p.set_defaults(fn=cmd_verify)

    p = sub.add_parser("stale"); p.add_argument("--days", type=int, default=90)
    p.set_defaults(fn=cmd_stale)

    p = sub.add_parser("report"); p.add_argument("slug")
    p.set_defaults(fn=cmd_report)

    args = ap.parse_args()
    json.dump(args.fn(args), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
