#!/usr/bin/env python3
"""声音档案：从你自己的成稿里提取可量化的文风特征。

用途：
    python3 voice_profile.py build                从 assets/voice-samples/ 生成风格卡
    python3 voice_profile.py compare <文件>        拿一篇稿子跟风格卡比对，看跑偏在哪
    python3 voice_profile.py show                  打印当前风格卡

为什么不用 profile.md 里那几条规则：
    规则写的是"应该"（说人话、先给结论），模型照着写还是像 AI。
    风格卡写的是"实测"（你平均句长 18 字、每百字 1.8 次说"我"），
    模型照数字对齐，出来的东西才像你。

零依赖，只用标准库。
"""
import argparse
import json
import os
import re
import sys
import glob
from datetime import datetime
from collections import Counter

ROOT = os.path.abspath(
    os.environ.get("VFLOW_HOME") or os.path.expanduser("~/Vflow")
)
SAMPLES = os.path.join(ROOT, "assets", "voice-samples")
CARD_MD = os.path.join(ROOT, "assets", "voice-card.md")
CARD_JSON = os.path.join(ROOT, "assets", "voice-card.json")

# 统计高频片段时要忽略的字和词
STOP = set("的了是在我有就都也还很吧呢啊把被给对从到和与及但不过还是这个那个什么怎么"
           "一二三不没有会要能说得看好做用让")
SENT_SPLIT = re.compile(r"[。！？!?；;\n]+")

# 语气标记：这些词决定"像不像你"，比主题词有用得多
TONE = ["说白了", "其实", "你会发现", "你看", "关键是", "问题在于", "换句话说",
        "也就是说", "坦白说", "说到底", "注意", "先看", "再看", "所以", "但是",
        "不过", "然后", "举个例子", "比如", "真正", "别", "不要", "记住",
        "有意思的是", "坏消息", "好消息", "简单说", "一句话", "结论是",
        "先说结论", "说清楚", "你猜", "说穿了", "说回来", "重点来了",
        "我先说", "最后是", "还有一点", "反过来", "这时候"]


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return ""


def strip_md(text):
    """去掉 markdown 标记，只留正文。"""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"^#{1,6}\s.*$", "", text, flags=re.M)
    text = re.sub(r"^[-*|>\s]+", "", text, flags=re.M)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[*_`]", "", text)
    return text


def sentences(text):
    return [s.strip() for s in SENT_SPLIT.split(text) if len(s.strip()) >= 2]


def ngrams(text, n):
    """连续 n 字片段，跳过含停用字或跨标点的。"""
    out = []
    for seg in re.split(r"[^\u4e00-\u9fff]+", text):
        for i in range(len(seg) - n + 1):
            g = seg[i:i + n]
            if any(c in STOP for c in g):
                continue
            out.append(g)
    return out


def analyze(text):
    text = strip_md(text)
    sents = sentences(text)
    lens = sorted(len(s) for s in sents)
    n = len(lens) or 1
    total = max(len(text), 1)

    c = Counter()
    for size in (2, 3, 4):
        c.update(ngrams(text, size))
    # 长片段优先，去掉被更长片段包住的高频短片段
    top = []
    for g, cnt in c.most_common(200):
        if cnt < 3:
            break
        if any(g in t[0] for t in top):
            continue
        top.append((g, cnt))
        if len(top) >= 12:
            break

    tone = []
    for w in TONE:
        cnt = text.count(w)
        if cnt:
            tone.append((w, round(cnt / (total / 1000), 2)))
    tone.sort(key=lambda x: -x[1])

    return {
        "chars": len(text),
        "sentences": len(sents),
        "avg_sent_len": round(sum(lens) / n, 1),
        "median_sent_len": lens[n // 2] if lens else 0,
        "max_sent_len": lens[-1] if lens else 0,
        "short_sent_ratio": round(
            sum(1 for x in lens if x <= 15) / n, 2),
        "question_ratio": round(
            text.count("？") + text.count("?"), 3) and round(
            (text.count("？") + text.count("?")) / max(len(sents), 1), 2),
        "exclaim_ratio": round(
            (text.count("！") + text.count("!")) / max(len(sents), 1), 2),
        "first_person_per_100": round(
            (text.count("我") + text.count("我们")) / total * 100, 2),
        "latin_per_1000": round(
            len(re.findall(r"[A-Za-z]{2,}", text)) / total * 1000, 1),
        "emoji": len(re.findall(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", text)),
        "tone_markers": tone[:12],
        "top_phrases": top,
    }


def build():
    files = sorted(glob.glob(os.path.join(SAMPLES, "*.md")) +
                   glob.glob(os.path.join(SAMPLES, "*.txt")))
    # 目录里的 README 是说明，不是样本，别算进去
    files = [f for f in files
             if not os.path.basename(f).lower().startswith("readme")]
    if not files:
        return {"error": "assets/voice-samples/ 里没有样本。放 2–3 篇你自己写过的成稿进去（.md 或 .txt）。"}

    merged = "\n\n".join(read_text(f) for f in files)
    stat = analyze(merged)
    stat["samples"] = [os.path.basename(f) for f in files]
    stat["built_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 样本里从没出现过的常见 AI 腔/黑话，作为禁忌
    banned = ["赋能", "抓手", "底层逻辑", "闭环", "颗粒度", "对齐", "打法",
              "护城河", "生态位", "组合拳", "总而言之", "综上所述", "值得一提",
              "不难看出", "众所周知"]
    stat["absent"] = [w for w in banned if w not in merged]

    with open(CARD_JSON, "w", encoding="utf-8") as fh:
        json.dump(stat, fh, ensure_ascii=False, indent=2)
    with open(CARD_MD, "w", encoding="utf-8") as fh:
        fh.write(render(stat))
    return stat


def render(s):
    lines = [
        "# 声音档案",
        "",
        "> 由 %d 篇样本自动提取，%s。写稿前读这份，写完跑 `compare` 看跑偏没有。"
        % (len(s.get("samples", [])), s.get("built_at", "")),
        "> 样本：%s" % "、".join(s.get("samples", [])),
        "",
        "## 量化特征",
        "",
        "| 指标 | 你的实测值 |",
        "|---|---|",
        "| 平均句长 | %s 字 |" % s["avg_sent_len"],
        "| 句长中位数 | %s 字 |" % s["median_sent_len"],
        "| 最长句 | %s 字 |" % s["max_sent_len"],
        "| 短句（≤15 字）占比 | %s |" % s["short_sent_ratio"],
        "| 问句占句数 | %s |" % s["question_ratio"],
        "| 感叹占句数 | %s |" % s["exclaim_ratio"],
        "| 每百字「我/我们」 | %s 次 |" % s["first_person_per_100"],
        "| 每千字英文词 | %s 处 |" % s["latin_per_1000"],
        "| emoji | %s 个 |" % s["emoji"],
        "",
        "## 语气标记（每千字出现次数，这是最像你的部分）",
        "",
    ]
    if s.get("tone_markers"):
        for w, f in s["tone_markers"]:
            lines.append("- %s —— %s 次/千字" % (w, f))
    else:
        lines.append("- （样本里没检测到，说明你不太用这类语气词，或者样本太少）")
    lines += [
        "",
        "## 高频词（参考，主要反映选题而不是文风）",
        "",
    ]
    if s["top_phrases"]:
        lines.append("、".join("%s(%d)" % (g, c) for g, c in s["top_phrases"][:8]))
    lines += ["", "## 样本里从没出现过的词（写了就不像你）", ""]
    lines += ["- %s" % w for w in s.get("absent", [])] or ["- （无）"]
    lines += [
        "",
        "## 用法",
        "",
        "1. 写稿前：`python3 scripts/voice_profile.py show` 读一遍数字",
        "2. 写完：`python3 scripts/voice_profile.py compare projects/<slug>/03-script.md`",
        "3. 偏离超过阈值的项，改到范围内再往下走",
        "",
    ]
    return "\n".join(lines)


def compare(path):
    card = None
    if os.path.isfile(CARD_JSON):
        try:
            card = json.loads(read_text(CARD_JSON))
        except json.JSONDecodeError:
            card = None
    if not card:
        return {"error": "还没有风格卡，先跑 build"}

    text = read_text(path)
    if not text.strip():
        return {"error": "文件是空的: %s" % path}
    cur = analyze(text)

    def diff(key, label, tol):
        a, b = card.get(key, 0), cur.get(key, 0)
        if a == 0:
            return None
        delta = abs(b - a) / a
        if delta <= tol:
            return None
        return {
            "item": label, "yours": a, "this": b,
            "verdict": "偏高" if b > a else "偏低",
            "gap": round(delta, 2),
        }

    issues = [x for x in [
        diff("avg_sent_len", "平均句长", 0.35),
        diff("short_sent_ratio", "短句占比", 0.4),
        diff("first_person_per_100", "第一人称密度", 0.5),
        diff("question_ratio", "问句密度", 0.6),
        diff("latin_per_1000", "中英混排密度", 0.6),
        diff("emoji", "emoji 数量", 0.8),
    ] if x]

    hits = [w for w in card.get("absent", []) if w in text]

    return {
        "file": path,
        "this": {k: cur[k] for k in
                 ("chars", "sentences", "avg_sent_len", "short_sent_ratio",
                  "first_person_per_100", "question_ratio", "latin_per_1000",
                  "emoji")},
        "card": {k: card.get(k) for k in
                 ("avg_sent_len", "short_sent_ratio", "first_person_per_100",
                  "question_ratio", "latin_per_1000", "emoji")},
        "deviations": issues,
        "banned_hits": hits,
        "verdict": "通过" if not issues and not hits else "有偏离，看上面",
    }


def main():
    ap = argparse.ArgumentParser(description="Vflow 声音档案")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build").set_defaults(fn=lambda a: build())
    sub.add_parser("show").set_defaults(
        fn=lambda a: {"card": read_text(CARD_MD)} if os.path.isfile(CARD_MD)
        else {"error": "还没有风格卡，先跑 build"})
    p = sub.add_parser("compare")
    p.add_argument("file")
    p.set_defaults(fn=lambda a: compare(a.file))

    args = ap.parse_args()
    json.dump(args.fn(args), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
