#!/usr/bin/env python3
"""Vflow 项目状态机。

项目状态的唯一真源是 `projects/<slug>/.vflow.json`。
工作台、脚本、Skill 都读它，不再靠猜文件是否存在、模板有没有被填。

用法：
    python3 vflow_state.py show <slug>                看一个项目（只读，不写盘）
    python3 vflow_state.py list                       列全部项目（只读）
    python3 vflow_state.py init <slug>                建项目并把模板铺进去、写状态
    python3 vflow_state.py migrate [--write]          给已有项目补状态；默认只预览
    python3 vflow_state.py set <slug> <阶段> <状态>      状态: empty|wip|done|skip|auto
    python3 vflow_state.py archive <slug> <文件>        归档当前内容为草稿版本
    python3 vflow_state.py sync <slug> [--from 03-script.md]   改上游后列出待同步下游
    python3 vflow_state.py final <slug> --video <路径> [--cover <路径>] [--platform douyin]

状态规则（v2）：
1. 磁盘内容推导出 empty / wip / done 三态；模板标记视为 empty。
2. 显式 `set` 是人的判断，内容没变就保留（done 记下当时的内容指纹）。
3. 内容变了（指纹对不上）→ done 自动退回 wip，不会假装还是定稿。
4. 制作（06）以交付指针为准：有终版成片才算 done。
5. 复盘（07）以数据为准：06-review.md 里有真实数字才算 done，写了但没数据是 wip。

设计原则：
1. 状态只有一份，写在 .vflow.json，别处都是派生。
2. 版本：主干文件永远是最新版；归档进 drafts/ 带版本号，永不覆盖。
3. 改上游要告诉使用者下游哪些文件可能失效，但不自动改——判断权在人。
"""
import argparse
import hashlib
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
REVIEW_MARKER = "vflow-review-data"
VIDEO_EXT = (".mp4", ".mov")

# 阶段：编号 / 名字 / 产出文件 / 负责 skill / 完成判据
# 判据 kind: file = 产出文件有内容；video = 有终版成片；data = 复盘有数据
STAGES = [
    ("01", "选题", "01-topic.md", "vflow-topic", "file"),
    ("02", "结构", "02-outline.md", "vflow-outline", "file"),
    ("03", "剧本", "03-script.md", "vflow-script", "file"),
    ("04", "包装", "04-package.md", "vflow-package", "file"),
    ("05", "检查", "05-check.md", "vflow-check", "file"),
    ("06", "制作", "publish-copy.md", "vflow-produce", "video"),
    ("07", "复盘", "06-review.md", "vflow-review", "data"),
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

STATE_VERSION = 2


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


def content_hash(path):
    """文件内容指纹。缺失或空模板返回 None。

    机器质检/复盘数据这类「自动追加节」不算内容变更：跑一次 qc.py 不该让
    已经定稿的检查阶段退回 wip。
    """
    if not os.path.isfile(path):
        return None
    text = read_text(path)
    if not text.strip() or TEMPLATE_MARK in text:
        return None
    if os.path.basename(path) == "05-check.md":
        text = re.sub(r"\n## 机器质检\n.*?(?=\n## |\Z)", "\n", text,
                      flags=re.S)
    if os.path.basename(path) == "03-script.md":
        text = re.sub(r"\n## 机器自检\n.*?(?=\n## |\Z)", "\n", text,
                      flags=re.S)
    norm = re.sub(r"\s+", " ", text).strip()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def mtime_str(path):
    try:
        return datetime.fromtimestamp(
            os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M")
    except OSError:
        return None


def final_video(slug):
    """交付指针：优先 .vflow.json 里显式记录的，其次 output/ 里的 final-*。"""
    out = os.path.join(slug_dir(slug), "output")
    if os.path.isdir(out):
        vids = [f for f in os.listdir(out) if f.lower().endswith(VIDEO_EXT)]
        finals = sorted(f for f in vids if f.startswith("final"))
        if finals:
            return "output/" + finals[-1]
    return None


def any_video(slug):
    for sub in ("output", "deck/final"):
        d = os.path.join(slug_dir(slug), *sub.split("/"))
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.lower().endswith(VIDEO_EXT):
                return "%s/%s" % (sub, f)
    return None


def review_rows(path):
    """从 06-review.md 的极简标记里读出每平台是否有真实数字。

    新版 review.py 会写 `<!-- vflow-review-data {...} -->`；旧模板写的
    表格只要「播放/完播」那一行有数字，也算有数据。
    """
    if not os.path.isfile(path):
        return {}
    text = read_text(path)
    if TEMPLATE_MARK in text:
        return {}
    m = re.search(r"<!--\s*%s\s*(\{.*?\})\s*-->" % REVIEW_MARKER,
                  text, re.S)
    if m:
        try:
            data = json.loads(m.group(1))
            return {k: v for k, v in data.items() if isinstance(v, dict)}
        except json.JSONDecodeError:
            pass
    rows = {}
    in_data = False
    for line in text.split("\n"):
        if line.startswith("## 数据"):
            in_data = True
            continue
        if in_data and line.startswith("## "):
            break
        if not in_data or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 3 and cells[0] in ("播放 / 曝光", "播放", "曝光"):
            if any(re.search(r"\d", c) for c in cells[1:]):
                rows["douyin"] = {"播放": cells[1]}
                if len(cells) > 2:
                    rows["xhs"] = {"播放": cells[2]}
    return rows


def review_numbers(slug):
    """把复盘数据统一成 {平台: {指标: 数字}}，方便算指标。

    两个来源合并：.vflow.json 的 metrics（review.py 写，机器读）
    + 06-review.md 的表格（人填，兜底）。前者优先。
    """
    out = {}

    # 1. 状态文件里的机器可读指标
    sp = state_path(slug)
    if os.path.isfile(sp):
        try:
            raw = json.loads(read_text(sp))
        except json.JSONDecodeError:
            raw = {}
        for plat, row in (raw.get("metrics") or {}).items():
            vals = {}
            if isinstance(row, dict):
                for k, v in row.items():
                    n = v if isinstance(v, (int, float)) else None
                    if n is None:
                        m = re.search(r"-?\d+(?:\.\d+)?", str(v))
                        n = float(m.group(0)) if m else None
                    if n is not None:
                        vals[k] = float(n)
            if vals:
                out[plat] = vals

    # 2. md 表格（旧数据 / 手工填的）
    for plat, row in review_rows(
            os.path.join(slug_dir(slug), "06-review.md")).items():
        vals = out.setdefault(plat, {})
        for k, v in row.items():
            m = re.search(r"-?\d+(?:\.\d+)?", str(v))
            if m:
                vals.setdefault(k, float(m.group(0)))
    return {k: v for k, v in out.items() if v}


def stage_file_status(slug, fname):
    path = os.path.join(slug_dir(slug), fname)
    return content_hash(path), mtime_str(path)


def derived_stage(slug, key, fname, kind, final_hint=None):
    """只从磁盘推导，不看旧状态。返回 (status, fp, updated)。"""
    if kind == "video":
        video = final_hint or final_video(slug)
        if video and os.path.isfile(os.path.join(slug_dir(slug), video)):
            return "done", None, mtime_str(os.path.join(slug_dir(slug), video))
        fp, _ = stage_file_status(slug, fname)
        if fp or any_video(slug):
            return "wip", fp, mtime_str(
                os.path.join(slug_dir(slug), fname))
        return "empty", None, None

    if kind == "data":
        nums = review_numbers(slug)
        fp, _ = stage_file_status(slug, fname)
        if nums:
            return "done", fp, mtime_str(
                os.path.join(slug_dir(slug), fname))
        if fp:
            return "wip", fp, mtime_str(
                os.path.join(slug_dir(slug), fname))
        return "empty", None, None

    fp, updated = stage_file_status(slug, fname)
    if fp:
        return "wip", fp, updated
    return "empty", None, None


def merge_stage(key, kind, derived, prev):
    """人的显式标记 + 磁盘现状 → 最终状态。

    prev 是 .vflow.json 里上次保存的记录；没有就完全按磁盘。
    """
    status, fp, updated = derived
    prev = prev or {}
    # 旧版状态文件没有 manual 字段但记了 done：当作人确认过，指纹按当前内容
    if "manual" not in prev and prev.get("status") == "done":
        prev = dict(prev, manual=True, doneFp=prev.get("doneFp") or fp)
    manual = prev.get("manual")

    if not manual:
        return {"status": status, "fp": fp, "updated": updated,
                "manual": False, "doneFp": (prev or {}).get("doneFp")}

    prev_status = prev.get("status")
    if prev_status == "skip":
        return {"status": "skip", "fp": fp, "updated": updated,
                "manual": True, "doneFp": prev.get("doneFp")}
    if prev_status != "done":
        # 显式 wip / empty：以磁盘为准，没内容时一定是 empty。
        if status == "empty":
            return {"status": "empty", "fp": None, "updated": None,
                    "manual": True, "doneFp": prev.get("doneFp")}
        # 内容又回到了当初定稿的那一版（比如自动追加的节被忽略），恢复 done。
        if prev.get("doneFp") and fp == prev.get("doneFp"):
            return {"status": "done", "fp": fp, "updated": updated,
                    "manual": True, "doneFp": prev.get("doneFp")}
        # 制作/复盘是交付物判据：东西真的出来了就该算完成，不受旧 wip 拖累。
        if kind != "file" and status == "done":
            return {"status": "done", "fp": fp, "updated": updated,
                    "manual": True, "doneFp": None}
        return {"status": "wip", "fp": fp, "updated": updated,
                "manual": True, "doneFp": prev.get("doneFp")}

    # 显式 done：内容变了就退回 wip，避免把改过的稿子当定稿
    done_fp = prev.get("doneFp")
    if kind == "file":
        if status == "empty":
            return {"status": "empty", "fp": None, "updated": None,
                    "manual": True, "doneFp": None}
        if done_fp and fp != done_fp:
            return {"status": "wip", "fp": fp, "updated": updated,
                    "manual": True, "doneFp": done_fp}
        return {"status": "done", "fp": fp, "updated": updated,
                "manual": True, "doneFp": done_fp or fp}

    # 制作 / 复盘：交付物被删就退回，否则保留 done
    if prev_status == "done" and status in ("done", "wip"):
        return {"status": "done" if status == "done" else "wip",
                "fp": fp, "updated": updated, "manual": True,
                "doneFp": done_fp}
    return {"status": status, "fp": fp, "updated": updated,
            "manual": True, "doneFp": done_fp}


def build_state(slug, prev=None):
    """从磁盘现状 + 上次保存的人为标记推导状态（不写盘）。"""
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

    if prev is None:
        prev = {}
        sp = state_path(slug)
        if os.path.isfile(sp):
            try:
                prev = json.loads(read_text(sp))
            except json.JSONDecodeError:
                prev = {}

    stages = {}
    final_hint = prev.get("final", {}).get("video")
    for key, name, fname, skill, kind in STAGES:
        derived = derived_stage(slug, key, fname, kind, final_hint)
        merged = merge_stage(key, kind, derived, prev.get("stages", {}).get(key))
        merged.update({"name": name, "file": fname, "skill": skill})
        stages[key] = merged

    current = STAGES[-1][0]
    for key, _, _, _, _ in STAGES:
        if stages[key]["status"] != "done":
            current = key
            break

    # 版本：drafts/ 里已归档的
    drafts = prev.get("drafts", {})
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

    final = dict(prev.get("final", {}))
    if not final.get("video"):
        pick = final_video(slug) or any_video(slug)
        if pick:
            final["video"] = pick

    qc = dict(prev.get("qc", {}))
    if qc.get("generated"):
        # 出版子或改了检查报告之后，旧质检结论就不算数了
        try:
            gen = datetime.strptime(qc["generated"], "%Y-%m-%d %H:%M")
            newest = 0.0
            for rel in (final.get("video"),
                        "05-check.md"):
                if rel:
                    fp = os.path.join(d, rel)
                    if os.path.isfile(fp):
                        newest = max(newest, os.path.getmtime(fp))
            if newest and newest > gen.timestamp() + 60:
                qc["stale"] = True
            else:
                qc.pop("stale", None)
        except ValueError:
            pass

    published = dict(prev.get("published", {}))
    nums = review_numbers(slug)
    review = {
        "published": published,
        "pending": bool(published) and not nums and not published.get("reviewed"),
        "has_data": bool(nums),
    }

    # 定稿之后又被改过的阶段：下游可能需要跟着改
    edited = [key for key, s in stages.items()
              if s["status"] == "wip" and s.get("doneFp")]

    return {
        "version": STATE_VERSION,
        "slug": slug,
        "title": title,
        "created": created or datetime.now().strftime("%Y-%m-%d"),
        "platforms": prev.get("platforms", ["douyin", "xhs"]),
        "stages": stages,
        "current": current,
        "progress": sum(1 for s in stages.values() if s["status"] == "done"),
        "final": final,
        "drafts": drafts,
        "published": published,
        "review": review,
        "qc": qc,
        "needsSync": prev.get("needsSync", []),
        "edited": edited,
        "hooks": prev.get("hooks", []),
        "metrics": prev.get("metrics", {}),
    }


def write_state(slug, state):
    state["version"] = STATE_VERSION
    os.makedirs(os.path.dirname(state_path(slug)), exist_ok=True)
    with open(state_path(slug), "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2)


def load_state(slug):
    sp = state_path(slug)
    if os.path.isfile(sp):
        try:
            return json.loads(read_text(sp))
        except json.JSONDecodeError:
            pass
    return {}


def iter_slugs():
    pdir = projects_dir()
    if not os.path.isdir(pdir):
        return
    for slug in sorted(os.listdir(pdir), reverse=True):
        d = os.path.join(pdir, slug)
        if os.path.isdir(d) and not slug.startswith("."):
            yield slug


def cmd_list(_args):
    return {"root": ROOT,
            "projects": [build_state(slug) for slug in iter_slugs()]}


def cmd_show(args):
    return build_state(args.slug)


def cmd_init(args):
    pdir = os.path.join(projects_dir(), args.slug)
    os.makedirs(pdir, exist_ok=True)
    tmpl_dir = os.path.join(ROOT, "pipeline")
    copied = []
    if os.path.isdir(tmpl_dir):
        for fn in sorted(os.listdir(tmpl_dir)):
            if not fn.endswith(".md"):
                continue
            dst = os.path.join(pdir, fn)
            if not os.path.exists(dst):
                shutil.copy2(os.path.join(tmpl_dir, fn), dst)
                copied.append(fn)
    for sub in ("assets", "output", "deck"):
        os.makedirs(os.path.join(pdir, sub), exist_ok=True)
    st = build_state(args.slug)
    write_state(args.slug, st)
    sync_readme(args.slug, st)
    return {"slug": args.slug, "templates": copied, "state": st}


def cmd_migrate(args):
    rows = []
    for slug in iter_slugs():
        st = build_state(slug)
        if args.write:
            write_state(slug, st)
        rows.append({"slug": slug,
                     "current": st["current"],
                     "progress": st["progress"],
                     "states": {k: v["status"] for k, v in st["stages"].items()}})
    return {"write": bool(args.write), "projects": rows}


def cmd_set(args):
    st = build_state(args.slug)
    if args.stage not in st["stages"]:
        return {"error": "阶段不存在: %s" % args.stage}
    if args.status not in ("empty", "wip", "done", "skip", "auto"):
        return {"error": "状态必须是 empty|wip|done|skip|auto"}

    key = args.stage
    row = st["stages"][key]
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    if args.status == "auto":
        row["manual"] = False
        row.pop("doneFp", None)
        derived = derived_stage(args.slug, key, row["file"],
                                [s[4] for s in STAGES if s[0] == key][0])
        row["status"], row["fp"], row["updated"] = derived
    else:
        if args.status == "done" and row["status"] == "done" \
                and row.get("manual") and row.get("doneFp"):
            # 已经是定稿且内容没变，重复标记不刷新指纹
            pass
        else:
            row["status"] = args.status
            row["manual"] = True
            row["updated"] = now
            if args.status == "done":
                kind = [s[4] for s in STAGES if s[0] == key][0]
                if kind == "file":
                    row["doneFp"] = row.get("fp")
                else:
                    row["doneFp"] = None
            else:
                row.pop("doneFp", None)

    st["current"] = next(
        (k for k, _, _, _, _ in STAGES
         if st["stages"][k]["status"] != "done"), STAGES[-1][0])
    st["progress"] = sum(1 for s in st["stages"].values()
                         if s["status"] == "done")
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

    new = re.sub(r"^- \[( |x)\] (\d{2}(?:b)?) (.*)$", repl, text, flags=re.M)
    if new != text:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(new)


def cmd_archive(args):
    """把主干文件归档一份到 drafts/，版本号自增，主干保持不变。"""
    st = build_state(args.slug)
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
    st = build_state(args.slug)
    src = args.from_file
    targets = DOWNSTREAM.get(src, [])
    dirty = []
    for t in targets:
        for key, _, fname, _, kind in STAGES:
            if fname == t and st["stages"][key]["status"] != "empty":
                dirty.append(t)
    st["needsSync"] = dirty
    write_state(args.slug, st)
    return {"from": src, "downstream": targets, "needsSync": dirty}


def cmd_final(args):
    st = build_state(args.slug)
    final = dict(st["final"])
    if args.video:
        final["video"] = args.video
    if args.cover:
        final["cover"] = args.cover
    st["final"] = final
    if args.platform:
        plat = st["published"].setdefault(args.platform, {})
        plat.setdefault("platform", args.platform)
        plat["published_at"] = plat.get(
            "published_at") or datetime.now().strftime("%Y-%m-%d %H:%M")
    write_state(args.slug, st)
    return st


def cmd_published(args):
    st = build_state(args.slug)
    plat = st["published"].setdefault(args.platform, {})
    plat["published_at"] = args.at or datetime.now().strftime("%Y-%m-%d %H:%M")
    plat["counts_as"] = args.counts_as or plat.get("counts_as") or "real"
    write_state(args.slug, st)
    return {"slug": args.slug, "published": st["published"],
            "review": st["review"]}


def main():
    ap = argparse.ArgumentParser(description="Vflow 项目状态机")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("show"); p.add_argument("slug"); p.set_defaults(fn=cmd_show)
    p = sub.add_parser("init"); p.add_argument("slug"); p.set_defaults(fn=cmd_init)
    p = sub.add_parser("list"); p.set_defaults(fn=cmd_list)
    p = sub.add_parser("migrate")
    p.add_argument("--write", action="store_true", help="真正写回 .vflow.json")
    p.set_defaults(fn=cmd_migrate)
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
    p.add_argument("--platform", choices=["douyin", "xhs"])
    p.set_defaults(fn=cmd_final)
    p = sub.add_parser("published")
    p.add_argument("slug"); p.add_argument("--platform", required=True,
                                           choices=["douyin", "xhs"])
    p.add_argument("--at"); p.add_argument("--counts-as",
                                           choices=["real", "test"])
    p.set_defaults(fn=cmd_published)

    args = ap.parse_args()
    result = args.fn(args)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
