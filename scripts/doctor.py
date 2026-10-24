#!/usr/bin/env python3
"""Vflow 环境自检：一条命令看出哪里会卡住你。

新机器上装完跑一次；出片失败、状态不对、技能装没装，也先跑它。
只读为主，`--fix` 只做安全修复（补目录、对齐状态文件），不替你装软件。

用法：
    python3 doctor.py            人读的报告
    python3 doctor.py --json     机器读（回归测试用）
    python3 doctor.py --fix      修能安全修的部分，再报告
    python3 doctor.py --skip-network

检查项：
1. 环境：Python 版本 / 数据目录 / 必需目录
2. 依赖：ffmpeg / ffprobe / Pillow / Playwright / edge-tts / 中文字体
3. 资产：profile / 声音样本 / 风格卡 / 钩子库 / 词表 / 台账
4. 技能：skills/*/SKILL.md 引用到的脚本和文件是否真的存在
5. 状态：.vflow.json 和磁盘是否一致；有没有项目缺状态文件
6. 待办：超期未复盘

零依赖。
"""
import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import vflow_state as VS          # noqa: E402

ROOT = VS.ROOT
LEVEL_ORDER = {"fail": 0, "warn": 1, "ok": 2, "info": 3}
FONT_CANDIDATES = [
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def check(name, level, detail, fix=""):
    return {"name": name, "level": level, "detail": detail, "fix": fix}


def which(cmd):
    return shutil.which(cmd)


def version(cmd, args=("-version",)):
    if not which(cmd):
        return None
    try:
        r = subprocess.run([cmd, *args], capture_output=True, text=True,
                           timeout=20)
        out = (r.stdout or r.stderr).split("\n")[0].strip()
        m = re.search(r"(\d+\.\d+(?:\.\d+)?)", out)
        return m.group(1) if m else out[:40]
    except (OSError, subprocess.TimeoutExpired):
        return None


def has_module(name):
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


# ---------- 1. 环境 ----------

def check_env():
    rows = []
    v = sys.version_info
    rows.append(check("Python", "ok" if v >= (3, 8) else "fail",
                      "%d.%d.%d" % v[:3],
                      "" if v >= (3, 8) else "升级到 Python 3.8+"))
    rows.append(check("数据目录", "ok" if os.path.isdir(ROOT) else "fail",
                      ROOT, "" if os.path.isdir(ROOT) else "检查 VFLOW_HOME"))
    writable = os.access(ROOT, os.W_OK) if os.path.isdir(ROOT) else False
    rows.append(check("目录可写", "ok" if writable else "fail",
                      "可写" if writable else "不可写",
                      "" if writable else "检查目录权限"))
    for sub in ("projects", "pipeline", "scripts", "assets", "ledger"):
        p = os.path.join(ROOT, sub)
        rows.append(check("目录 %s/" % sub,
                          "ok" if os.path.isdir(p) else "warn",
                          "存在" if os.path.isdir(p) else "缺失",
                          "" if os.path.isdir(p) else "doctor --fix 或手动建"))
    return rows


# ---------- 2. 依赖 ----------

def check_deps():
    rows = []
    for cmd in ("ffmpeg", "ffprobe"):
        ver = version(cmd)
        rows.append(check(cmd, "ok" if ver else "fail",
                          ver or "未安装", "" if ver else "brew install ffmpeg"))
    rows.append(check("Pillow", "ok" if has_module("PIL") else "warn",
                      "已安装" if has_module("PIL") else "未安装",
                      "" if has_module("PIL") else
                      "pip install pillow --break-system-packages（字幕/封面质检要用）"))
    rows.append(check("Playwright", "ok" if has_module("playwright") else "warn",
                      "已安装" if has_module("playwright") else "未安装",
                      "" if has_module("playwright") else
                      "pip install playwright && playwright install chromium（出片要用）"))
    rows.append(check("edge-tts", "ok" if has_module("edge_tts") or which("edge-tts")
                      else "info",
                      "已安装" if has_module("edge_tts") or which("edge-tts")
                      else "未安装（可选，用 say 也能出片）"))
    if sys.platform == "darwin":
        rows.append(check("say", "ok" if which("say") else "info",
                          "可用" if which("say") else "不可用（TTS 兜底）"))
    font = next((f for f in FONT_CANDIDATES if os.path.isfile(f)), None)
    rows.append(check("中文字体", "ok" if font else "warn",
                      font or "没找到",
                      "" if font else "装 Noto Sans CJK 或指定 --font"))
    rows.append(check("yt-dlp", "ok" if which("yt-dlp") else "info",
                      "已安装" if which("yt-dlp") else "未安装（下载对标视频可选）"))
    return rows


# ---------- 3. 资产 ----------

def check_assets():
    rows = []
    prof = os.path.join(ROOT, "profile.md")
    if os.path.isfile(prof):
        text = VS.read_text(prof)
        empty_fields = [k for k in ("账号名", "阶段", "主受众")
                        if not re.search(r"\*\*%s\*\*：\s*\S" % k, text)]
        placeholder = "（例：" in text or bool(empty_fields)
        detail = ("待填：" + "、".join(empty_fields)) if empty_fields else "有内容"
        rows.append(check("profile.md", "warn" if placeholder else "ok",
                          detail,
                          "" if not placeholder else "把第 0–3 节填完再开工"))
    else:
        rows.append(check("profile.md", "fail", "不存在",
                          "跑 python3 scripts/setup.py 或让 Agent 引导"))

    samples = os.path.join(ROOT, "assets", "voice-samples")
    n = len([f for f in os.listdir(samples)
             if f.endswith(".md") and f.lower() != "readme.md"]) \
        if os.path.isdir(samples) else 0
    rows.append(check("声音样本", "ok" if n >= 2 else "warn",
                      "%d 篇" % n,
                      "" if n >= 2 else "放 2–3 篇自己写过的成稿，再跑 voice_profile.py build"))

    card = os.path.join(ROOT, "assets", "voice-card.md")
    if os.path.isfile(card):
        newest = 0
        if os.path.isdir(samples):
            for f in os.listdir(samples):
                if f.endswith(".md"):
                    newest = max(newest,
                                 os.path.getmtime(os.path.join(samples, f)))
        stale = newest and newest > os.path.getmtime(card) + 1
        rows.append(check("风格卡", "warn" if stale else "ok",
                          "比样本旧，需要重建" if stale else "已生成",
                          "python3 scripts/voice_profile.py build" if stale else ""))
    else:
        rows.append(check("风格卡", "warn", "还没生成",
                          "python3 scripts/voice_profile.py build"))

    for name, path in (("钩子库", "assets/hooks.md"),
                       ("结构库", "assets/structures.md"),
                       ("敏感词表", "assets/wordlist.md"),
                       ("证据台账", "ledger/evidence.md"),
                       ("选题池", "backlog.md"),
                       ("声明台账", "claims.md"),
                       ("内容日历", "calendar.md"),
                       ("内容策略", "docs/content-strategy.md")):
        p = os.path.join(ROOT, path)
        rows.append(check(name, "ok" if os.path.isfile(p) else "warn",
                          "存在" if os.path.isfile(p) else "缺失",
                          "" if os.path.isfile(p) else "doctor --fix"))
    return rows


# ---------- 4. 技能引用 ----------

def check_skills(fix=False):
    rows = []
    skills_dir = os.path.join(ROOT, "skills")
    if not os.path.isdir(skills_dir):
        return [check("skills/", "fail", "目录不存在")]
    checked = 0
    missing = []
    for d in sorted(os.listdir(skills_dir)):
        sk = os.path.join(skills_dir, d, "SKILL.md")
        if not os.path.isfile(sk):
            continue
        if not d.startswith("vflow"):
            continue          # 第三方技能（video-download 等）不强制
        text = VS.read_text(sk)
        # `$VFLOW/scripts/x.py` / `scripts/x.py` / `references/x` / `assets/x`
        for m in re.finditer(r"`([^`\n]+)`", text):
            ref = m.group(1).strip()
            ref = ref.split()[0] if ref.split() else ref
            if not re.match(r"^(\$VFLOW/)?(scripts|references|assets|pipeline)/"
                            r"[\w\-一-鿿./]+$", ref):
                continue
            rel = ref.replace("$VFLOW/", "")
            cand = [os.path.join(ROOT, rel)]
            if rel.startswith("references/"):
                cand.append(os.path.join(skills_dir, d, rel))
            checked += 1
            if not any(os.path.exists(c) for c in cand):
                missing.append("%s → %s" % (os.path.join("skills", d, "SKILL.md"), ref))
    rows.append(check("技能引用", "ok" if not missing else "fail",
                      "检查 %d 处引用，%d 处失效" % (checked, len(missing)),
                      "" if not missing else "死链：\n  " + "\n  ".join(missing[:12])))
    # 安装状态
    installed = []
    for t in ("claude", "workbuddy", "codex", "gemini", "agents"):
        d = os.path.expanduser("~/.%s/skills" % t) if t != "agents" else \
            os.path.expanduser("~/.agents/skills")
        if os.path.isdir(d) and os.path.isdir(os.path.join(d, "vflow")):
            installed.append(t)
    rows.append(check("技能安装", "info",
                      ("已装到：" + "、".join(installed)) if installed
                      else "未装到任何 Agent（当前目录直接跑也能用）",
                      "" if installed else "bash skills/install.sh"))
    return rows


# ---------- 5. 状态一致性 ----------

def check_state(fix=False):
    rows = []
    migrated = 0
    drift = []
    missing = []
    for slug in VS.iter_slugs():
        sp = VS.state_path(slug)
        if not os.path.isfile(sp):
            missing.append(slug)
            if fix:
                VS.write_state(slug, VS.build_state(slug))
                migrated += 1
            continue
        try:
            stored = json.loads(VS.read_text(sp))
        except json.JSONDecodeError:
            drift.append("%s：状态文件损坏" % slug)
            if fix:
                VS.write_state(slug, VS.build_state(slug))
                migrated += 1
            continue
        if stored.get("version") != VS.STATE_VERSION:
            if fix:
                VS.write_state(slug, VS.build_state(slug, stored))
                migrated += 1
            continue
        built = VS.build_state(slug, stored)
        diff = [k for k in built["stages"]
                if built["stages"][k]["status"] !=
                stored.get("stages", {}).get(k, {}).get("status")]
        if diff:
            drift.append("%s：%s" % (slug, "、".join(diff)))
            if fix:
                VS.write_state(slug, built)
                migrated += 1
    if drift:
        rows.append(check("状态一致", "warn",
                          "%d 个项目状态和磁盘不一致：\n  %s"
                          % (len(drift), "\n  ".join(drift[:8])),
                          "doctor --fix 会按磁盘重新推导" if not fix else
                          "已修复"))
    else:
        rows.append(check("状态一致", "ok", "状态文件和磁盘一致"))
    if missing:
        rows.append(check("状态文件", "warn",
                          "%d 个项目缺 .vflow.json（%s）"
                          % (len(missing), "、".join(missing[:5])),
                          "doctor --fix 补齐" if not fix else
                          ("已补 %d 个" % migrated)))
    elif fix and migrated:
        rows.append(check("状态文件", "ok", "已修复 %d 项" % migrated))
    return rows


# ---------- 5.5 版本 ----------

def check_version():
    vp = os.path.join(ROOT, "version.py")
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    out = []
    try:
        import version as V
        r = V.check()
        if r["ok"]:
            out.append(check("版本一致", "ok", "v%s" % r["current"]))
        else:
            out.append(check("版本一致", "fail", "；".join(r["problems"][:4]),
                             "python3 scripts/version.py check"))
    except Exception as e:
        out.append(check("版本一致", "warn", "检查失败：%s" % e))
    try:
        import publish as P
        cfg = P.load_config()
        mode = cfg.get("mode", "manual")
        out.append(check("发布模式", "ok" if mode == "manual" else "warn",
                         "%s%s" % (mode, "（allow_auto 已开）"
                                   if cfg.get("allow_auto") else ""),
                         "" if mode == "manual" else
                         "非 manual 模式会打开浏览器/尝试自动化，确认这是你要的"))
    except Exception:
        pass
    return out


# ---------- 6. 待办 ----------

def check_todo():
    rows = []
    try:
        import review as RV
    except ImportError:
        return rows
    pend = RV.cmd_pending(type("A", (), {"days": 7})())
    if pend.get("pending"):
        overdue = pend.get("overdue", 0)
        rows.append(check("待复盘", "warn" if overdue else "info",
                          "%d 条待回填，%d 条超 7 天" % (
                              pend["count"], overdue),
                          "python3 scripts/review.py pending"))
    else:
        rows.append(check("待复盘", "ok", "没有积压"))
    try:
        import content_calendar as CC
        due = CC.cmd_due(type("A", (), {"days": 3})())
        if due.get("count"):
            rows.append(check("排期到期", "warn" if due.get("overdue") else "info",
                              "%d 条 3 天内到期，%d 条已过期"
                              % (due["count"], due.get("overdue", 0)),
                              "python3 scripts/content_calendar.py due"))
    except Exception:
        pass
    try:
        import claims as CL
        cl = CL.cmd_list(type("A", (), {"slug": None, "status": None})())
        if cl.get("by_status", {}).get("待核"):
            rows.append(check("待核声明", "warn",
                              "%d 条声明没核过" % cl["by_status"]["待核"],
                              "python3 scripts/claims.py list --status 待核"))
    except Exception:
        pass
    try:
        import backlog as BL
        rows_b = BL.parse()
        cand = [r for r in rows_b if r["status"] == "候选"]
        rows.append(check("选题池", "info",
                          "候选 %d 条" % len(cand),
                          "python3 scripts/backlog.py list" if cand else ""))
    except ImportError:
        pass
    return rows


# ---------- 主流程 ----------

def run(fix=False):
    rows = []
    rows += check_env()
    rows += check_deps()
    rows += check_assets()
    rows += check_skills(fix)
    rows += check_state(fix)
    rows += check_version()
    rows += check_todo()
    summary = {lv: sum(1 for r in rows if r["level"] == lv)
               for lv in ("fail", "warn", "ok", "info")}
    return {"root": ROOT, "fix": fix, "summary": summary, "checks": rows,
            "ok": summary["fail"] == 0}


def render(result):
    icon = {"fail": "❌", "warn": "⚠️", "ok": "✅", "info": "ℹ️"}
    lines = ["Vflow 环境自检 · %s" % result["root"], ""]
    for r in result["checks"]:
        line = "%s %s：%s" % (icon[r["level"]], r["name"], r["detail"])
        lines.append(line)
        if r["fix"] and r["level"] in ("fail", "warn", "info"):
            lines.append("    → %s" % r["fix"].replace("\n", "\n      "))
    s = result["summary"]
    lines += ["", "结论：%s（fail %d / warn %d / ok %d）" % (
        "可以开工" if result["ok"] else "先修 fail 项",
        s["fail"], s["warn"], s["ok"])]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Vflow 环境自检")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--skip-network", action="store_true")
    args = ap.parse_args()
    result = run(fix=args.fix)
    if args.json:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        print(render(result))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
