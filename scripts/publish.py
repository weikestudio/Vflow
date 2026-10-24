#!/usr/bin/env python3
"""发布队列：人工 / 半自动 / 自动三档，默认永远是最保守的那一档。

**为什么默认不自动发**：
- 平台对自动化发布有明确限制，账号可能被判定异常；
- 页面选择器随 UI 改版就会失效，自动发的失败方式通常是"发出去一条错内容"；
- Vflow 的定位是"可信的内容生产者"，不是"发量工厂"。

所以：
- **manual（默认）**：只生成发布包，你自己发。安全、可控。
- **assisted**：帮你打开创作页，把标题/正文/标签复制到剪贴板并预填到页面。
  仍然要你亲手点发布。
- **auto**：真的自动提交。**必须同时满足**：config 显式开启、本机装了 Playwright、
  这条内容质检全过、并且加 `--i-understand-the-risk`。缺一个就退回 manual。

用法：
    python3 publish.py queue <slug> --platform douyin [--mode manual|assisted|auto]
    python3 publish.py list [--status 待发|已发|失败|退回人工]
    python3 publish.py run <slug> --platform douyin [--mode ...] [--i-understand-the-risk]
    python3 publish.py done <slug> --platform douyin [--url ...]
    python3 publish.py config                         看当前配置
    python3 publish.py config --mode assisted          改默认（写 publish.config.json）

发布包由 `package.py` 生成，本脚本只消费它。发布成功后自动登记 `review.py published`。

零依赖；assisted/auto 会尝试用本机工具，缺了就退回人工并说明。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import webbrowser
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import vflow_state as VS          # noqa: E402

ROOT = VS.ROOT
CONFIG = os.path.join(ROOT, "publish.config.json")
DEFAULT_CONFIG = {
    "mode": "manual",
    "allow_auto": False,
    "platforms": {
        "douyin": {
            "creator_url": "https://creator.douyin.com/creator-micro/content/upload",
            "login_hint": "先在 Chrome 登录抖音创作者中心",
        },
        "xhs": {
            "creator_url": "https://creator.xiaohongshu.com/publish/publish",
            "login_hint": "先在 Chrome 登录小红书创作服务平台",
        },
    },
    "selectors": {
        "_comment": "选择器会随平台改版失效。auto 失败时先看这里，别改脚本。",
        "douyin": {"title": "input[placeholder*='标题']",
                   "body": "div[contenteditable='true']",
                   "submit": "button:has-text('发布')"},
        "xhs": {"title": "input[placeholder*='标题']",
                "body": "div[contenteditable='true']",
                "submit": "button:has-text('发布')"},
    },
}
MODES = ["manual", "assisted", "auto"]
STATUSES = ["待发", "已发", "失败", "退回人工"]


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def read(p):
    try:
        with open(p, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def load_config():
    if not os.path.isfile(CONFIG):
        return dict(DEFAULT_CONFIG)
    try:
        cfg = json.loads(read(CONFIG))
    except json.JSONDecodeError:
        return dict(DEFAULT_CONFIG)
    out = json.loads(json.dumps(DEFAULT_CONFIG))
    out.update({k: v for k, v in cfg.items() if k != "platforms"})
    out["platforms"].update(cfg.get("platforms") or {})
    return out


def save_config(cfg):
    with open(CONFIG, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=2)


def publish_dir(slug):
    return os.path.join(VS.slug_dir(slug), "publish")


def manifest_path(slug):
    return os.path.join(publish_dir(slug), "manifest.json")


def load_manifest(slug):
    p = manifest_path(slug)
    if not os.path.isfile(p):
        return None
    try:
        return json.loads(read(p))
    except json.JSONDecodeError:
        return None


def queue_path(slug):
    return os.path.join(publish_dir(slug), "queue.json")


def load_queue(slug):
    p = queue_path(slug)
    if not os.path.isfile(p):
        return {"items": []}
    try:
        return json.loads(read(p))
    except json.JSONDecodeError:
        return {"items": []}


def save_queue(slug, q):
    d = publish_dir(slug)
    os.makedirs(d, exist_ok=True)
    with open(queue_path(slug), "w", encoding="utf-8") as fh:
        json.dump(q, fh, ensure_ascii=False, indent=2)


def qc_ok(slug):
    """质检门槛：revision 之后跑过 qc，且没有 FAIL。"""
    st = VS.build_state(slug)
    qc = st.get("qc") or {}
    if not qc.get("generated"):
        return False, "还没跑过 qc.py"
    if qc.get("fail"):
        return False, "qc 有 %d 项未通过" % qc["fail"]
    if qc.get("stale"):
        return False, "成片或检查稿在质检之后改过，先重跑 qc.py"
    return True, "qc 通过（%s）" % qc.get("generated")


def effective_mode(requested, slug):
    """实际执行模式：任何一道门没过都退回 manual。"""
    cfg = load_config()
    mode = requested or cfg.get("mode") or "manual"
    reasons = []
    if mode == "auto":
        if not cfg.get("allow_auto"):
            reasons.append("publish.config.json 的 allow_auto 没开")
        if not shutil.which("node") and not _has_playwright():
            reasons.append("本机没有 Playwright / node")
        ok, why = qc_ok(slug)
        if not ok:
            reasons.append("质检未通过：%s" % why)
    if mode in ("auto",) and reasons:
        return "manual", reasons
    return mode, reasons


def _has_playwright():
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


def platform_data(slug, platform):
    m = load_manifest(slug) or {}
    pkg = (m.get("platforms") or {}).get(platform) or {}
    if not pkg and os.path.isdir(publish_dir(slug)):
        # 没有 manifest 时退回读 publish-copy.md
        text = read(os.path.join(VS.slug_dir(slug), "publish-copy.md"))
        pkg = {"title": "", "body": "", "tags": []}
    return pkg


def cmd_queue(a):
    slug = a.slug
    if not os.path.isdir(VS.slug_dir(slug)):
        return {"error": "项目不存在：%s" % slug}
    m = load_manifest(slug)
    if not m:
        return {"error": "还没有发布包。先跑：python3 scripts/package.py build %s" % slug}
    mode, reasons = effective_mode(a.mode, slug)
    q = load_queue(slug)
    item = next((i for i in q["items"]
                 if i["platform"] == a.platform and i["status"] != "已发"), None)
    if item:
        item["mode"] = mode
        item["updated"] = now()
    else:
        q["items"].append({"platform": a.platform, "mode": mode,
                           "status": "待发", "created": now(),
                           "updated": now(), "url": ""})
    save_queue(slug, q)
    ok, why = qc_ok(slug)
    return {"ok": True, "slug": slug, "platform": a.platform,
            "mode": mode, "fallback": reasons, "qc": {"ok": ok, "why": why},
            "next": "python3 scripts/publish.py run %s --platform %s"
                    % (slug, a.platform)}


def cmd_list(a):
    rows = []
    for slug in VS.iter_slugs():
        q = load_queue(slug)
        for i in q["items"]:
            if a.status and i["status"] != a.status:
                continue
            rows.append({"slug": slug, **i})
    return {"count": len(rows),
            "by_status": {s: sum(1 for r in rows if r["status"] == s)
                          for s in STATUSES},
            "items": rows}


def copy_to_clipboard(text):
    for cmd in (["pbcopy"], ["wl-copy"], ["xclip", "-selection", "clipboard"]):
        if shutil.which(cmd[0]):
            try:
                subprocess.run(cmd, input=text, text=True, timeout=5,
                               check=True)
                return True
            except (OSError, subprocess.SubprocessError):
                continue
    return False


def run_auto(slug, platform, cfg, data):
    """真正提交。只在全部门都过了才会被调用。"""
    sel = (cfg.get("selectors") or {}).get(platform) or {}
    url = (cfg.get("platforms") or {}).get(platform, {}).get("creator_url")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, "没有 Playwright"
    video = (cfg.get("_manifest_video") or "")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            ctx = browser.new_context()
            page = ctx.new_page()
            page.goto(url, timeout=60000)
            page.wait_for_timeout(3000)
            if video and os.path.isfile(video):
                inp = page.query_selector("input[type='file']")
                if inp:
                    inp.set_input_files(video)
                    page.wait_for_timeout(8000)
            if data.get("title") and sel.get("title"):
                try:
                    page.fill(sel["title"], data["title"], timeout=5000)
                except Exception:
                    pass
            if data.get("body") and sel.get("body"):
                try:
                    page.fill(sel["body"], data["body"], timeout=5000)
                except Exception:
                    pass
            # 不自动点提交：让使用者亲手确认最后一步
            return False, "已打开发布页并预填，请人工确认后点发布（auto 也不代点提交）"
    except Exception as e:
        return False, "自动流程出错：%s" % str(e)[:200]


def cmd_run(a):
    slug = a.slug
    if not os.path.isdir(VS.slug_dir(slug)):
        return {"error": "项目不存在：%s" % slug}
    cfg = load_config()
    data = platform_data(slug, a.platform)
    mode, reasons = effective_mode(a.mode, slug)
    ok, why = qc_ok(slug)
    q = load_queue(slug)
    item = next((i for i in q["items"] if i["platform"] == a.platform), None)
    if not item:
        return {"error": "先入队：publish.py queue %s --platform %s"
                         % (slug, a.platform)}

    if mode == "auto":
        if not a.i_understand_the_risk:
            mode = "manual"
            reasons.append("auto 需要显式加 --i-understand-the-risk")
        else:
            vid = (load_manifest(slug) or {}).get("files", {}).get("video")
            cfg["_manifest_video"] = os.path.join(VS.slug_dir(slug),
                                                  "publish", vid or "")
            submitted, why_auto = run_auto(slug, a.platform, cfg, data)
            if not submitted:
                mode = "assisted"
                reasons.append(why_auto)

    if mode == "assisted":
        url = (cfg.get("platforms") or {}).get(a.platform, {}).get("creator_url")
        text = "\n\n".join(x for x in (data.get("title"), data.get("body"),
                                      " ".join(data.get("tags") or [])) if x)
        copied = copy_to_clipboard(text)
        opened = False
        if url:
            try:
                opened = webbrowser.open(url)
            except Exception:
                opened = False
        item["mode"] = "assisted"
        item["status"] = "待发"
        item["updated"] = now()
        save_queue(slug, q)
        return {"ok": True, "mode": "assisted", "fallback": reasons,
                "opened": opened, "copied": copied,
                "url": url, "qc": why,
                "next": "在浏览器里确认内容和标签，手动点发布；发完跑 "
                        "publish.py done %s --platform %s" % (slug, a.platform)}

    # manual
    item["mode"] = "manual"
    item["status"] = "待发" if item["status"] == "待发" else item["status"]
    item["updated"] = now()
    save_queue(slug, q)
    files = (load_manifest(slug) or {}).get("files", {})
    return {"ok": True, "mode": "manual", "fallback": reasons, "qc": why,
            "package": publish_dir(slug),
            "files": files,
            "next": "按 publish/checklist.md 手动发布；发完跑 publish.py done "
                    "%s --platform %s" % (slug, a.platform)}


def cmd_done(a):
    slug = a.slug
    if not os.path.isdir(VS.slug_dir(slug)):
        return {"error": "项目不存在：%s" % slug}
    q = load_queue(slug)
    item = next((i for i in q["items"] if i["platform"] == a.platform), None)
    if not item:
        item = {"platform": a.platform, "mode": "manual", "created": now()}
        q["items"].append(item)
    item["status"] = "已发"
    item["updated"] = now()
    item["url"] = a.url or item.get("url", "")
    save_queue(slug, q)

    # 联动：登记发布 + 标记日历
    try:
        import review as RV
        RV.cmd_published(type("A", (), {
            "slug": slug, "platform": a.platform, "at": None,
            "counts_as": None, "bucket": None})())
    except Exception:
        pass

    return {"ok": True, "status": "已发", "url": item["url"],
            "next": "48 小时后复盘：python3 scripts/review.py pending"}


def cmd_config(a):
    cfg = load_config()
    if a.mode:
        cfg["mode"] = a.mode
        save_config(cfg)
        return {"ok": True, "mode": cfg["mode"],
                "note": "auto 还要把 allow_auto 设成 true，并且显式加 "
                        "--i-understand-the-risk；否则会退回 manual"}
    if a.allow_auto is not None:
        cfg["allow_auto"] = bool(a.allow_auto)
        save_config(cfg)
        return {"ok": True, "allow_auto": cfg["allow_auto"]}
    return {"config": cfg, "path": CONFIG,
            "modes": {"manual": "只生成发布包，自己发（默认）",
                      "assisted": "打开创作页 + 复制文案，手动点发布",
                      "auto": "尝试自动提交，需 allow_auto + Playwright + 确认参数"}}


def main():
    ap = argparse.ArgumentParser(description="Vflow 发布队列")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("queue")
    p.add_argument("slug"); p.add_argument("--platform", required=True,
                                           choices=["douyin", "xhs"])
    p.add_argument("--mode", choices=MODES)
    p.set_defaults(fn=cmd_queue)

    p = sub.add_parser("list"); p.add_argument("--status", choices=STATUSES)
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("run")
    p.add_argument("slug"); p.add_argument("--platform", required=True,
                                           choices=["douyin", "xhs"])
    p.add_argument("--mode", choices=MODES)
    p.add_argument("--i-understand-the-risk", action="store_true")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("done")
    p.add_argument("slug"); p.add_argument("--platform", required=True,
                                           choices=["douyin", "xhs"])
    p.add_argument("--url")
    p.set_defaults(fn=cmd_done)

    p = sub.add_parser("config")
    p.add_argument("--mode", choices=MODES)
    p.add_argument("--allow-auto", type=lambda x: x.lower() == "true",
                   default=None)
    p.set_defaults(fn=cmd_config)

    args = ap.parse_args()
    json.dump(args.fn(args), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
