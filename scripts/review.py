#!/usr/bin/env python3
"""Vflow 复盘闭环：发布登记 → 待复盘队列 → 数据回填 → 联动钩子库和证据台账。

复盘不发生，风格卡、钩子库、证据台账就全是空转。这个脚本把复盘从
「要记得做」变成「不做就不算完」。

用法：
    python3 review.py published <slug> --platform douyin [--at "2026-10-24 20:00"] [--counts-as real|test]
    python3 review.py pending [--days 7]          看谁该复盘了（含超期）
    python3 review.py fill <slug> --platform douyin --play 12000 --ret5 45 --finish 28 \\
        --like 300 --comment 40 --save 120 --share 20 --follow 15 \\
        [--search-share 35] [--good "..." --bad "..." --comments "..." --action "..."]
    python3 review.py note <slug> "观察到的现象" [--again E1]
    python3 review.py stats [--platform douyin] [--bucket B]
    python3 review.py report                      输出 markdown 复盘汇总表

设计：
- 机器读 .vflow.json 的 metrics（唯一真源），06-review.md 的表格给人看，两边一起写。
- 填完数据 → 复盘阶段自动变 done；指标进 stats，同桶均值有了分母。
- 钩子编号记录在项目 .vflow.json 的 hooks 里，fill 时自动回填（一条数据仍不算数）。
- 观察只进台账，够三条可比证据才准 promote。

零依赖。
"""
import argparse
import json
import os
import re
import statistics
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import vflow_state as VS          # noqa: E402
import ledger as LG               # noqa: E402

ROOT = VS.ROOT
PLATFORMS = {"douyin": "抖音", "xhs": "小红书"}
METRIC_LABELS = [
    ("play", "播放 / 曝光", "播放"),
    ("ret5", "5 秒完播", "5秒完播"),
    ("finish", "完播率", "完播率"),
    ("like", "点赞", "点赞"),
    ("comment", "评论", "评论"),
    ("save", "收藏", "收藏"),
    ("share", "转发", "转发"),
    ("follow", "涨粉", "涨粉"),
    ("collect", "收藏率", "收藏率"),
    ("revisit", "复访率", "复访率"),
]
RATE_KEYS = ("ret5", "finish", "search_share", "collect", "revisit")


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def num(v):
    """'12,000' / '45%' / 45 / None → float 或 None。"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"-?\d+(?:\.\d+)?", str(v))
    return float(m.group(0)) if m else None


def fmt(v, rate=False):
    if v is None:
        return ""
    v = float(v)
    if rate:
        return ("%g%%" % v)
    if v == int(v):
        return format(int(v), ",") if abs(v) >= 1000 else "%d" % int(v)
    return "%g" % v


def parse_when(s):
    if not s:
        return None
    for f in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M", "%Y/%m/%d"):
        try:
            return datetime.strptime(s.strip(), f)
        except ValueError:
            continue
    return None


# ---------- 状态读写 ----------

def load_state(slug):
    st = VS.build_state(slug)
    return st


def save_state(slug, st):
    VS.write_state(slug, st)


def review_path(slug):
    return os.path.join(VS.slug_dir(slug), "06-review.md")


def ensure_review(slug):
    p = review_path(slug)
    if os.path.isfile(p):
        text = open(p, encoding="utf-8").read()
        if VS.TEMPLATE_MARK not in text:
            return text
        return text.replace(
            "<!-- vflow-template: 未填写 -->\n", "")
    # 没文件：从模板起一份
    tpl = os.path.join(ROOT, "pipeline", "06-review.md")
    text = ""
    if os.path.isfile(tpl):
        text = open(tpl, encoding="utf-8").read()
        text = text.replace("<!-- vflow-template: 未填写 -->\n", "")
    return text


def section_bounds(text, title):
    """返回 (heading_end, section_end)。找不到返回 None。"""
    m = re.search(r"^## %s\s*$" % re.escape(title), text, re.M)
    if not m:
        return None
    start = m.end()
    nxt = re.search(r"^## ", text[start:], re.M)
    end = start + nxt.start() if nxt else len(text)
    return start, end


def set_section(text, title, body):
    bounds = section_bounds(text, title)
    if not bounds:
        return text.rstrip() + "\n\n## %s\n\n%s\n" % (title, body.strip())
    start, end = bounds
    return text[:start] + "\n" + body.strip() + "\n\n" + text[end:]


def set_field(text, label, value):
    pat = r"^- \*\*%s\*\*：.*$" % re.escape(label)
    line = "- **%s**：%s" % (label, value)
    if re.search(pat, text, re.M):
        return re.sub(pat, line, text, count=1, flags=re.M)
    return text.rstrip() + "\n" + line + "\n"


# ---------- 数据表 ----------

def table_cell(value, rate):
    return fmt(value, rate) if value is not None else "—"


def render_table(metrics):
    header = "| 指标 | 抖音 | 小红书 |\n|---|---|---|"
    rows = [header]
    for _key, label, _mkey in METRIC_LABELS:
        cells = [table_cell((metrics.get("douyin") or {}).get(_mkey),
                            _key in RATE_KEYS),
                 table_cell((metrics.get("xhs") or {}).get(_mkey),
                            _key in RATE_KEYS)]
        rows.append("| %s | %s | %s |" % (label, cells[0], cells[1]))
    rows.append("| 搜索来源占比 | — | %s |" % table_cell(
        num((metrics.get("xhs") or {}).get("搜索来源占比")), True))
    rows.append("| 互动率 | %s | %s |" % (
        table_cell(num((metrics.get("douyin") or {}).get("互动率")), True),
        table_cell(num((metrics.get("xhs") or {}).get("互动率")), True)))
    return "\n".join(rows)


# ---------- 命令 ----------

def cmd_published(a):
    slug = a.slug
    if not os.path.isdir(VS.slug_dir(slug)):
        return {"error": "项目不存在: %s" % slug}
    st = load_state(slug)
    plat = st["published"].setdefault(a.platform, {})
    plat["published_at"] = a.at or now()
    # 重新登记发布 = 这次是真的发了；要保留 test 语义就显式传 --counts-as test
    plat["counts_as"] = a.counts_as or "real"
    if a.bucket:
        plat["bucket"] = a.bucket
    save_state(slug, st)
    when = parse_when(plat["published_at"]) or datetime.now()
    due = datetime.fromordinal(when.toordinal() + 2)
    return {"ok": True, "slug": slug, "platform": a.platform,
            "published_at": plat["published_at"],
            "review_due": due.strftime("%Y-%m-%d"),
            "next": "48 小时后回填：python3 scripts/review.py fill %s "
                    "--platform %s --play ..." % (slug, a.platform)}


def project_track(st, slug):
    """轨道：发布时登记的 track 优先，其次按平台推。"""
    for plat, pv in (st.get("published") or {}).items():
        if isinstance(pv, dict) and pv.get("track"):
            return pv["track"]
    plats = list((st.get("published") or {}).keys())
    if plats == ["xhs"]:
        return "深度轨"
    if "xhs" == plats[0] if plats else False:
        return "深度轨"
    return "发现轨"


def project_bucket(st, slug):
    for plat in st.get("published", {}).values():
        if plat.get("bucket"):
            return plat["bucket"]
    text = VS.read_text(os.path.join(VS.slug_dir(slug), "01-topic.md"))
    m = re.search(r"([ABC])\s*(演示|拆解|实录)型", text)
    return ("%s %s型" % (m.group(1), m.group(2))) if m else "未分桶"


def cmd_pending(a):
    rows = []
    for slug in VS.iter_slugs():
        st = load_state(slug)
        pub = st.get("published") or {}
        pub = {k: v for k, v in pub.items()
               if isinstance(v, dict) and v.get("counts_as", "real") == "real"}
        if not pub:
            continue
        has_data = bool(VS.review_numbers(slug))
        when = None
        for v in pub.values():
            when = parse_when(v.get("published_at")) or when
        age_h = (datetime.now() - when).total_seconds() / 3600 if when else None
        if has_data:
            continue
        overdue = age_h is not None and age_h > 24 * a.days
        rows.append({
            "slug": slug,
            "published_at": min(v.get("published_at", "") for v in pub.values()),
            "age_hours": round(age_h, 1) if age_h is not None else None,
            "due": age_h is not None and age_h >= 48,
            "overdue": overdue,
            "platforms": sorted(pub.keys()),
            "action": "python3 scripts/review.py fill %s --platform %s --play ..."
                      % (slug, sorted(pub.keys())[0]),
        })
    rows.sort(key=lambda r: -((r["age_hours"] or 0)))
    return {"pending": rows, "count": len(rows),
            "overdue": sum(1 for r in rows if r["overdue"])}


def cmd_fill(a):
    slug = a.slug
    if not os.path.isdir(VS.slug_dir(slug)):
        return {"error": "项目不存在: %s" % slug}
    st = load_state(slug)
    plat = a.platform

    raw = {
        "播放": num(a.play), "5秒完播": num(a.ret5),
        "完播率": num(a.finish), "点赞": num(a.like),
        "评论": num(a.comment), "收藏": num(a.save),
        "转发": num(a.share), "涨粉": num(a.follow),
        "收藏率": num(a.collect_rate), "复访率": num(a.revisit),
    }
    if plat == "xhs" and a.search_share is not None:
        raw["搜索来源占比"] = num(a.search_share)

    metrics = dict(st.get("metrics") or {})
    row = dict(metrics.get(plat) or {})
    for k, v in raw.items():
        if v is not None:
            row[k] = v

    eng = sum(row.get(k, 0) or 0 for k in ("点赞", "评论", "收藏", "转发"))
    play = row.get("播放") or 0
    if play:
        row["互动率"] = round(eng / play * 100, 2)
        # 没手填收藏率时，用收藏 / 播放算
        if row.get("收藏率") is None and row.get("收藏") is not None:
            row["收藏率"] = round(row["收藏"] / play * 100, 2)
    metrics[plat] = row
    st["metrics"] = metrics

    pub = st["published"].setdefault(plat, {})
    pub["reviewed_at"] = now()
    if a.bucket:
        pub["bucket"] = a.bucket
    if a.track:
        pub["track"] = a.track
    if pub.get("counts_as") is None:
        pub["counts_as"] = "real"

    # 写回 md：数据表 + 判断 + 下一条改什么
    text = ensure_review(slug)
    text = set_field(text, "发布日期", pub.get("published_at", ""))
    text = set_field(text, "复盘日期", now())
    text = set_field(text, "平台", PLATFORMS[plat])
    text = set_section(text, "数据", render_table(metrics))

    if a.good or a.bad or a.comments:
        body = ["**轨道 / 分桶**：%s · %s（发现轨看 5 秒留存 / 完播；"
                "深度轨看收藏率 / 搜索来源 / 复访）" % (
                    project_track(st, slug), project_bucket(st, slug))]
        if a.good:
            body.append("\n**这条好在哪**\n%s" % a.good.strip())
        if a.bad:
            body.append("\n**这条差在哪**\n%s" % a.bad.strip())
        if a.comments:
            body.append("\n**评论区在说什么**\n%s" % a.comments.strip())
        text = set_section(text, "判断", "\n".join(body))

    if a.action:
        text = set_section(text, "下一条改什么", a.action.strip())

    with open(review_path(slug), "w", encoding="utf-8") as fh:
        fh.write(text.rstrip() + "\n")

    # 联动：钩子回填 + 状态重算
    hooks_done = fill_hooks(slug, st, row, a)
    save_state(slug, st)
    note = None
    if a.observation:
        note = cmd_note(type("A", (), {
            "slug": slug, "text": a.observation,
            "again": a.again})())

    return {"ok": True, "slug": slug, "platform": plat,
            "metrics": row, "hooks": hooks_done,
            "observation": note,
            "review_stage": load_state(slug)["stages"]["07"]["status"],
            "next": "看同轨均值：python3 scripts/review.py stats --track %s"
                    % project_track(st, slug)}


def fill_hooks(slug, st, row, a):
    """把复盘数据回填到钩子库（比例口径与 hooks.md 的 3 秒留存对齐）。"""
    try:
        import hooks as HK
    except ImportError:
        return {"skipped": "hooks.py 不可用"}
    ids = st.get("hooks") or []
    if not ids:
        return {"skipped": "这个项目没记录用过哪个钩子（包装阶段跑 hooks.py use）"}
    ret5 = row.get("5秒完播")
    finish = row.get("完播率")
    verdict = a.hook_verdict
    if not verdict and ret5 is not None:
        verdict = "有效" if ret5 >= 45 else ("无效" if ret5 < 30 else "一般")
    out = []
    for hid in ids:
        args = type("A", (), {
            "hook": hid, "slug": slug,
            "ret3": ("%g%%" % ret5) if ret5 is not None else None,
            "finish": ("%g%%" % finish) if finish is not None else None,
            "verdict": verdict,
        })()
        out.append(HK.cmd_fill(args))
    return {"filled": out, "note": "5 秒完播被当成 3 秒留存的近似值；口径不同请手动改"}


def cmd_note(a):
    slug = a.slug
    if not os.path.isdir(VS.slug_dir(slug)):
        return {"error": "项目不存在: %s" % slug}
    LS = LG
    LS.ensure_file()
    rows = LS.parse(LS.read_text(LS.LEDGER_MD))
    text = ensure_review(slug)

    if a.again:
        res = LS.cmd_add(type("A", (), {
            "text": None, "slug": slug, "again": a.again})())
    else:
        res = LS.cmd_add(type("A", (), {
            "text": a.text, "slug": slug, "again": None})())
        # 同一个观察第二次出现时，自动再加一条证据
    if "error" in res:
        return res

    cand = res.get("id")
    n = res.get("count")
    body = ["- **观察**：%s" % (a.text or a.again),
            "- **台账编号**：%s（当前 %s 条证据）" % (cand, n),
            "- **够三条才升级**：`python3 scripts/ledger.py promote %s`" % cand]
    bounds = section_bounds(text, "观察记进台账（不直接改默认）")
    if bounds:
        text = set_section(text, "观察记进台账（不直接改默认）", "\n".join(body))
    else:
        text = text.rstrip() + "\n\n## 观察记进台账（不直接改默认）\n\n" + \
            "\n".join(body) + "\n"
    with open(review_path(slug), "w", encoding="utf-8") as fh:
        fh.write(text.rstrip() + "\n")
    save_state(slug, load_state(slug))
    return res


def collect(platform=None, bucket=None, track=None):
    recs = []
    for slug in VS.iter_slugs():
        st = load_state(slug)
        nums = VS.review_numbers(slug)
        if not nums:
            continue
        b = project_bucket(st, slug)
        tr = project_track(st, slug)
        if bucket and not b.startswith(bucket):
            continue
        if track and tr != track:
            continue
        for plat, vals in nums.items():
            if platform and plat != platform:
                continue
            recs.append({"slug": slug, "platform": plat,
                         "bucket": b, "track": tr, "vals": vals})
    return recs


def summarize(recs):
    keys = [("收藏率", "收藏率"), ("5秒完播", "5秒完播"),
            ("复访率", "复访率"), ("完播率", "完播率"),
            ("播放", "播放"), ("互动率", "互动率"), ("涨粉", "涨粉")]
    out = {"count": len(recs), "metrics": {}}
    for key, _label in keys:
        vals = [r["vals"][key] for r in recs if r["vals"].get(key) is not None]
        if vals:
            out["metrics"][key] = {
                "n": len(vals),
                "mean": round(statistics.mean(vals), 2),
                "median": round(statistics.median(vals), 2),
                "min": round(min(vals), 2),
                "max": round(max(vals), 2),
            }
    return out


def cmd_stats(a):
    recs = collect(a.platform, a.bucket, a.track)
    out = {"overall": summarize(recs), "buckets": {}, "platforms": {},
           "tracks": {}}
    buckets = sorted({r["bucket"] for r in recs})
    for b in buckets:
        out["buckets"][b] = summarize([r for r in recs if r["bucket"] == b])
    for p in sorted({r["platform"] for r in recs}):
        out["platforms"][p] = summarize([r for r in recs if r["platform"] == p])
    for tr in sorted({r["track"] for r in recs}):
        out["tracks"][tr] = summarize([r for r in recs if r["track"] == tr])
    out["note"] = ("样本少于 3 条时只能当参考，不能当规律。"
                   "跨轨道、跨桶比数据都会得出错误结论。")
    out["north_star"] = ("发现轨看 5 秒留存（≥45% 有效）；"
                         "深度轨看收藏率（方法类 ≥3%、观点类 ≥1.5% 有效）")
    return out


def cmd_report(a):
    recs = collect(a.platform, None)
    if not recs:
        return {"markdown": "还没有任何复盘数据。"}
    lines = ["# Vflow 复盘汇总", "",
             "生成：%s · 样本 %d 条（一条数据不是规律，三条可比才升级）" %
             (now(), len(recs)), ""]
    head = ("| 项目 | 平台 | 轨道 | 分桶 | 播放 | 5 秒完播 | 完播率 | "
            "收藏率 | 复访率 | 互动率 | 涨粉 |")
    lines += [head, "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in recs:
        v = r["vals"]
        lines.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r["slug"], PLATFORMS.get(r["platform"], r["platform"]), r["track"],
            r["bucket"], fmt(v.get("播放")), fmt(v.get("5秒完播"), True),
            fmt(v.get("完播率"), True), fmt(v.get("收藏率"), True),
            fmt(v.get("复访率"), True), fmt(v.get("互动率"), True),
            fmt(v.get("涨粉"))))
    s = summarize(recs)
    lines += ["", "## 同桶均值（全部样本）", ""]
    for k, st in s["metrics"].items():
        lines.append("- %s：均值 %s / 中位 %s（n=%d）" % (
            k, fmt(st["mean"]), fmt(st["median"]), st["n"]))
    md = "\n".join(lines)
    if a.out:
        out = a.out if os.path.isabs(a.out) else os.path.join(VS.ROOT, a.out)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(md + "\n")
        return {"out": out, "markdown": md}
    return {"markdown": md}


def main():
    ap = argparse.ArgumentParser(description="Vflow 复盘闭环")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("published")
    p.add_argument("slug")
    p.add_argument("--platform", required=True, choices=list(PLATFORMS))
    p.add_argument("--at")
    p.add_argument("--counts-as", choices=["real", "test"], default=None)
    p.add_argument("--bucket", choices=["A", "B", "C"])
    p.set_defaults(fn=cmd_published)

    p = sub.add_parser("pending")
    p.add_argument("--days", type=int, default=7)
    p.set_defaults(fn=cmd_pending)

    p = sub.add_parser("fill")
    p.add_argument("slug")
    p.add_argument("--platform", required=True, choices=list(PLATFORMS))
    for flag in ("play", "ret5", "finish", "like", "comment", "save",
                 "share", "follow", "search-share", "collect-rate", "revisit"):
        p.add_argument("--" + flag, dest=flag.replace("-", "_"))
    p.add_argument("--good"); p.add_argument("--bad")
    p.add_argument("--comments"); p.add_argument("--action")
    p.add_argument("--observation"); p.add_argument("--again")
    p.add_argument("--hook-verdict", choices=["有效", "一般", "无效"])
    p.add_argument("--bucket", choices=["A", "B", "C"])
    p.add_argument("--track", choices=["发现轨", "深度轨"])
    p.set_defaults(fn=cmd_fill)

    p = sub.add_parser("note")
    p.add_argument("slug"); p.add_argument("text", nargs="?")
    p.add_argument("--again")
    p.set_defaults(fn=cmd_note)

    p = sub.add_parser("stats")
    p.add_argument("--platform", choices=list(PLATFORMS))
    p.add_argument("--bucket", choices=["A", "B", "C"])
    p.add_argument("--track", choices=["发现轨", "深度轨"])
    p.set_defaults(fn=cmd_stats)

    p = sub.add_parser("report")
    p.add_argument("--platform", choices=list(PLATFORMS))
    p.add_argument("--out", default="dashboard/review.md")
    p.set_defaults(fn=cmd_report)

    args = ap.parse_args()
    result = args.fn(args)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
