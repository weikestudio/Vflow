#!/usr/bin/env python3
"""Vflow 版本库：记录每个版本改了什么，并校验技能版本号一致。

用法：
    python3 version.py current             当前版本
    python3 version.py check               校验：SKILL.md 的 version 字段、CHANGELOG、版本文件是否一致
    python3 version.py list                列出所有版本
    python3 version.py bump <版本> --note  开一个新版本（生成骨架，不自动改技能）

约定：
- 版本号写在 `VERSION` 文件里，格式 `MAJOR.MINOR.PATCH`。
- 每个 `skills/*/SKILL.md` 的 frontmatter 里有 `version:`，必须和 VERSION 一致。
- 每个版本在 `versions/vX.Y.Z.md` 有一份记录，`versions/CHANGELOG.md` 是索引。
- 技能变了但版本没变，`check` 会报错——这是防止"改了没记"。

零依赖。
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VERSION_FILE = os.path.join(ROOT, "VERSION")
VERSIONS = os.path.join(ROOT, "versions")
SKILLS = os.path.join(ROOT, "skills")
CHANGELOG = os.path.join(VERSIONS, "CHANGELOG.md")
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def read(p):
    try:
        with open(p, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def current():
    v = read(VERSION_FILE).strip()
    return v if v else "0.0.0"


def skill_version(path):
    text = read(path)
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return None
    m2 = re.search(r"^version:\s*(.+)$", m.group(1), re.M)
    return m2.group(1).strip().strip('"') if m2 else None


def skill_names():
    out = []
    if not os.path.isdir(SKILLS):
        return out
    for d in sorted(os.listdir(SKILLS)):
        p = os.path.join(SKILLS, d, "SKILL.md")
        if os.path.isfile(p):
            out.append((d, p))
    return out


def check():
    problems = []
    warnings = []
    v = current()
    if not SEMVER.match(v):
        problems.append("VERSION 文件内容不是 MAJOR.MINOR.PATCH：%r" % v)
    ver_file = os.path.join(VERSIONS, "v%s.md" % v)
    if not os.path.isfile(ver_file):
        problems.append("缺少版本记录 versions/v%s.md" % v)
    for d, p in skill_names():
        sv = skill_version(p)
        if not sv:
            # 第三方技能（不归 Vflow 版本管理）允许没有
            if d.startswith("vflow"):
                problems.append("skills/%s/SKILL.md 缺 version 字段" % d)
            else:
                warnings.append("skills/%s 是第三方技能，不参与版本校验" % d)
        elif sv != v:
            problems.append("skills/%s/SKILL.md 版本 %s ≠ 当前 %s" % (d, sv, v))
    if not os.path.isfile(CHANGELOG):
        problems.append("缺少 versions/CHANGELOG.md")
    return {"current": v, "problems": problems, "warnings": warnings,
            "ok": not problems}


def cmd_current(_a):
    return {"version": current()}


def cmd_check(_a):
    return check()


def cmd_list(_a):
    rows = []
    if os.path.isdir(VERSIONS):
        for f in sorted(os.listdir(VERSIONS)):
            m = re.match(r"^v(\d+\.\d+\.\d+)\.md$", f)
            if m:
                text = read(os.path.join(VERSIONS, f))
                title = re.search(r"^# (.+)$", text, re.M)
                date = re.search(r"^\s*-\s*\*\*日期\*\*：(.+)$", text, re.M)
                rows.append({"version": m.group(1),
                             "title": title.group(1) if title else "",
                             "date": date.group(1).strip() if date else ""})
    return {"current": current(), "versions": rows}


def cmd_bump(a):
    if not SEMVER.match(a.version):
        return {"error": "版本号必须是 MAJOR.MINOR.PATCH"}
    if os.path.isfile(os.path.join(VERSIONS, "v%s.md" % a.version)):
        return {"error": "版本 %s 已存在" % a.version}
    os.makedirs(VERSIONS, exist_ok=True)
    body = """# Vflow v%s

- **日期**：%s
- **类型**：%s
- **摘要**：%s

## 改了什么

（按模块写，每条能对应到一个文件或一组文件）

## 为什么

（解决什么真实问题，不写"优化体验"这种空话）

## 影响面

- 数据格式：
- 技能行为：
- 破坏性变更：

## 验收

- [ ] `bash tests/run_regression.sh` 全绿
- [ ] `python3 scripts/doctor.py` 无 fail
- [ ] `python3 scripts/version.py check` 通过
""" % (a.version, a.note_date or "", a.note_type or "minor",
       a.note or "")
    with open(os.path.join(VERSIONS, "v%s.md" % a.version), "w",
              encoding="utf-8") as fh:
        fh.write(body)
    with open(VERSION_FILE, "w", encoding="utf-8") as fh:
        fh.write(a.version + "\n")
    with open(CHANGELOG, "a", encoding="utf-8") as fh:
        fh.write("- [v%s](v%s.md) %s — %s\n" % (
            a.version, a.version, a.note_date or "", a.note or ""))
    return {"ok": True, "version": a.version,
            "todo": "把 skills/*/SKILL.md 的 version 改成 %s" % a.version}


def main():
    ap = argparse.ArgumentParser(description="Vflow 版本库")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("current").set_defaults(fn=cmd_current)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    p = sub.add_parser("bump")
    p.add_argument("version")
    p.add_argument("--note", default="")
    p.add_argument("--date", dest="note_date", default="")
    p.add_argument("--type", dest="note_type", default="minor")
    p.set_defaults(fn=cmd_bump)
    args = ap.parse_args()
    result = args.fn(args)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    if args.cmd == "check":
        sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
