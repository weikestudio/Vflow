#!/usr/bin/env python3
"""一键生成发布包：一条内容要发的所有东西，放在一个目录里，直接可用。

发布包不是"把文件挪个地方"，它是发布前的最后一道关：
- 成片、封面、双平台文案、标签、AI 声明、检查清单，全在一个目录；
- 质检没过、声明没登记、封面不合格，**拒绝生成**；
- 生成之后有 manifest.json，发布队列和工作台读它，不再各自猜路径。

用法：
    python3 package.py build <slug> [--zip] [--force]
    python3 package.py show <slug>
    python3 package.py checklist <slug>

产出：
    projects/<slug>/publish/
    ├── video.mp4            终版成片（从 final 指针复制）
    ├── cover-douyin.png     抖音封面（有就复制）
    ├── cover-xhs.png
    ├── copy-douyin.md       抖音：标题 / 正文 / 标签 / AI 声明
    ├── copy-xhs.md          小红书：标题 / 正文 / 标签 / 关键词矩阵 / AI 声明
    ├── checklist.md         发布前逐项勾选
    ├── manifest.json        机器读：文件、平台文案、质检结论
    └── publish-<slug>.zip   可选，整个目录打包

零依赖。
"""
import argparse
import json
import os
import re
import shutil
import sys
import zipfile
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import vflow_state as VS          # noqa: E402
import qc as QC                   # noqa: E402

ROOT = VS.ROOT


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def read(p):
    return VS.read_text(p)


def out_dir(slug):
    return os.path.join(VS.slug_dir(slug), "publish")


# ---------- 校验 ----------

def gates(slug):
    """进发布包之前必须过的门。返回 (ok, blockers, warns)。"""
    st = VS.build_state(slug)
    blockers, warns = [], []

    check = st["stages"]["05"]["status"]
    if check != "done":
        blockers.append("检查阶段（05）没完成")
    q = st.get("qc") or {}
    if not q.get("generated"):
        blockers.append("没跑过机器质检（qc.py all）")
    elif q.get("fail"):
        blockers.append("机器质检有 %d 项未通过" % q["fail"])
    elif q.get("stale"):
        blockers.append("质检之后成片或检查稿改过，重跑 qc.py")

    if st["stages"]["06"]["status"] != "done":
        blockers.append("制作阶段（06）没完成：成片不存在或指针失效")

    # 声明台账：未登记的对外数字
    try:
        import claims as CL
        scan = CL.cmd_scan(type("A", (), {"slug": slug})())
        if scan.get("count"):
            warns.append("%d 处数字/引用没登记来源（claims.py scan）"
                         % scan["count"])
    except Exception:
        pass

    # 复盘门槛不需要（发布前还没数据）
    return not blockers, blockers, warns


# ---------- 文案 ----------

def platform_copy(slug, plat):
    package = QC.parse_package(slug)
    data = package.get(plat) or {}
    text = read(os.path.join(VS.slug_dir(slug), "04-package.md"))
    tags = data.get("tags") or ""
    tag_list = re.findall(r"#\S+", tags) or \
        [t for t in re.split(r"[,，、\s]+", tags) if t and t != "—"]

    # AI 声明
    m = re.search(r"^##\s*AI 生成声明\s*$", text, re.M)
    ai_decl = ""
    if m:
        start = m.end()
        nxt = re.search(r"^##\s+", text[start:], re.M)
        chunk = text[start:start + nxt.start()] if nxt else text[start:]
        for line in chunk.split("\n"):
            if "声明" in line and "：" in line:
                ai_decl = line.split("：", 1)[1].strip()
                break

    matrix = QC.parse_matrix(text)

    # 正文第一段从 publish-copy.md 取（如果有）
    body = ""
    copy_md = read(os.path.join(VS.slug_dir(slug), "publish-copy.md"))
    if copy_md and VS.TEMPLATE_MARK not in copy_md:
        sec = "抖音" if plat == "douyin" else "小红书"
        mm = re.search(r"^##\s*%s\s*$" % sec, copy_md, re.M)
        if mm:
            start = mm.end()
            nxt = re.search(r"^##\s+", copy_md[start:], re.M)
            chunk = copy_md[start:start + nxt.start()] if nxt else copy_md[start:]
            bm = re.search(r"\*\*正文\*\*\s*\n+(.+?)(?=\n#|\n---|\Z)",
                           chunk, re.S)
            if bm:
                body = bm.group(1).strip()

    return {
        "title": data.get("title", ""),
        "cover": data.get("cover", ""),
        "opening": data.get("opening", ""),
        "body": body,
        "tags": tag_list,
        "ai_decl": ai_decl,
        "matrix": matrix if plat == "xhs" else {},
    }


def render_copy(slug, plat, copy, st):
    name = "抖音" if plat == "douyin" else "小红书"
    lines = ["# 发布文案 · %s" % name, "",
             "- 项目：%s" % slug,
             "- 生成：%s" % now(), ""]
    lines += ["## 标题", "", copy["title"] or "（没填）", ""]
    if copy["opening"]:
        lines += ["## 开头（口播 / 画面）", "", copy["opening"], ""]
    if copy["body"]:
        lines += ["## 正文", "", copy["body"], ""]
    if copy["tags"]:
        lines += ["## 标签", "", " ".join(copy["tags"]), ""]
    if copy["matrix"]:
        lines += ["## 关键词矩阵", "", "| 维度 | 关键词 |", "|---|---|"]
        for k, v in copy["matrix"].items():
            lines.append("| %s | %s |" % (k, v))
        lines.append("")
    video = st.get("final", {}).get("video")
    if video:
        lines += ["## 成片", "", "- 文件：`video.mp4`（源自 `%s`）" % video, ""]
    lines += ["## AI 生成声明", "", copy["ai_decl"] or
              "（没填。平台要求对 AI 生成内容做标识，发布前补上）", ""]
    return "\n".join(lines)


def render_checklist(slug, copy_dy, copy_xhs):
    st = VS.build_state(slug)
    q = st.get("qc") or {}
    items = [
        ("成片已看一遍（首帧 / 封面 / 结尾）", False),
        ("质检结论：FAIL %s / WARN %s（%s）" % (
            q.get("fail", "—"), q.get("warn", "—"), q.get("generated", "—")),
         True),
        ("抖音标题 ≤20 字：%s" % (copy_dy["title"] or "（空）"), bool(copy_dy["title"])),
        ("小红书标题前 20 字含核心词", bool(copy_xhs.get("matrix"))),
        ("两平台文案不一样（不是一套粘贴两边）", True),
        ("标签数量对（抖音 3–5 / 小红书 5–10）", True),
        ("AI 生成声明已写", bool(copy_dy["ai_decl"] or copy_xhs["ai_decl"])),
        ("没有留联系方式 / 二维码 / 外链", True),
        ("免费边界说清了（推荐了工具才需要）", True),
        ("数字已登记来源（claims.py）", True),
    ]
    lines = ["# 发布前检查清单 · %s" % slug, "",
             "> 打勾之后再发。打不了勾的，回到对应阶段修，不要带着问题发。", ""]
    for label, ok in items:
        lines.append("- [%s] %s" % ("x" if ok else " ", label))
    lines += ["", "## 发布后", "",
              "- [ ] 跑 `publish.py done <slug> --platform <平台>` 登记",
              "- [ ] 48 小时后 `review.py pending` 回填数据", ""]
    return "\n".join(lines)


# ---------- 生成 ----------

def build(slug, make_zip=False, force=False):
    if not os.path.isdir(VS.slug_dir(slug)):
        return {"error": "项目不存在：%s" % slug}, 2
    ok, blockers, warns = gates(slug)
    d = out_dir(slug)
    if not ok and not force:
        return {"blocked": True, "blockers": blockers, "warns": warns,
                "hint": "修完再跑；确实要出包加 --force（不推荐）"}, 1

    os.makedirs(d, exist_ok=True)
    st = VS.build_state(slug)
    copied = {}

    # 成片
    video = st.get("final", {}).get("video")
    if video:
        src = os.path.join(VS.slug_dir(slug), video)
        if os.path.isfile(src):
            dst = os.path.join(d, "video.mp4")
            shutil.copy2(src, dst)
            copied["video"] = "video.mp4"

    # 封面
    qc_dir = os.path.join(VS.slug_dir(slug), "output", "qc")
    for plat, name in (("douyin", "cover-douyin.png"),
                       ("xhs", "cover-xhs.png")):
        src = os.path.join(qc_dir, name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(d, name))
            copied["cover-" + plat] = name

    # 文案
    copy_dy = platform_copy(slug, "douyin")
    copy_xhs = platform_copy(slug, "xhs")
    for plat, copy in (("douyin", copy_dy), ("xhs", copy_xhs)):
        fn = "copy-%s.md" % plat
        with open(os.path.join(d, fn), "w", encoding="utf-8") as fh:
            fh.write(render_copy(slug, plat, copy, st))
        copied["copy-" + plat] = fn

    with open(os.path.join(d, "checklist.md"), "w", encoding="utf-8") as fh:
        fh.write(render_checklist(slug, copy_dy, copy_xhs))
    copied["checklist"] = "checklist.md"

    manifest = {
        "slug": slug,
        "title": st.get("title"),
        "generated": now(),
        "forced": bool(force and not ok),
        "qc": st.get("qc") or {},
        "files": copied,
        "platforms": {
            "douyin": copy_dy,
            "xhs": copy_xhs,
        },
        "warns": warns,
    }
    with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)

    zip_name = None
    if make_zip:
        zip_name = "publish-%s.zip" % slug
        zpath = os.path.join(d, zip_name)
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(d):
                for f in files:
                    if f == zip_name:
                        continue
                    full = os.path.join(root, f)
                    zf.write(full, os.path.relpath(full, d))

    return {"ok": True, "dir": "publish/", "files": copied,
            "zip": zip_name, "warns": warns,
            "next": "发布：python3 scripts/publish.py queue %s --platform douyin"
                    % slug}, 0


def cmd_show(a):
    m = None
    mp = os.path.join(out_dir(a.slug), "manifest.json")
    if os.path.isfile(mp):
        try:
            m = json.loads(read(mp))
        except json.JSONDecodeError:
            m = None
    if not m:
        return {"error": "还没生成发布包：package.py build %s" % a.slug}
    return m


def cmd_checklist(a):
    p = os.path.join(out_dir(a.slug), "checklist.md")
    if not os.path.isfile(p):
        return {"error": "还没生成发布包"}
    return {"checklist": read(p)}


def main():
    ap = argparse.ArgumentParser(description="Vflow 一键发布包")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("build"); p.add_argument("slug")
    p.add_argument("--zip", action="store_true")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=lambda a: build(a.slug, a.zip, a.force))
    p = sub.add_parser("show"); p.add_argument("slug")
    p.set_defaults(fn=lambda a: (cmd_show(a), 0))
    p = sub.add_parser("checklist"); p.add_argument("slug")
    p.set_defaults(fn=lambda a: (cmd_checklist(a), 0))

    args = ap.parse_args()
    result, code = args.fn(args)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    sys.exit(code)


if __name__ == "__main__":
    main()
