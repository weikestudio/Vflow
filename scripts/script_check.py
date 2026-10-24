#!/usr/bin/env python3
"""口播稿机器自检：按双轨阈值查留存、可保存物、CTA、节奏和 AI 味。

不能替你判断"讲得好不好"，但能拦住最容易犯的硬伤：开头慢热、
前 1/3 没有可保存物、结尾还是在求点赞、一句话太长、整段没有变化。

用法：
    python3 script_check.py <slug> [--track 发现轨|深度轨] [--json]
    python3 script_check.py <slug> --include-check   # 连检查稿一起查（04/05）

结果追加到 03-script.md 的「## 机器自检」节，同时写 .vflow.json 的 scriptQc。
有 FAIL → 退出码 1。

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

import vflow_state as VS          # noqa: E402

ROOT = VS.ROOT
SECTION = "机器自检"
MARKER = "vflow-script-qc"

# 双轨阈值（5 秒留存口径，第三方整理，非平台官方口径）
TRACK = {
    "发现轨": {"min_sec": 40, "max_sec": 100, "page_sec": (8, 12)},
    "深度轨": {"min_sec": 85, "max_sec": 200, "page_sec": (15, 20)},
}
RATE_PER_SEC = 4.2

# 慢热开头：出现在前两句就是 FAIL
SLOW_PATTERNS = [
    r"^(大家好|各位好|哈喽|Hello|hi)",
    r"^(今天|这期|本期)我?们?(来|要)?(聊|讲|说|分享)",
    r"^我想(说|讲|聊)",
    r"^(我先(说|讲)|先说一个|我跟你讲|先跟你讲)",
    r"^(首先|今天给大家)",
    r"^在(这个|如今|当下)",
    r"^(随着|随着时代)",
]
SLOW_LABEL = {
    SLOW_PATTERNS[0]: "大家好 / 各位好",
    SLOW_PATTERNS[1]: "今天我们来聊",
    SLOW_PATTERNS[2]: "我想说",
    SLOW_PATTERNS[3]: "我先说 / 先说一个",
    SLOW_PATTERNS[4]: "首先",
    SLOW_PATTERNS[5]: "在这个时代",
    SLOW_PATTERNS[6]: "随着……",
}
# 空转的 re-hook：只喊"但是更重要"没有新东西
EMPTY_REHOOK = [r"但是更重要", r"更重要的", r"真正重要的是", r"然而"]
# 指向错误动作的 CTA
BAD_CTA = [r"点个?赞", r"点赞", r"求赞", r"双击", r"关注我", r"转发一下"]
GOOD_CTA = [r"收藏", r"存下", r"存起来", r"截个?图", r"码住", r"记下"]
# AI 味 / 书面语
AI_WORDS = ["赋能", "抓手", "底层逻辑", "闭环", "颗粒度", "对齐", "综上所述",
            "总而言之", "首先", "其次", "最后一点", "值得注意的是"]
# 可保存物线索
SAVE_CUES = [r"标准", r"清单", r"步骤", r"判断", r"对照", r"三条", r"四个",
             r"检查表", r"公式", r"参数", r"流程", r"方法", r"模板", r"动作"]


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def read(p):
    return VS.read_text(p)


def num(v):
    if v is None:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", str(v))
    return float(m.group(0)) if m else None


# ---------- 解析稿件 ----------

def parse_head(text):
    """稿件头里的结构化字段。"""
    def field(*names):
        for n in names:
            m = re.search(r"^- \*\*%s\*\*[：:]\s*(.+)$" % re.escape(n),
                          text, re.M)
            if not m:
                continue
            v = m.group(1).strip()
            # 空值时下一个字段会粘上来，导致误读
            if v.startswith("- **") or v in ("", "—"):
                continue
            return v
        return None
    return {
        "template": field("结构模板", "模板"),
        "judgment": field("核心判断", "判断"),
        "saveable": field("可保存物"),
        "loop": field("开放循环"),
        "rehook": field("中段 re-hook", "中段 rehook", "re-hook"),
        "action": field("结尾动作", "动作"),
        "target": field("目标时长"),
        "track": field("轨道"),
    }


def script_body(text):
    """只取『## 逐字稿』到下一个 ## 之间的正文，去掉表格和画面标记。"""
    m = re.search(r"^##\s*逐字稿\s*$", text, re.M)
    if not m:
        return ""
    start = m.end()
    nxt = re.search(r"^##\s+", text[start:], re.M)
    body = text[start:start + nxt.start()] if nxt else text[start:]
    lines = []
    for line in body.split("\n"):
        if line.strip().startswith("|"):
            continue
        line = re.sub(r"^>+\s?", "", line)
        line = re.sub(r"（[^）]*秒[^）]*）", "", line)  # 时间标注
        line = re.sub(r"^\*\*[^*]+\*\*\s*$", "", line)   # 加粗页标题
        line = re.sub(r"【[^】]*】", "", line)          # 画面提示
        lines.append(line.strip())
    return "\n".join(lines)


def sentences(body):
    parts = re.split(r"[。！？!?\n]+", body)
    return [p.strip() for p in parts if p.strip()]


def pages(text, body):
    """按 P1..Pn 或 【第 N 页】切页，返回 [(标题, 正文)]。"""
    out = []
    pattern = re.compile(
        r"^\*\*(P\d+[^*]*|第\s*\d+\s*页[^*]*)\*\*(?:\s*[（(][^）)]*[）)])?\s*$",
        re.M)
    marks = list(pattern.finditer(text))
    if not marks:
        return []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        chunk = text[m.end():end]
        chunk = re.sub(r"^##\s+.*$", "", chunk, flags=re.M)
        chunk = re.sub(r"【[^】]*】", "", chunk)
        chunk = "\n".join(re.sub(r"^>+\s?", "", l).strip()
                          for l in chunk.split("\n"))
        out.append((m.group(1).strip(), chunk))
    return out


def count_hook_variants(text):
    """钩子变体表里有几行（按不同原型算）。"""
    m = re.search(r"^##\s*钩子变体.*?$", text, re.M)
    if not m:
        return 0, []
    start = m.end()
    nxt = re.search(r"^##\s+", text[start:], re.M)
    chunk = text[start:start + nxt.start()] if nxt else text[start:]
    rows = []
    for line in chunk.split("\n"):
        if not line.startswith("|") or "---" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 3 and cells[0] not in ("#", ""):
            if re.match(r"^[A-Za-z]|^\d+$", cells[0]):
                rows.append(cells)
    proto = {r[1] for r in rows if len(r) > 1 and r[1] and r[1] != "H__"}
    # 占位行（还没填）不计
    filled = [r for r in rows if len(r) > 2 and len(r[2]) > 4]
    return len(filled), sorted(proto)


# ---------- 检查 ----------

def check(slug, track=None):
    text = read(os.path.join(VS.slug_dir(slug), "03-script.md"))
    rows = []
    if not text.strip() or VS.TEMPLATE_MARK in text:
        rows.append(("稿件", "SKIP", "03-script.md 还是空模板"))
        return rows, {}, text

    head = parse_head(text)
    body = script_body(text)
    if not body.strip():
        rows.append(("稿件正文", "FAIL", "找不到『## 逐字稿』正文"))
        return rows, head, text
    sents = sentences(body)
    chars = len(re.sub(r"\s", "", body))
    est = round(chars / RATE_PER_SEC)

    track = track or ("深度轨" if "深度轨" in (head.get("track") or "")
                      else "发现轨")
    th = TRACK.get(track, TRACK["发现轨"])
    head["track_used"] = track

    # 1. 结构模板
    if head.get("template"):
        rows.append(("结构模板", "PASS", head["template"]))
    else:
        rows.append(("结构模板", "FAIL", "稿件头没写用了哪个模板（T1–T6）"))

    # 2. 慢热开头
    first = "".join(sents[:2])
    slow = [p for p in SLOW_PATTERNS if re.search(p, first)]
    if slow:
        rows.append(("开头 2 句", "FAIL",
                     "慢热开头：%s。前 2 句必须是判断 / 冲突 / 数字"
                     % SLOW_LABEL.get(slow[0], slow[0])))
    else:
        rows.append(("开头 2 句", "PASS", first[:40] or "—"))

    # 3. 钩子变体
    n_var, protos = count_hook_variants(text)
    if n_var >= 3 and len(protos) >= 3:
        rows.append(("钩子变体", "PASS", "%d 个，原型 %s" % (n_var, "、".join(protos))))
    elif n_var >= 3:
        rows.append(("钩子变体", "WARN",
                     "%d 个但原型只有 %d 种，要不同原型不是改写" % (n_var, len(protos))))
    else:
        rows.append(("钩子变体", "WARN",
                     "只找到 %d 个变体，建议 3 个不同原型" % n_var))

    # 4. 开放循环 + re-hook
    if head.get("loop"):
        rows.append(("开放循环", "PASS", head["loop"][:40]))
    else:
        rows.append(("开放循环", "WARN", "稿件头没写开放循环，中段容易散"))
    if head.get("rehook"):
        empty = [p for p in EMPTY_REHOOK if re.search(p, head["rehook"])]
        if empty:
            rows.append(("中段 re-hook", "WARN",
                         "写的是空转句（%s），要接一个新东西" % empty[0]))
        else:
            rows.append(("中段 re-hook", "PASS", head["rehook"][:40]))
    else:
        rows.append(("中段 re-hook", "WARN", "没写，50% 附近最容易掉完播"))

    # 5. 可保存物（硬门槛）
    type_hint = ("B" if "拆解" in text else
                 "A" if "演示" in text else
                 "C" if "实录" in text else "")
    if head.get("saveable"):
        first_third = body[:max(1, len(body) // 3)]
        early = 1 if any(re.search(c, first_third) for c in SAVE_CUES) else 0
        # 稿件头写了「第 N 秒」时按时间判断，比按字数切更准
        m_at = re.search(r"第\s*(\d+)\s*秒", head["saveable"])
        if m_at and est:
            early = 1 if int(m_at.group(1)) <= est * 0.4 else 0
        status = "PASS" if early else "WARN"
        note = head["saveable"][:40]
        if not early:
            note += "（前 1/3 没看到明显的可保存物线索，确认一下位置）"
        rows.append(("可保存物", status, note))
    else:
        rows.append(("可保存物", "FAIL",
                     "稿件头没写可保存物；%s型内容没有它不许进制作"
                     % (type_hint or "B/A/C")))

    # 6. CTA
    tail = "".join(sents[-4:])
    if any(re.search(p, tail) for p in BAD_CTA) and \
            not any(re.search(p, tail) for p in GOOD_CTA):
        rows.append(("结尾 CTA", "WARN",
                     "结尾在求点赞/关注，双轨口径下应指向收藏或关注后回访"))
    elif any(re.search(p, tail) for p in GOOD_CTA):
        rows.append(("结尾 CTA", "PASS", "指向收藏/截图等可保存动作"))
    else:
        rows.append(("结尾 CTA", "WARN", "结尾没有明确动作"))

    # 7. 时长
    if est < th["min_sec"]:
        rows.append(("时长", "WARN",
                     "估算 %d 秒，%s 建议 %d–%d 秒"
                     % (est, track, th["min_sec"], th["max_sec"])))
    elif est > th["max_sec"]:
        rows.append(("时长", "WARN",
                     "估算 %d 秒，超过 %s 上限 %d 秒，考虑拆条或压到深度轨"
                     % (est, track, th["max_sec"])))
    else:
        rows.append(("时长", "PASS", "估算 %d 秒（%s）" % (est, track)))

    # 8. 句长
    if sents:
        lens = [len(s) for s in sents]
        long_s = [s for s in sents if len(s) > 25]
        avg = sum(lens) / len(lens)
        if long_s:
            rows.append(("句长", "WARN",
                         "平均 %.1f 字；%d 句超过 25 字，例：%s"
                         % (avg, len(long_s), long_s[0][:30])))
        else:
            rows.append(("句长", "PASS", "平均 %.1f 字，无超长句" % avg))

    # 9. AI 味 / 书面语
    hits = [w for w in AI_WORDS if w in body]
    if hits:
        rows.append(("AI 味用词", "WARN", "命中：%s" % "、".join(hits)))
    else:
        rows.append(("AI 味用词", "PASS", "无书面语连接词"))

    # 10. 开头两句的钩子密度
    if len(first) < 6:
        rows.append(("钩子信息量", "WARN", "开头太短，可能没给判断"))
    else:
        rows.append(("钩子信息量", "PASS", "前两句 %d 字" % len(first)))

    # 11. 节奏：每页字数是否接近轨道节拍
    pgs = pages(text, body)
    if pgs:
        page_chars = [len(re.sub(r"\s", "", c)) for _, c in pgs]
        big = [i + 1 for i, c in enumerate(page_chars)
               if c / RATE_PER_SEC > th["page_sec"][1] + 6]
        if big:
            rows.append(("节奏", "WARN",
                         "第 %s 页超过 %d 秒没有变化，考虑拆页或加画面"
                         % ("、".join(map(str, big[:4])), th["page_sec"][1])))
        else:
            rows.append(("节奏", "PASS",
                         "%d 页，每页约 %.1f 秒"
                         % (len(pgs), sum(page_chars) / len(page_chars) /
                            RATE_PER_SEC)))

    # 12. 重复句
    norm = [re.sub(r"[，。！？、\s]", "", s) for s in sents if len(s) > 6]
    dup = {s for s in norm if norm.count(s) > 1}
    if dup:
        rows.append(("重复", "WARN", "重复句：%s" % " / ".join(list(dup)[:2])[:60]))
    else:
        rows.append(("重复", "PASS", "无重复句"))

    # 13. 口语标记密度（太低像书面稿）
    markers = len(re.findall(r"所以|其实|你看|说白了|对吧|真的|就是", body))
    per_k = markers / max(1, chars / 1000)
    rows.append(("口语度", "PASS" if per_k >= 3 else "WARN",
                 "语气标记 %.1f 次/千字%s"
                 % (per_k, "" if per_k >= 3 else "（低于 3 偏低，像书面稿）")))

    meta = {"track": track, "chars": chars, "est_sec": est,
            "pages": len(pgs), "sentences": len(sents),
            "template": head.get("template"), "saveable": head.get("saveable")}
    return rows, meta, text


# ---------- 写回 ----------

def render(rows, meta):
    lines = ["<!-- %s %s -->" % (MARKER, json.dumps(
        {"generated": now(), **meta}, ensure_ascii=False)), ""]
    lines.append("生成：%s · 轨道：%s · 估算 %d 秒 %s · 结论：**%s**" % (
        now(), meta.get("track", "—"), meta.get("est_sec", 0),
        ("/ %d 页" % meta["pages"]) if meta.get("pages") else "",
        "通过" if not any(r[1] == "FAIL" for r in rows) else "有未通过项"))
    lines += ["", "| 检查项 | 结果 | 详情 |", "|---|---|---|"]
    for item, status, detail in rows:
        icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌", "SKIP": "⏭"}.get(
            status, status)
        lines.append("| %s | %s | %s |" % (item, icon + " " + status, detail))
    return "\n".join(lines)


def write_back(slug, block):
    path = os.path.join(VS.slug_dir(slug), "03-script.md")
    text = read(path)
    text = text.replace("<!-- vflow-template: 未填写 -->\n", "")
    section = "## %s\n\n%s" % (SECTION, block.strip())
    m = re.search(r"^##\s*%s\s*$" % re.escape(SECTION), text, re.M)
    if m:
        nxt = re.search(r"^##\s+", text[m.end():], re.M)
        end = m.end() + nxt.start() if nxt else len(text)
        text = text[:m.start()] + section + "\n\n" + text[end:]
    else:
        text = text.rstrip() + "\n\n" + section + "\n"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text.rstrip() + "\n")


def main():
    ap = argparse.ArgumentParser(description="Vflow 口播稿机器自检")
    ap.add_argument("slug")
    ap.add_argument("--track", choices=list(TRACK))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--include-check", action="store_true")
    args = ap.parse_args()

    if not os.path.isdir(VS.slug_dir(args.slug)):
        print(json.dumps({"error": "项目不存在：%s" % args.slug},
                         ensure_ascii=False), file=sys.stderr)
        sys.exit(2)

    rows, meta, _text = check(args.slug, args.track)
    block = render(rows, meta)
    write_back(args.slug, block)

    st = VS.build_state(args.slug)
    st["scriptQc"] = {
        "generated": now(),
        "fail": sum(1 for r in rows if r[1] == "FAIL"),
        "warn": sum(1 for r in rows if r[1] == "WARN"),
        "track": meta.get("track"),
        "est_sec": meta.get("est_sec"),
    }
    VS.write_state(args.slug, st)

    result = {"slug": args.slug, "fail": st["scriptQc"]["fail"],
              "warn": st["scriptQc"]["warn"], "meta": meta,
              "rows": [{"item": i, "status": s, "detail": d} for i, s, d in rows]}
    if args.json:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌", "SKIP": "⏭"}
        for i, s, d in rows:
            print("%s %s：%s" % (icon.get(s, s), i, d))
        print("\n结论：%s（FAIL %d / WARN %d）" % (
            "通过" if result["fail"] == 0 else "有未通过项",
            result["fail"], result["warn"]))
    sys.exit(0 if result["fail"] == 0 else 1)


if __name__ == "__main__":
    main()
