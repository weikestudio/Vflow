#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 prompts/ 目录里的 Markdown 提示词打包成 prompts.json，供提示词软件导入。
用法：
  /Users/v1/.workbuddy/binaries/python/envs/default/bin/python \
      ~/shortvideo-studio/scripts/build_prompts_json.py
产出：~/shortvideo-studio/prompts/prompts.json
"""
import json
import os
import re
import sys

ROOT = os.path.expanduser("~/shortvideo-studio")
PROMPTS = os.path.join(ROOT, "prompts")
OUT = os.path.join(PROMPTS, "prompts.json")

# 每个文件的元信息：标题 / 分类 / 变量列表
META = {
    "01-全链路主控.md": {
        "title": "短视频全链路主控（小V智谈）",
        "category": "主控",
        "desc": "选题→结构→剧本→包装→检查→制作 六阶段。自包含，每阶段停一次等人确认。适合完整做一条内容。",
        "tags": ["短视频", "全链路", "主控", "抖音", "小红书"],
    },
    "02-单条快出.md": {
        "title": "单条快出（一次对话出到发布前）",
        "category": "快出",
        "desc": "一条消息拿完整结果：命题判断+框架+逐字稿+双端包装+发布前检查+拍摄清单。追求快。",
        "tags": ["短视频", "快出", "一条到底"],
    },
    "03-口播稿深加工.md": {
        "title": "口播稿深加工（解决太浅 / 解法不明）",
        "category": "改稿",
        "desc": "给已有稿子用。先量化诊断密度与结构，再补机制层、升级判据、补方法页。",
        "tags": ["改稿", "深化", "方法论"],
    },
    "04-发布前体检.md": {
        "title": "发布前体检（风险 + AI 味双层）",
        "category": "检查",
        "desc": "发布前最后一道关。扫广告结构、导流、点名、承诺、画面隐私，以及 AI 味特征。输出可发/不可发。",
        "tags": ["检查", "风险", "AI味"],
    },
    "05-选题筛选与命题改造.md": {
        "title": "选题筛选与命题改造",
        "category": "选题",
        "desc": "有模糊想法但还没写稿时用。主要任务是拦住不该做的选题，而不是把所有选题包装成能做的。",
        "tags": ["选题", "命题", "把关"],
    },
}

VAR_RE = re.compile(r"\{\{([^}]*)\}\}")


def extract_block(md: str) -> str:
    """取出 Markdown 里被 ``` 包起来的提示词正文（第一个代码块）。"""
    lines = md.split("\n")
    start = None
    for i, ln in enumerate(lines):
        if ln.strip() == "```":
            start = i + 1
            break
    if start is None:
        return ""
    for j in range(len(lines) - 1, start - 1, -1):
        if lines[j].strip() == "```":
            return "\n".join(lines[start:j]).rstrip() + "\n"
    return "\n".join(lines[start:]).rstrip() + "\n"


def main():
    items = []
    for name, meta in META.items():
        path = os.path.join(PROMPTS, name)
        if not os.path.exists(path):
            print("缺少文件，跳过：%s" % name, file=sys.stderr)
            continue
        md = open(path, encoding="utf-8").read()
        body = extract_block(md)
        if not body:
            print("未提取到代码块：%s" % name, file=sys.stderr)
            continue
        variables = []
        for m in VAR_RE.finditer(body):
            v = m.group(1).strip()
            if v and v not in variables:
                variables.append(v)
        items.append({
            "title": meta["title"],
            "category": meta["category"],
            "description": meta["desc"],
            "tags": meta["tags"],
            "variables": variables,
            "content": body,
            "source": "prompts/" + name,
        })

    data = {
        "name": "小V智谈 · 短视频提示词集",
        "version": "1.0",
        "generated": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M"),
        "note": "共 %d 条。content 即完整提示词，{{}} 是使用前要替换的变量。" % len(items),
        "prompts": items,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("已生成 %s" % OUT)
    for it in items:
        print("  [%s] %-28s 变量 %d 个，%d 字" % (
            it["category"], it["title"], len(it["variables"]), len(it["content"])))


if __name__ == "__main__":
    main()
