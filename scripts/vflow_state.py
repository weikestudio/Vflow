#!/usr/bin/env python3
"""Vflow 项目状态机。

项目状态的唯一真源是 `projects/<slug>/.vflow.json`。
工作台、脚本、Skill 都读它，不再靠猜文件是否存在、模板有没有被填。

用法：
    python3 vflow_state.py show <slug>            看一个项目
    python3 vflow_state.py list                   列全部项目（JSON）
    python3 vflow_state.py init <slug>            建/刷新状态文件
    python3 vflow_state.py migrate                给所有已有项目补状态文件
    python3 vflow_state.py set <slug> <阶段> <状态>   状态: empty|wip|done|skip
    python3 vflow_state.py archive <slug> <文件>     归档当前内容为草稿版本
    python3 vflow_state.py sync <slug> [--from 03-script.md]   列出待同步的下游
    python3 vflow_state.py final <slug> --video <路径> [--cover <路径>]

设计原则：
1. 状态只有一份，写在 .vflow.json，别处都是派生。
2. 版本：主干文件永远是最新版；归档进 drafts/ 带版本号，永不覆盖。
3. 改上游要告诉使用者下游哪些文件可能失效，但不自动改——判断权在人。
"""
import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime

ROOT = os.path.abspath(
    os.environ.get("VFLOW_HOME") or os.path.expanduser("~/Vflow")
)
TEMPLATE_MARK = "<!-- vflow-template"

# 阶段：编号 / 名字 / 产出文件 / 负责 skill
STAGES = [
    ("01", "选题", "01-topic.md", "vflow-topic"),
    ("02", "结构", "02-outline.md", "vflow-outline"),
    ("03", "剧本", "03-script.md", "vflow-script"),
    ("04", "包装", "04-package.md", "vflow-package"),
    ("05", "检查", "05-check.md", "vflow-check"),
    ("06", "制作", "publish-copy.md", "vflow-produce"),
    ("07", "复盘", "06-review.md", "vflow-review"),
]

# 改了上游，下游哪些文件可能失效（只提示，不自动改）
DOWNSTREAM = {
    "01-topic.md": ["02-outline.md", "03-script.md", "04-package.md"],
    "02-outline.md": ["03-script.md", "04-package.md"],
    "03-script.md": ["04-package.md", "05-check.md", "publish-copy.md"],
    "04-package.md": ["05-check.md", "publish-copy.md"],
    "05-check.md": ["publish-copy.md"],
    "publish-copy.md": [],
    "06-review.md": [],
}

STATE_VERSION = 1


def projects_dir():
    return os.path.join(ROOT, "projects")


def slug_dir(slug):
    return os.path.join(projects_dir(), slug)


def state_path(slug):
    return os.path.join(slug_dir(slug), ".vflow.json")


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return ""


def file_status(slug, fname):
    """判断一个阶段产出文件是真写了，还是空模板。"""
    path = os.path.join(slug_dir(slug), fname)
    if not os.path.isfile(path):
        return "empty", None
    content = read_text(path)
    if not content.strip() or TEMPLATE_MARK in content:
        return "empty", None
    return "done", datetime.fromtimestamp(
        os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M")


def build_state(slug):
    """从磁盘现状推导状态（不依赖旧状态文件，可重复执行）。"""
    d = slug_dir(slug)
    readme = read_text(os.path.join(d, "README.md"))
    title = slug
    m = re.search(r"^# (.+)$", readme, re.M)
    if m:
        title = m.group(1).strip()
    created = ""
    m = re.search(r"创建:\s*([\d\-]+)", readme)
    if m:
        created = m.group(1)

    # README 的勾选框优先（人是权威），没有勾选就用文件填充状态
    checked = {}
    for mm in re.finditer(r"^- \[( |x)\] (\d{2}) ", readme, re.M):
        checked[mm.group(2)] = mm.group(1) == "x"

    stages = {}
    for key, name, fname, skill in STAGES:
        st, updated = file_status(slug, fname)
        if key in checked:
            st = "done" if checked[key] else st
        if st == "done" and not updated:
            updated = datetime.now().strftime("%Y-%m-%d %H:%M")
        stages[key] = {
            "name": name, "file": fname, "skill": skill,
            "status": st, "updated": updated,
        }

    # 当前阶段 = 第一个没完成的
    current = "07"
    for key, _, _, _ in STAGES:
        if stages[key]["status"] != "done":
            current = key
            break

    # 兼容老状态文件里的 final / drafts / hooks / metrics
    old = {}
    sp = state_path(slug)
    if os.path.isfile(sp):
        try:
            old = json.loads(read_text(sp))
        except json.JSONDecodeError:
            old = {}

    # 版本：drafts/ 里已归档的
    drafts = old.get("drafts", {})
    dd = os.path.join(d, "drafts")
    if os.path.isdir(dd):
        for f in sorted(os.listdir(dd)):
            m = re.match(r"(.+?)-v(\d+)\.md$", f)
            if not m:
                continue
            base, num = m.group(1) + ".md", int(m.group(2))
            entry = drafts.setdefault(base, {"latest": 0, "files": []})
            rel = "drafts/" + f
            if rel not in entry["files"]:
                entry["files"].append(rel)
            entry["latest"] = max(entry["latest"], num)

    final = old.get("final", {})
    if not final.get("video"):
        out = os.path.join(d, "output")
        if os.path.isdir(out):
            vids = [f for f in os.listdir(out)
                    if f.lower().endswith((".mp4", ".mov"))]
            finals = [f for f in vids if f.startswith("final")]
            pick = finals[0] if finals else (vids[0] if vids else None)
            if pick:
                final["video"] = "output/" + pick

    return {
        "version": STATE_VERSION,
        "slug": slug,
        "title": title,
        "created": created or datetime.now().strftime("%Y-%m-%d"),
        "platforms": old.get("platforms", ["douyin", "xhs"]),
        "stages": stages,
        "current": current,
        "progress": sum(1 for s in stages.values() if s["status"] == "done"),
        "final": final,
        "drafts": drafts,
        "needsSync": old.get("needsSync", []),
        "hooks": old.get("hooks", []),
        "metrics": old.get("metrics", {}),
    }


def write_state(slug, state):
    state["version"] = STATE_VERSION
    with open(state_path(slug), "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2)


def load_state(slug):
    sp = state_path(slug)
    if os.path.isfile(sp):
        try:
            return json.loads(read_text(sp))
        except json.JSONDecodeError:
            pass
    return build_state(slug)


def cmd_list(_args):
    out = []
    pdir = projects_dir()
    if not os.path.isdir(pdir):
        return {"projects": []}
    for slug in sorted(os.listdir(pdir), reverse=True):
        d = os.path.join(pdir, slug)
        if not os.path.isdir(d) or slug.startswith("."):
            continue
        st = load_state(slug)
        st = build_state(slug) if st.get("version") != STATE_VERSION else st
        out.append(st)
    return {"root": ROOT, "projects": out}


def cmd_show(args):
    # 只读：不写盘，避免把手工 set 的 skip / updated 覆盖掉
    return build_state(args.slug)


def cmd_init(args):
    st = build_state(args.slug)
    write_state(args.slug, st)
    return st


def cmd_migrate(_args):
    n = 0
    for slug in sorted(os.listdir(projects_dir())):
        d = os.path.join(projects_dir(), slug)
        if not os.path.isdir(d) or slug.startswith("."):
            continue
        write_state(slug, build_state(slug))
        n += 1
    return {"migrated": n}


def cmd_set(args):
    st = load_state(args.slug)
    if args.stage not in st["stages"]:
        return {"error": "阶段不存在: %s" % args.stage}
    if args.status not in ("empty", "wip", "done", "skip"):
        return {"error": "状态必须是 empty|wip|done|skip"}
    st["stages"][args.stage]["status"] = args.status
    st["stages"][args.stage]["updated"] = \
        datetime.now().strftime("%Y-%m-%d %H:%M")
    # current / progress 是派生字段，改完阶段必须重算，否则一直停在旧值
    st["current"] = next(
        (k for k, _, _, _ in STAGES if st["stages"][k]["status"] != "done"),
        STAGES[-1][0])
    st["progress"] = sum(1 for s in st["stages"].values()
                         if s["status"] == "done")
    # 同步 README 勾选框，让人和机器一致
    sync_readme(args.slug, st)
    write_state(args.slug, st)
    return st


def sync_readme(slug, state):
    path = os.path.join(slug_dir(slug), "README.md")
    text = read_text(path)
    if not text:
        return

    def repl(m):
        key = m.group(2)
        mark = "x" if state["stages"].get(key, {}).get("status") == "done" \
            else " "
        return "- [%s] %s %s" % (mark, key, m.group(3))

    new = re.sub(r"^- \[( |x)\] (\d{2}) (.*)$", repl, text, flags=re.M)
    if new != text:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(new)


def cmd_archive(args):
    """把主干文件归档一份到 drafts/，版本号自增，主干保持不变。"""
    st = load_state(args.slug)
    d = slug_dir(args.slug)
    src = os.path.join(d, args.file)
    if not os.path.isfile(src):
        return {"error": "文件不存在: %s" % args.file}
    base = os.path.basename(args.file)
    stem = base[:-3] if base.endswith(".md") else base
    entry = st["drafts"].setdefault(base, {"latest": 0, "files": []})
    entry["latest"] += 1
    rel = "drafts/%s-v%d.md" % (stem, entry["latest"])
    os.makedirs(os.path.join(d, "drafts"), exist_ok=True)
    shutil.copy2(src, os.path.join(d, rel))
    entry["files"].append(rel)
    write_state(args.slug, st)
    return {"archived": rel, "version": entry["latest"], "state": st}


def cmd_sync(args):
    """改了上游之后，列出可能失效的下游文件。"""
    st = load_state(args.slug)
    src = args.from_file
    targets = DOWNSTREAM.get(src, [])
    dirty = []
    for t in targets:
        s, _ = file_status(args.slug, t)
        if s == "done":
            dirty.append(t)
    st["needsSync"] = dirty
    write_state(args.slug, st)
    return {"from": src, "downstream": targets, "needsSync": dirty}


def cmd_final(args):
    st = load_state(args.slug)
    if args.video:
        st["final"]["video"] = args.video
    if args.cover:
        st["final"]["cover"] = args.cover
    write_state(args.slug, st)
    return st


def main():
    ap = argparse.ArgumentParser(description="Vflow 项目状态机")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("show"); p.add_argument("slug"); p.set_defaults(fn=cmd_show)
    p = sub.add_parser("init"); p.add_argument("slug"); p.set_defaults(fn=cmd_init)
    p = sub.add_parser("list"); p.set_defaults(fn=cmd_list)
    p = sub.add_parser("migrate"); p.set_defaults(fn=cmd_migrate)
    p = sub.add_parser("set")
    p.add_argument("slug"); p.add_argument("stage"); p.add_argument("status")
    p.set_defaults(fn=cmd_set)
    p = sub.add_parser("archive")
    p.add_argument("slug"); p.add_argument("file")
    p.set_defaults(fn=cmd_archive)
    p = sub.add_parser("sync")
    p.add_argument("slug"); p.add_argument("--from", dest="from_file",
                                           default="03-script.md")
    p.set_defaults(fn=cmd_sync)
    p = sub.add_parser("final")
    p.add_argument("slug"); p.add_argument("--video"); p.add_argument("--cover")
    p.set_defaults(fn=cmd_final)

    args = ap.parse_args()
    result = args.fn(args)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
