#!/usr/bin/env python3
"""发布前敏感词扫描：词表兜底 + 模型判断之前的第一道网。

用法：
    python3 risk_scan.py <文件或目录>            扫描
    cat 稿子.md | python3 risk_scan.py -          从标准输入读
    python3 risk_scan.py <文件> --json            机器可读输出

设计：
1. 词表分四层：redline（必改）> ad-law（高）> platform（中）> mine（提示）
2. 只提示，不屏蔽。命中不等于违规，只等于"值得再看一眼"
3. 输出行号和上下文，方便直接定位
4. 平台规则会变，词表要人维护——踩到坑就往 mine 层加

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
WORDLIST = os.path.join(ROOT, "assets", "wordlist.md")

LEVELS = {
    "redline": ("红线", 3),
    "ad-law": ("广告法", 2),
    "platform": ("平台敏感", 1),
    "mine": ("自己踩过", 2),
}


def load_words():
    """从 wordlist.md 按 ## 标题解析层级。"""
    table = {}
    if not os.path.isfile(WORDLIST):
        return table
    cur = None
    with open(WORDLIST, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            m = re.match(r"^##\s+(\S+)", line)
            if m:
                cur = m.group(1)
                table.setdefault(cur, [])
                continue
            if not cur or line.startswith("#") or line.startswith(">"):
                continue
            if line.startswith("-"):
                line = line[1:]
            # 去掉「导流类：」「不承诺收益类：」这类分组前缀
            line = re.sub(r"^[^：:]{1,10}[：:]", "", line)
            line = re.sub(r"（[^）]*）", "", line)
            for w in re.split(r"[、,，\s]+", line):
                w = w.strip()
                if w and len(w) >= 2 and not w.startswith("（"):
                    table[cur].append(w)
    return table


def scan_text(text, table, source="-"):
    hits = []
    lines = text.split("\n")
    for level, words in table.items():
        if level not in LEVELS:
            continue
        label, weight = LEVELS[level]
        for w in set(words):
            for i, line in enumerate(lines, 1):
                if w in line:
                    # 去掉 markdown 标记做上下文展示
                    ctx = re.sub(r"[*_`#|]", "", line).strip()
                    hits.append({
                        "level": level, "label": label, "weight": weight,
                        "word": w, "line": i, "context": ctx[:80],
                        "file": source,
                    })
    hits.sort(key=lambda h: (-h["weight"], h["line"]))
    return hits


def collect(paths, table):
    hits = []
    for p in paths:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                if "/drafts" in root or "/output" in root:
                    continue
                for f in sorted(files):
                    if f.endswith(".md"):
                        hits += scan_text(
                            open(os.path.join(root, f), encoding="utf-8").read(),
                            table, os.path.relpath(os.path.join(root, f), ROOT))
        elif os.path.isfile(p):
            hits += scan_text(
                open(p, encoding="utf-8").read(), table,
                os.path.relpath(p, ROOT))
    return hits


def render(hits):
    if not hits:
        return "没命中词表。注意：这不代表安全，模型那层还要过一遍。"
    out = ["命中 %d 处，按严重度排：\n" % len(hits)]
    cur = None
    for h in hits:
        if h["label"] != cur:
            cur = h["label"]
            out.append("【%s】" % cur)
        out.append("  %s:%s  「%s」" % (h["file"], h["line"], h["word"]))
        out.append("      %s" % h["context"])
    out.append("\n只提示，不屏蔽。命中不等于违规，自己判断。")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Vflow 敏感词扫描")
    ap.add_argument("paths", nargs="*", help="文件或目录，不给就从标准输入读")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    table = load_words()
    if not table:
        print("词表没读到：%s" % WORDLIST)
        sys.exit(1)

    if args.paths:
        hits = collect(args.paths, table)
    else:
        hits = scan_text(sys.stdin.read(), table, "stdin")

    if args.json:
        json.dump({"count": len(hits), "hits": hits},
                  sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        print(render(hits))


if __name__ == "__main__":
    main()
