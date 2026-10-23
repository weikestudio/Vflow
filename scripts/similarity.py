#!/usr/bin/env python3
"""二创边界自检：改写稿跟原稿到底有多像。

用法：
    python3 similarity.py <原稿> <改写稿>
    python3 similarity.py <原稿> <改写稿> --json

为什么需要它：
    vflow-topic 让你"抄机制"（钩子在第几秒、结构怎么排），这没问题。
    但抄着抄着容易变成"换个说法的同一段话"——平台判同质化，观众也看得出来。
    这个脚本把"像不像"变成数字，并指出**具体哪几句太像**，直接能改。

判定标准（可改）：
    < 0.30  安全：借的是结构，句子是自己写的
    0.30–0.50  需检查：看列出的相似句，逐句改
    > 0.50  高风险：基本是改写级别的照搬，要重写

零依赖。
"""
import argparse
import difflib
import json
import os
import re
import sys

SAFE, WARN = 0.30, 0.50


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return ""


def normalize(text):
    text = re.sub(r"^#{1,6}\s.*$", "", text, flags=re.M)
    text = re.sub(r"^[-*|>\s]+", "", text, flags=re.M)
    text = re.sub(r"[*_`（）()【】\[\]“”\"'「」：:，,。.！!？?；;、\s]", "", text)
    return text


def sentences(text):
    out = [s for s in re.split(r"[。！？!?\n]+", text) if len(s.strip()) >= 6]
    return [s.strip() for s in out]


def grams(text, n=4):
    return {text[i:i + n] for i in range(len(text) - n + 1)}


def coverage(src, dst, n=4):
    """dst 里有多少比例的 n-gram 来自 src。看的是"搬了多少原料"。"""
    a, b = grams(src, n), grams(dst, n)
    if not b:
        return 0.0
    return len(a & b) / len(b)


def jaccard(src, dst, n=4):
    a, b = grams(src, n), grams(dst, n)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def top_pairs(src_sents, dst_sents, k=3):
    out = []
    for ds in dst_sents:
        best, best_r = None, 0
        for ss in src_sents:
            r = difflib.SequenceMatcher(None, ss, ds).ratio()
            if r > best_r:
                best, best_r = ss, r
        if best and best_r >= 0.55:
            out.append({"score": round(best_r, 2),
                        "src": best[:60], "dst": ds[:60]})
    out.sort(key=lambda x: -x["score"])
    return out[:k]


def check(src_path, dst_path):
    src_raw, dst_raw = read_text(src_path), read_text(dst_path)
    if not src_raw.strip() or not dst_raw.strip():
        return {"error": "两个文件都得有内容"}
    src, dst = normalize(src_raw), normalize(dst_raw)

    cov = coverage(src, dst)
    jac = jaccard(src, dst)
    overall = round(cov * 0.6 + jac * 0.4, 3)
    pairs = top_pairs(sentences(src_raw), sentences(dst_raw))

    if overall < SAFE:
        verdict = "安全"
    elif overall < WARN:
        verdict = "需检查"
    else:
        verdict = "高风险"

    return {
        "src": os.path.basename(src_path),
        "dst": os.path.basename(dst_path),
        "coverage": round(cov, 3),
        "jaccard": round(jac, 3),
        "overall": overall,
        "verdict": verdict,
        "similar_sentences": pairs,
        "advice": ADVICE[verdict],
    }


ADVICE = {
    "安全": "借的是结构，句子是你自己的。可以过。",
    "需检查": "下面几句跟原稿太像，逐句改掉再过。改法：换案例、换视角、换表述，别只换同义词。",
    "高风险": "这是改写级照搬，不是二创。重写：保留它的结构和节奏，把论据和表达全部换成你自己的。",
}


def main():
    ap = argparse.ArgumentParser(description="Vflow 二创相似度自检")
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    r = check(args.src, args.dst)

    if args.json:
        json.dump(r, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return

    if "error" in r:
        print(r["error"])
        sys.exit(1)
    print("原稿：%s" % r["src"])
    print("改写：%s" % r["dst"])
    print("整体相似度：%s（覆盖率 %s / 重合度 %s）"
          % (r["overall"], r["coverage"], r["jaccard"]))
    print("判定：%s" % r["verdict"])
    print(r["advice"])
    if r["similar_sentences"]:
        print("\n最像的几句：")
        for p in r["similar_sentences"]:
            print("  %.2f 相似" % p["score"])
            print("    原：%s" % p["src"])
            print("    改：%s" % p["dst"])


if __name__ == "__main__":
    main()
