#!/usr/bin/env python3
"""扫描 Vflow 工作台，生成可视化仪表盘 dashboard/index.html。

用法：
    python3 \
        ~/Vflow/scripts/build_dashboard.py

产出：
    ~/Vflow/dashboard/index.html   （单文件，数据内嵌，双击可开）

工作流有变化就重新跑一次，数据即刷新。
"""
import glob
import json
import os
import re
import subprocess
from datetime import datetime

ROOT = os.path.expanduser("~/Vflow")
PROJECTS = os.path.join(ROOT, "projects")
OUT_DIR = os.path.join(ROOT, "dashboard")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── 阶段定义 ──────────────────────────────────────────────────
STAGES = [
    {"key": "01", "name": "选题", "file": "01-topic.md",
     "skills": "vflow-topic",
     "next": "写选题卡，确认后再进结构"},
    {"key": "02", "name": "结构", "file": "02-outline.md",
     "skills": "vflow-outline",
     "next": "出页面级框架，点头后再写稿"},
    {"key": "03", "name": "剧本", "file": "03-script.md",
     "skills": "vflow-script",
     "next": "写口播逐字稿，查流失点"},
    {"key": "03b", "name": "提词稿", "file": "03b-teleprompter.md",
     "skills": "露脸口播专用",
     "next": "标换气点与分镜，准备拍摄"},
    {"key": "04", "name": "包装", "file": "04-package.md",
     "skills": "vflow-package",
     "next": "出标题 / 封面 / 开头，两端各一版"},
    {"key": "05", "name": "检查", "file": "05-check.md",
     "skills": "vflow-check",
     "next": "跑发布前风险与 AI 味检查"},
    {"key": "06", "name": "成片", "file": None,
     "skills": "bbshare-video · make_vertical.sh",
     "next": "生成 1080×1920 竖版成片"},
    {"key": "07", "name": "复盘", "file": "06-review.md",
     "skills": "发布 48 小时后回填",
     "next": "发布并回填数据，沉淀规律"},
]

# ── 空模板特征串（命中即视为未填写）────────────────────────────
EMPTY_MARKERS = {
    "01-topic.md": ["（说清楚这条讲什么", "- [ ] 做\n- [ ] 不做"],
    "02-outline.md": ["（8 页 ≈ 90–110 秒）", "| 1 | 钩子 |  |  |"],
    "03-script.md": ["（0–X 秒）", "（中文口播 200 字"],
    "03b-teleprompter.md": ["**钩子（0–3 秒）**\n> \n", "（目标 60–90 秒）"],
    "04-package.md": ["- **文字标题**（≤20 字）：\n", "1. \n2. \n3. "],
    "05-check.md": ["- **检查时间**：\n"],
    "06-review.md": ["- **发布日期**：\n"],
}


def read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def is_filled(name, path):
    if not os.path.exists(path):
        return False
    txt = read(path)
    if len(txt.strip()) < 120:
        return False
    for m in EMPTY_MARKERS.get(name, []):
        if m in txt:
            return False
    return True


def grab(pattern, txt, group=1, default=""):
    m = re.search(pattern, txt)
    return m.group(group).strip() if m else default


def probe(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=width,height", "-of", "json", path],
            capture_output=True, text=True, timeout=30).stdout
        d = json.loads(out)
        dur = float(d.get("format", {}).get("duration", 0))
        w = h = ""
        for s in d.get("streams", []):
            if s.get("width"):
                w, h = s["width"], s["height"]
                break
        return dur, w, h
    except Exception:
        return 0.0, "", ""


def meta_for(name, txt):
    out = {}
    if name == "01-topic.md":
        out["命题"] = grab(r"\*\*改后命题\*\*：(.+)", txt) or grab(r"## 一句话选题\n+(.+)", txt)
        out["类型"] = grab(r"\*\*类型\*\*：(.+)", txt)
        out["时长"] = grab(r"\*\*目标时长\*\*：(.+)", txt)
        out["平台"] = grab(r"\*\*平台\*\*：(.+)", txt)
        act = grab(r"## 看完他能拿走什么\n+(.+)", txt)
        if act:
            out["交付动作"] = re.sub(r"[*>]+", "", act)[:80]
    elif name == "02-outline.md":
        out["页数"] = grab(r"\*\*总页数\*\*：(.+)", txt)
        out["时长"] = grab(r"\*\*目标时长\*\*：(.+)", txt)
    elif name == "03-script.md":
        out["版本"] = grab(r"\*\*版本\*\*：(.+)", txt)
        out["字数"] = grab(r"\*\*字数\*\*：(.+)", txt)
        out["状态"] = grab(r"\*\*状态\*\*：(.+)", txt)
    elif name == "03b-teleprompter.md":
        out["总时长"] = grab(r"\*\*总时长\*\*：(.+)", txt)
        out["提词速度"] = grab(r"\*\*提词速度\*\*：(.+)", txt)
        rig = grab(r"\*\*机位 / 背景\*\*：(.+)", txt)
        if rig:
            out["机位背景"] = rig[:60]
    elif name == "04-package.md":
        out["抖音标题"] = grab(r"\*\*文字标题（作品文案[^）]*）\*\*：\n\s*> (.+)", txt)
        out["抖音封面"] = grab(r"\*\*封面标题（压屏大字[^）]*）\*\*：\n\s*> (.+)", txt)
        out["小红书标题"] = grab(r"\*\*笔记标题（[^）]*）\*\*：\n\s*> (.+)", txt)
        out["小红书封面"] = grab(r"\n- \*\*封面标题\*\*：\n\s*> (.+)", txt)
        tags = grab(r"\*\*话题\*\*\n+\s*> (.+)", txt)
        if tags:
            out["抖音话题"] = tags
    elif name == "05-check.md":
        out["结论"] = grab(r"\*\*结论\*\*：(.+)", txt)
        risk = grab(r"\*\*平台机器审核\*\*：(.+)", txt)
        if risk:
            out["机器审核"] = clean(risk, 34)
        n = len(re.findall(r"\*\*第 \d 处\*\*", txt))
        if n:
            out["AI 味命中"] = "%d 处" % n
    return {k: v for k, v in out.items() if v}


def stage_state(s, pdir):
    if s["key"] == "06":  # 成片看 output/
        vids = sorted(glob.glob(os.path.join(pdir, "output", "*.mp4")))
        if not vids:
            return "missing", {}, ""
        v = vids[-1]
        dur, w, h = probe(v)
        meta = {
            "文件": os.path.basename(v),
            "时长": "%.1f 秒" % dur,
            "分辨率": ("%s×%s" % (w, h)) if w else "",
            "大小": "%.1f MB" % (os.path.getsize(v) / 1024 / 1024),
        }
        return "done", meta, v
    name = s["file"]
    path = os.path.join(pdir, name)
    if not os.path.exists(path):
        return "missing", {}, ""
    if not is_filled(name, path):
        return "template", {}, path
    return "done", meta_for(name, read(path)), path


def next_action(states):
    for s in STAGES:
        if states.get(s["key"], {}).get("state") != "done":
            return s["next"]
    return "全链路已完成"


def scan_project(pdir):
    slug = os.path.basename(pdir)
    m = re.match(r"(\d{8})-(.+)", slug)
    date, title = (m.group(1), m.group(2)) if m else ("", slug)
    states = {}
    for s in STAGES:
        st, meta, path = stage_state(s, pdir)
        states[s["key"]] = {"state": st, "meta": meta, "path": path}
    done_n = sum(1 for k in states if states[k]["state"] == "done")
    topic = read(os.path.join(pdir, "01-topic.md"))
    # 01 没填但有成片 = 链路验证用的测试项目，不算真选题
    kind = "real" if states["01"]["state"] == "done" else (
        "test" if states["06"]["state"] == "done" else "blank")
    return {
        "slug": slug,
        "date": date,
        "title": title,
        "kind": kind,
        "one_liner": (grab(r"\*\*改后命题\*\*：(.+)", topic)
                      or grab(r"## 一句话选题\n+(.+)", topic)),
        "states": states,
        "done_n": done_n,
        "total_n": len(STAGES),
        "progress": round(done_n / len(STAGES) * 100),
        "next": next_action(states),
        "mtime": os.path.getmtime(pdir),
    }


def clean(s, limit=48):
    """去掉 markdown 强调符号，超长时在标点处收尾"""
    s = re.sub(r"\*+", "", s).strip()
    if len(s) <= limit:
        return s
    cut = s[:limit]
    for sep in ("。", "；", "，"):
        i = cut.rfind(sep)
        if i > limit * 0.5:
            return cut[:i + 1]
    return cut + "…"


def pace(line):
    """从「**发布节奏**：（待定。建议起步每周 2 条，…）」里取出可读结论"""
    if not line:
        return "待定"
    m = re.search(r"(每周\s*\d+\s*条)", line)
    if m:
        return ("待定 · " if "待定" in line else "") + m.group(1)
    return clean(re.sub(r"[（）]", "", line), 26) or "待定"


def studio_summary():
    txt = read(os.path.join(ROOT, "STUDIO.md"))
    return {
        "账号名": clean(grab(r"\*\*账号名\*\*：(.+)", txt), 20) or "（未填）",
        "当前阶段": clean(grab(r"\*\*阶段\*\*：(.+)", txt), 30) or "（未填）",
        "内容主线": clean(grab(r"围绕一句话：\*\*(.+)", txt), 30) or "（未填）",
        "出镜方式": clean(grab(r"\*\*出镜方式：(.+)", txt), 30) or "（未填）",
        "发布节奏": pace(grab(r"\*\*发布节奏\*\*：([^\n]+)", txt)),
        "主受众": clean(grab(r"\*\*主受众\*\*：(.+)", txt), 56) or "（未填）",
    }


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    projs = [scan_project(p) for p in sorted(glob.glob(os.path.join(PROJECTS, "*")))
             if os.path.isdir(p)]
    projs.sort(key=lambda x: x["mtime"], reverse=True)
    real = [p for p in projs if p["kind"] == "real"]
    active = real[0] if real else (projs[0] if projs else None)

    data = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "root": ROOT,
        "stages": STAGES,
        "projects": projs,
        "active": active["slug"] if active else "",
        "studio": studio_summary(),
        "stats": {
            "total": len(real),
            "shipped": sum(1 for p in real if p["states"]["06"]["state"] == "done"),
            "in_progress": sum(1 for p in real if 0 < p["done_n"] < p["total_n"]),
            "reviewed": sum(1 for p in real if p["states"]["07"]["state"] == "done"),
            "test": sum(1 for p in projs if p["kind"] != "real"),
        },
    }

    tpl = read(os.path.join(SCRIPT_DIR, "dashboard_template.html"))
    html = tpl.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    out = os.path.join(OUT_DIR, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    print("dashboard ->", out)
    print("projects: %d | shipped: %d | in_progress: %d"
          % (data["stats"]["total"], data["stats"]["shipped"], data["stats"]["in_progress"]))
    for p in projs:
        print("  - %-28s %2d/%d  %s"
              % (p["slug"], p["done_n"], p["total_n"], p["next"]))


if __name__ == "__main__":
    main()
