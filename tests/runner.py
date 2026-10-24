#!/usr/bin/env python3
"""Vflow 回归测试 runner。

纯标准库。每个用例在独立的临时数据目录里跑，不碰真实项目。

用法：
    python3 tests/runner.py             全部跑
    python3 tests/runner.py --only state 只跑某个套件
    python3 tests/runner.py --verbose   失败时打印完整输出
    bash tests/run_regression.sh        一键（含 suite 列表）

用例分两类：
1. 状态机 / 复盘 / 质检 / 钩子 / 台账 —— 用真实脚本跑
2. 技能契约（定位锁）—— 断言 SKILL.md 里必须存在的约束，改 skill 改坏了会红
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPTS = os.path.join(ROOT, "scripts")

FAILS = []


# ---------- 工具 ----------

def workspace():
    """临时数据目录：复制 scripts + pipeline + assets + VERSION + versions。"""
    d = tempfile.mkdtemp(prefix="vflow-test-")
    shutil.copytree(SCRIPTS, os.path.join(d, "scripts"))
    shutil.copytree(os.path.join(ROOT, "pipeline"),
                    os.path.join(d, "pipeline"))
    os.makedirs(os.path.join(d, "projects"))
    os.makedirs(os.path.join(d, "assets"))
    os.makedirs(os.path.join(d, "ledger"))
    for f in ("hooks.md", "wordlist.md", "structures.md"):
        src = os.path.join(ROOT, "assets", f)
        if os.path.isfile(src):
            shutil.copy(src, os.path.join(d, "assets", f))
    for f in ("profile.md", "VERSION"):
        src = os.path.join(ROOT, f)
        if os.path.isfile(src):
            shutil.copy(src, os.path.join(d, f))
    src = os.path.join(ROOT, "versions")
    if os.path.isdir(src):
        shutil.copytree(src, os.path.join(d, "versions"))
    # backlog / claims / calendar 由各套件自己创建，避免带上真实数据
    return d


def run(d, *args, check=False, env=None):
    e = dict(os.environ)
    e["VFLOW_HOME"] = d
    e["VFLOW_PY"] = sys.executable
    if env:
        e.update(env)
    r = subprocess.run([sys.executable] + list(args), cwd=d, env=e,
                       capture_output=True, text=True, timeout=180)
    if check and r.returncode not in (0,):
        raise AssertionError("命令失败 %s\nstdout:%s\nstderr:%s"
                             % (" ".join(args), r.stdout, r.stderr))
    return r


def cmd(d, script, *args):
    return run(d, os.path.join("scripts", script), *args)


def jout(r):
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError("不是 JSON：%s\n%s" % (r.stdout[:500], e))


def read(d, rel):
    with open(os.path.join(d, rel), encoding="utf-8") as fh:
        return fh.read()


def write(d, rel, text):
    p = os.path.join(d, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text)


def touch_filled(d, rel, body):
    write(d, rel, "<!-- 已填写 -->\n" + body)


def new_proj(d, name="测试选题"):
    r = subprocess.run(
        ["bash", os.path.join(d, "scripts", "new_project.sh"), name],
        cwd=d, env={**os.environ, "VFLOW_HOME": d,
                    "VFLOW_PY": sys.executable},
        capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, (r.stdout + r.stderr)
    if "已存在" in r.stdout:
        return [s for s in os.listdir(os.path.join(d, "projects"))][0]
    line = [l for l in r.stdout.splitlines() if "项目已创建:" in l][0]
    slug = line.split("项目已创建:")[1].strip().rstrip("/").split("/")[-1]
    assert os.path.isdir(os.path.join(d, "projects", slug)), \
        "项目目录没建出来：%r" % slug
    return slug


def new_proj_unique(d, base):
    """同一套件里开多个项目时给个序号，避免同日同名冲突。"""
    n = len(os.listdir(os.path.join(d, "projects")))
    return new_proj(d, "%s-%d" % (base, n))


def test(name, fn, verbose=False):
    try:
        fn()
        print("  ✅ %s" % name)
        return True
    except Exception as e:
        print("  ❌ %s" % name)
        print("     %s" % str(e).replace("\n", "\n     "))
        FAILS.append(name)
        return False


# ---------- 套件：状态机 ----------

def suite_state():
    d = workspace()
    try:
        slug = new_proj(d)
        # 1. 模板 = empty，有内容 = wip
        st = jout(cmd(d, "vflow_state.py", "show", slug))
        assert all(s["status"] == "empty" for s in st["stages"].values()), \
            "新项目应该七阶段全空：%s" % {k: v["status"] for k, v in st["stages"].items()}
        touch_filled(d, "%s/01-topic.md" % ("projects/" + slug), "# 选题\n有内容\n")
        st = jout(cmd(d, "vflow_state.py", "show", slug))
        assert st["stages"]["01"]["status"] == "wip", "有内容但没标完成应是 wip"
        assert st["current"] == "01", "当前阶段应停在 01"

        # 2. 显式 done 保留；改内容自动退回 wip
        cmd(d, "vflow_state.py", "set", slug, "01", "done")
        st = jout(cmd(d, "vflow_state.py", "show", slug))
        assert st["stages"]["01"]["status"] == "done"
        assert st["stages"]["01"]["manual"] is True
        st_before = os.path.getmtime(os.path.join(d, "projects", slug, ".vflow.json"))
        with open(os.path.join(d, "projects", slug, "01-topic.md"), "a") as fh:
            fh.write("\n补一句\n")
        os.utime(os.path.join(d, "projects", slug, "01-topic.md"),
                 (st_before + 10, st_before + 10))
        st = jout(cmd(d, "vflow_state.py", "show", slug))
        assert st["stages"]["01"]["status"] == "wip", \
            "定稿后又改内容，应退回 wip，实际 %s" % st["stages"]["01"]["status"]

        # 3. skip 保留
        cmd(d, "vflow_state.py", "set", slug, "02", "skip")
        st = jout(cmd(d, "vflow_state.py", "show", slug))
        assert st["stages"]["02"]["status"] == "skip", "skip 应保留"

        # 4. 制作看交付指针；复盘看数据
        touch_filled(d, "projects/%s/publish-copy.md" % slug, "# 文案\n有内容\n")
        st = jout(cmd(d, "vflow_state.py", "show", slug))
        assert st["stages"]["06"]["status"] == "wip", "有文案没成片应是 wip"
        os.makedirs(os.path.join(d, "projects", slug, "output"), exist_ok=True)
        open(os.path.join(d, "projects", slug, "output", "final-x.mp4"), "w").close()
        cmd(d, "vflow_state.py", "final", slug, "--video", "output/final-x.mp4")
        st = jout(cmd(d, "vflow_state.py", "show", slug))
        assert st["stages"]["06"]["status"] == "done", "有终版成片应是 done"
        touch_filled(d, "projects/%s/06-review.md" % slug, "# 复盘\n## 数据\n")
        st = jout(cmd(d, "vflow_state.py", "show", slug))
        assert st["stages"]["07"]["status"] == "wip", "复盘写了但没数据应是 wip"
        cmd(d, "review.py", "fill", slug, "--platform", "douyin", "--play", "1000")
        st = jout(cmd(d, "vflow_state.py", "show", slug))
        assert st["stages"]["07"]["status"] == "done", "有数据后复盘应是 done"

        # 5. 自动追加的机器质检节不算内容变更：跑完 qc 不能把定稿的 05 踢回 wip
        touch_filled(d, "projects/%s/05-check.md" % slug, "# 检查\n三层通过\n")
        cmd(d, "vflow_state.py", "set", slug, "05", "done")
        cmd(d, "qc.py", "cover", slug)
        assert "## 机器质检" in read(d, "projects/%s/05-check.md" % slug)
        st = jout(cmd(d, "vflow_state.py", "show", slug))
        assert st["stages"]["05"]["status"] == "done", \
            "qc 追加的机器质检节不该让定稿的检查阶段退回 wip"

        # 6. 只读命令不写盘
        before = json.loads(read(d, "projects/%s/.vflow.json" % slug))
        r = cmd(d, "vflow_state.py", "list")
        after = json.loads(read(d, "projects/%s/.vflow.json" % slug))
        assert before == after, "只读命令不应该改状态文件"
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---------- 套件：复盘 ----------

def suite_review():
    d = workspace()
    try:
        slug = new_proj(d, "复盘测试")
        for f in ("01-topic.md", "02-outline.md", "03-script.md",
                  "04-package.md", "05-check.md"):
            touch_filled(d, "projects/%s/%s" % (slug, f), "# 有内容\n")
        os.makedirs(os.path.join(d, "projects", slug, "output"), exist_ok=True)
        open(os.path.join(d, "projects", slug, "output", "final.mp4"), "w").close()

        # 只有真实发布才进待复盘
        cmd(d, "review.py", "published", slug, "--platform", "douyin",
            "--counts-as", "test")
        p = jout(cmd(d, "review.py", "pending"))
        assert p["count"] == 0, "测试发布不该进待复盘"
        cmd(d, "review.py", "published", slug, "--platform", "douyin",
            "--at", "2026-01-20 20:00")
        p = jout(cmd(d, "review.py", "pending"))
        assert p["count"] == 1 and p["overdue"], "几个月前发布应超期：%s" % p

        # 数据回填：互动率算对，09类边界
        r = jout(cmd(d, "review.py", "fill", slug, "--platform", "douyin",
                     "--play", "10000", "--ret5", "45", "--finish", "28",
                     "--like", "200", "--comment", "50", "--save", "30",
                     "--share", "20", "--follow", "10",
                     "--good", "开头具体", "--action", "压到 3 页"))
        assert r["metrics"]["互动率"] == 3.0, "互动率应是 (200+50+30+20)/10000=3%%"
        assert r["review_stage"] == "done"
        p = jout(cmd(d, "review.py", "pending"))
        assert p["count"] == 0, "回填后不应再待复盘"

        md = read(d, "projects/%s/06-review.md" % slug)
        assert "10,000" in md and "压到 3 页" in md and "## 数据" in md
        assert "vflow-template" not in md, "回填后应去掉模板标记"

        # 同桶均值
        s = jout(cmd(d, "review.py", "stats", "--platform", "douyin"))
        assert s["overall"]["count"] == 1
        assert s["overall"]["metrics"]["播放"]["mean"] == 10000.0

        # 台账门槛：一条不够，三条才准
        n = jout(cmd(d, "review.py", "note", slug, "具体痛点开头留人更好"))
        assert n["count"] == 1 and not n["ready"]
        pr = jout(cmd(d, "ledger.py", "promote", n["id"]))
        assert pr.get("refused") is True, "一条证据必须被拒绝升级"
        for i in range(2):
            slug2 = new_proj(d, "证据%d" % i)
            cmd(d, "review.py", "note", slug2, "具体痛点开头留人更好",
                "--again", n["id"])
        pr = jout(cmd(d, "ledger.py", "promote", n["id"]))
        assert pr.get("promoted") is True, "三条证据应能升级"

        # 钩子回填：没记录就跳过；记录了就写进去
        cmd(d, "hooks.py", "use", "H3", slug, "--platform", "douyin")
        r = jout(cmd(d, "review.py", "fill", slug, "--platform", "douyin",
                     "--play", "12000", "--ret5", "50"))
        filled = r["hooks"].get("filled") or []
        assert filled and filled[0].get("ok"), "有钩子记录时应自动回填：%s" % r["hooks"]
        hook_md = read(d, "assets/hooks.md")
        assert "50%" in hook_md or "50" in hook_md, "钩子表格里应出现回填的留存"
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---------- 套件：质检 ----------

def suite_qc():
    d = workspace()
    try:
        slug = new_proj(d, "质检测试")
        write(d, "projects/%s/04-package.md" % slug, """<!-- 已填写 -->
# 04 · 包装

## 抖音

- **文字标题**（≤20 字）：
  > 换 AI 工具最贵的是重讲业务
- **封面标题**（压屏大字）：
  > 经验不在
  > 工具里
- **开头 3 秒口播**：
  > 你纠结错地方了。

## 小红书

- **笔记标题**（≤20 字）：
  > AI 工具怎么选？先做迁移测试
- **封面标题**：
  > 资产在文件里
  > 不在工具里
""")
        r = jout(cmd(d, "qc.py", "cover", slug))
        rows = {x["item"]: x["status"] for x in r["rows"]}
        # 标题含「最贵」不该误报（只硬拦「最好/最强」这类承诺）
        assert rows["抖音 · 极限词"] == "PASS", "「最贵」不是绝对化承诺，不该 FAIL：%s" % rows
        assert rows["抖音 · 封面字数"] == "PASS"
        assert rows["抖音 · 字体适配"] == "PASS", "两行封面字应通过"
        assert r["fail"] == 0, "这个封面应全过：%s" % r["rows"]

        # 封面字和标题一模一样 → FAIL
        write(d, "projects/%s/04-package.md" % slug, """<!-- 已填写 -->
## 抖音

- **文字标题**（≤20 字）：
  > 同一句话
- **封面标题**：
  > 同一句话
""")
        r = jout(cmd(d, "qc.py", "cover", slug))
        rows = {x["item"]: x["status"] for x in r["rows"]}
        assert rows["抖音 · 封面≠标题"] == "FAIL"
        # 硬极限词 → FAIL
        write(d, "projects/%s/04-package.md" % slug, """<!-- 已填写 -->
## 抖音

- **文字标题**（≤20 字）：
  > 全网最好的 AI 工具
- **封面标题**：
  > 换个角度
""")
        r = jout(cmd(d, "qc.py", "cover", slug))
        rows = {x["item"]: x["status"] for x in r["rows"]}
        assert rows["抖音 · 极限词"] == "FAIL", "「最好」必须 FAIL"

        # 没成片时 video 是 SKIP，不应报错
        r = jout(cmd(d, "qc.py", "video", slug))
        assert r["rows"][0]["status"] == "SKIP"
        # 报告写进了 05-check.md
        assert "## 机器质检" in read(d, "projects/%s/05-check.md" % slug)
        # 有 FAIL 时退出码为 1
        r = cmd(d, "qc.py", "cover", slug)
        assert r.returncode == 1, "有 FAIL 时退出码应为 1"
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---------- 套件：选题池 ----------

def suite_backlog():
    d = workspace()
    try:
        jout(cmd(d, "backlog.py", "add", "想法A", "--type", "B"))
        jout(cmd(d, "backlog.py", "add", "想法B"))
        lst = jout(cmd(d, "backlog.py", "list"))
        assert lst["by_status"]["候选"] == 2
        cmd(d, "backlog.py", "start", "想法A")
        cmd(d, "backlog.py", "kill", "想法B", "--why", "答不了第二问")
        lst = jout(cmd(d, "backlog.py", "list"))
        assert lst["by_status"]["在做"] == 1 and lst["by_status"]["已毙"] == 1
        # 毙掉的不能直接 start
        r = jout(cmd(d, "backlog.py", "start", "想法B"))
        assert "error" in r, "已毙的选题直接 start 应被拒绝"
        # 开项目自动关联同名候选（先有池子文件，才会联动）
        jout(cmd(d, "backlog.py", "add", "开工测试"))
        slug = new_proj(d, "开工测试")
        lst = jout(cmd(d, "backlog.py", "list"))
        row = [r for r in lst["rows"] if r["title"] == "开工测试"][0]
        assert row["status"] == "在做", "开项目应把同名候选转成在做"
        assert row["slug"] == slug, "开项目应回填 slug"
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---------- 套件：自检 ----------

def suite_doctor():
    d = workspace()
    try:
        new_proj(d, "自检测试")
        r = run(d, os.path.join("scripts", "doctor.py"), "--json")
        try:
            data = json.loads(r.stdout)
        except json.JSONDecodeError:
            raise AssertionError("doctor --json 输出不是 JSON：%s" % r.stdout[:300])
        names = {c["name"]: c for c in data["checks"]}
        assert "Python" in names and "ffmpeg" in names and "状态一致" in names
        assert names["状态一致"]["level"] == "ok", "新项目状态应一致"
        # 故意制造漂移，doctor 要报出来，--fix 后恢复
        p = os.path.join(d, "projects", ".vflow.json")
        st = json.loads(read(d, "projects/%s/.vflow.json"
                             % os.listdir(os.path.join(d, "projects"))[0]))
        st["stages"]["01"]["status"] = "done"
        st["stages"]["01"]["manual"] = True
        write(d, "projects/%s/.vflow.json" % st["slug"],
              json.dumps(st, ensure_ascii=False))
        data = json.loads(run(d, os.path.join("scripts", "doctor.py"),
                              "--json").stdout)
        names = {c["name"]: c for c in data["checks"]}
        assert names["状态一致"]["level"] != "ok", \
            "状态漂移时 doctor 应报警"
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---------- 套件：技能契约（定位锁）----------

CONTRACTS = [
    ("vflow", "没有 profile 不能开工", r"不存在就按|先引导使用者把它建起来|引导使用者填"),
    ("vflow", "不自动发布", r"不自动发布"),
    ("vflow", "一条数据不改默认", r"一条数据不改默认"),
    ("vflow", "三个确认点", r"三个确认点"),
    ("vflow-topic", "三问筛查", r"三问"),
    ("vflow-topic", "二创边界", r"similarity\.py"),
    ("vflow-outline", "方法页不超过 4 页", r"方法页不超过 4 页"),
    ("vflow-script", "写前读声音档案", r"voice_profile\.py show"),
    ("vflow-script", "先选结构模板", r"structures\.md"),
    ("vflow-script", "可保存物硬门槛", r"不许进制作"),
    ("vflow-script", "三个钩子变体", r"3 个\*\*不同原型"),
    ("vflow-package", "兑现检查", r"兑现检查"),
    ("vflow-check", "三层检查", r"第三层：AI 味检测"),
    ("vflow-check", "没过不许制作", r"没过检查不许进制作"),
    ("vflow-produce", "旁白锁定", r"旁白锁定"),
    ("vflow-produce", "不替用户点发布", r"不替使用者点发布"),
    ("vflow-review", "48 小时", r"48 小时"),
    ("vflow-review", "三条可比证据", r"三条"),
    ("vflow-review", "不因一条数据改 profile", r"不因为一条数据改"),
    ("vflow-review", "双轨指标", r"深度轨.*收藏率|收藏率.*深度轨"),
    ("vflow-package", "小红书关键词矩阵", r"关键词矩阵"),
    ("vflow-check", "声明台账", r"claims\.py"),
    ("vflow", "默认不自动发布", r"auto 需显式开启|默认.*人工"),
    ("vflow", "脚本先过机器自检", r"script_check\.py"),
]


def suite_contracts():
    missing = []
    for skill, label, pattern in CONTRACTS:
        path = os.path.join(ROOT, "skills", skill, "SKILL.md")
        assert os.path.isfile(path), "技能文件不存在：%s" % path
        text = open(path, encoding="utf-8").read()
        if not re.search(pattern, text):
            missing.append("%s → %s（找不到：%s）" % (skill, label, pattern))
    assert not missing, "技能契约被改坏：\n" + "\n".join(missing)

    # 每个 vflow-* 技能必须有完整的边界四段
    for d in sorted(os.listdir(os.path.join(ROOT, "skills"))):
        if not d.startswith("vflow-"):
            continue
        text = open(os.path.join(ROOT, "skills", d, "SKILL.md"),
                    encoding="utf-8").read()
        for seg in ("**做**", "**不做**", "**单独被调用时**", "**越界信号**"):
            assert seg in text, "%s 缺少边界段落：%s" % (d, seg)

    # 阶段数一致：主控 / AGENTS / README 里都是七阶段
    for f in ("skills/vflow/SKILL.md", "AGENTS.md", "README.md"):
        text = open(os.path.join(ROOT, f), encoding="utf-8").read()
        assert "七阶段" in text, "%s 应写明七阶段" % f

    # 阶段产出文件名一致：skill 里写的产出文件必须和 pipeline 模板对得上
    templates = set(f for f in os.listdir(os.path.join(ROOT, "pipeline"))
                    if f.endswith(".md"))
    expected = {"01-topic.md", "02-outline.md", "03-script.md",
                "04-package.md", "05-check.md", "06-review.md",
                "publish-copy.md"}
    assert expected <= templates, "pipeline 模板缺失：%s" % (expected - templates)

    # 脚本都能编译
    for f in os.listdir(SCRIPTS):
        if not f.endswith(".py"):
            continue
        r = subprocess.run([sys.executable, "-m", "py_compile",
                            os.path.join(SCRIPTS, f)],
                           capture_output=True, text=True)
        assert r.returncode == 0, "%s 编译失败：%s" % (f, r.stderr)
    # 内置模板不含项目专属字段
    for f in templates:
        text = open(os.path.join(ROOT, "pipeline", f), encoding="utf-8").read()
        assert "2026" not in text or "示例" not in text, \
            "模板 %s 里不应有示例日期" % f


# ---------- 套件：口播稿自检 ----------

GOOD_SCRIPT = """<!-- 已填写 -->
# 03 · 口播逐字稿

- **结构模板**：T1 重新定义题
- **核心判断**：选 AI 工具最贵的不是订阅费，是你得把业务重讲一遍
- **可保存物**：一个迁移测试（三个字段：输入 / 步骤 / 输出），第 12 秒出现
- **开放循环**：开头问"为什么换工具像搬一次家"，结尾回答
- **中段 re-hook**：做到第三步会发现，真正难的是把判断标准写下来
- **结尾动作**：今晚挑一件最常干的事，写成三个字段
- **轨道**：发现轨
- **目标时长**：75 秒

## 钩子变体

| # | 原型 | 口播第一句 | 画面第一帧 | 2 秒内能念完 |
|---|---|---|---|---|
| A | H1 | 你纠结的不是选哪个工具 | 两个终端并排 | ✅ |
| B | H11 | 我在两个工具之间来回搬了三次家 | 三次迁移截图 | ✅ |
| C | H12 | 三个字段，让你换工具不用重讲业务 | 三字段清单 | ✅ |

## 逐字稿

**P1 · 钩子（0–4s）**

> 你纠结的不是选哪个工具。
>
> 是换一次，你的业务就得重讲一遍。

**P2 · 共情（4–16s）**

> 每次换工具，你都把业务讲一遍。
>
> 讲给客服，讲给助手，讲给下一个模型。

**P3 · 转折（16–34s）**

> 所以真正贵的不是订阅费。
>
> 是你攒下来的那点东西，带不走。
>
> 我做了个迁移测试，就三个字段：输入、步骤、输出。

**P4 · 方法（34–56s）**

> 第一次写，二十分钟。
>
> 写完你会发现，八个流程里六个能直接搬。
>
> 剩下两个，是只有你能判断的。

**P5 · re-hook（56–66s）**

> 做到这你会发现，真正难的不是搬。
>
> 是你从来没把判断标准写下来过。

**P6 · 收尾（66–78s）**

> 今晚挑一件最常干的事，写成三个字段。
>
> 这份清单存下来，下次换工具直接对着填。
"""


def suite_script():
    d = workspace()
    try:
        slug = new_proj(d, "口播自检")
        write(d, "projects/%s/03-script.md" % slug, GOOD_SCRIPT)
        r = cmd(d, "script_check.py", slug, "--json")
        data = jout(r)
        assert data["fail"] == 0, "好稿不该有 FAIL：%s" % data["rows"]
        rows = {x["item"]: x["status"] for x in data["rows"]}
        assert rows["结构模板"] == "PASS"
        assert rows["开头 2 句"] == "PASS"
        assert rows["钩子变体"] == "PASS"
        assert rows["可保存物"] == "PASS"
        assert r.returncode == 0
        # 报告写回 03-script.md
        assert "## 机器自检" in read(d, "projects/%s/03-script.md" % slug)

        # 慢热开头 → FAIL
        bad = GOOD_SCRIPT.replace(
            "> 你纠结的不是选哪个工具。\n>\n> 是换一次，你的业务就得重讲一遍。",
            "> 大家好，今天我给大家聊聊 AI 工具。")
        write(d, "projects/%s/03-script.md" % slug, bad)
        data = jout(cmd(d, "script_check.py", slug, "--json"))
        rows = {x["item"]: x["status"] for x in data["rows"]}
        assert rows["开头 2 句"] == "FAIL", "慢热开头必须 FAIL：%s" % rows
        assert cmd(d, "script_check.py", slug).returncode == 1

        # 缺可保存物 → FAIL
        bad2 = GOOD_SCRIPT.replace(
            "- **可保存物**：一个迁移测试（三个字段：输入 / 步骤 / 输出），第 12 秒出现",
            "- **可保存物**：")
        assert bad2 != GOOD_SCRIPT, "测试自身：可保存物替换没生效"
        write(d, "projects/%s/03-script.md" % slug, bad2)
        data = jout(cmd(d, "script_check.py", slug, "--json"))
        rows = {x["item"]: x["status"] for x in data["rows"]}
        assert rows["可保存物"] == "FAIL"

        # 结尾求点赞 → WARN
        bad3 = GOOD_SCRIPT.replace(
            "> 这份清单存下来，下次换工具直接对着填。", "> 点个赞，关注我。")
        write(d, "projects/%s/03-script.md" % slug, bad3)
        data = jout(cmd(d, "script_check.py", slug, "--json"))
        rows = {x["item"]: x["status"] for x in data["rows"]}
        assert rows["结尾 CTA"] == "WARN"

        # 机器自检节不算内容变更：定稿后跑一次不该退回 wip
        write(d, "projects/%s/03-script.md" % slug, GOOD_SCRIPT)
        cmd(d, "vflow_state.py", "set", slug, "03", "done")
        cmd(d, "script_check.py", slug, "--json")
        st = jout(cmd(d, "vflow_state.py", "show", slug))
        assert st["stages"]["03"]["status"] == "done", \
            "script_check 追加的自检节不该让定稿退回 wip"
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---------- 套件：声明台账 ----------

def suite_claims():
    d = workspace()
    try:
        slug = new_proj(d, "声明测试")
        write(d, "projects/%s/03-script.md" % slug, """<!-- 已填写 -->
# 03 · 口播逐字稿

## 逐字稿

**P1 · 钩子（0–3s）**

> 它在大模型服务市场的份额是 49.5%。
>
> 日活 1.68 亿。
>
> 行业测算，万播能分到五到十块。
""")
        r = jout(cmd(d, "claims.py", "scan", slug))
        assert r["count"] >= 2, "应扫出至少两处未登记声明：%s" % r
        claims = [u["claim"] for u in r["unregistered"]]
        assert any("49.5" in c for c in claims), claims

        a = jout(cmd(d, "claims.py", "add", "49.5%", "--source",
                     "IDC 2026-06", "--caliber", "大模型服务市场份额",
                     "--slug", slug, "--verified", "2026-10-24"))
        assert a["id"] == "C1" and a["status"] == "已核"
        r = jout(cmd(d, "claims.py", "scan", slug))
        assert all("49.5" not in u["claim"] for u in r["unregistered"])

        # 没写来源 → 待核 + 警告
        b = jout(cmd(d, "claims.py", "add", "日活 1.68 亿", "--slug", slug))
        assert b["status"] == "待核" and "warn" in b
        # 重复登记被拒
        dup = jout(cmd(d, "claims.py", "add", "日活 1.68 亿", "--slug", slug))
        assert "error" in dup

        lst = jout(cmd(d, "claims.py", "list", "--slug", slug))
        assert lst["total"] == 2

        # 逾期未核（C2 还没核过）
        stale = jout(cmd(d, "claims.py", "stale", "--days", "90"))
        assert any(s["id"] == "C2" for s in stale["stale"]), stale

        v = jout(cmd(d, "claims.py", "verify", "C2"))
        assert v.get("ok") and v["status"] == "已核", v
        stale = jout(cmd(d, "claims.py", "stale", "--days", "90"))
        assert all(s["id"] != "C2" for s in stale["stale"]), "刚核过不该算逾期"

        rep = jout(cmd(d, "claims.py", "report", slug))
        assert "C1" in rep["markdown"] and rep["pending"] == 0, rep
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---------- 套件：发布包与发布队列 ----------

def make_ready_project(d, name="发布包测试"):
    """造一个能过所有门的项目：检查+质检通过、有终版成片、双平台文案齐全。"""
    slug = new_proj(d, name)
    proj = "projects/%s" % slug
    write(d, proj + "/04-package.md", """<!-- 已填写 -->
# 04 · 包装

## 抖音

- **文字标题**（≤20 字）：
  > 换工具最贵的是重讲业务
- **封面标题**（压屏大字）：
  > 经验不在
  > 工具里
- **开头 3 秒口播**：
  > 你纠结错地方了。
- **话题标签**（3–5 个）：
  > #AI工具 #AI落地 #企业效率

## 小红书

- **笔记标题**（≤20 字）：
  > AI 工具怎么选 先做迁移测试
- **封面标题**：
  > 资产在文件里
- **标签**（5–10 个）：
  > #AI工具 #AI落地 #企业效率 #AI工作流 #ClaudeCode

## 小红书关键词矩阵（必做）

| 维度 | 关键词 | 放在哪 |
|---|---|---|
| 核心词（1–2） | AI 工具 | 标题前 20 字 |
| 长尾词（2–3） | AI 工具怎么选 | 标题后半 |
| 问题词（1–2） | 换工具要重讲业务吗 | 正文首段 |
| 场景词（2–3） | 写周报 | 正文例子 |

## AI 生成声明

- **声明**：文稿 AI 辅助生成，画面为人工录屏
""")
    write(d, proj + "/05-check.md",
          "<!-- 已填写 -->\n# 05 · 发布前检查\n\n- **结论**：可发布\n\n五层全过。\n")
    write(d, proj + "/publish-copy.md", """<!-- 已填写 -->
# 发布文案

## 抖音

**标题**

换工具最贵的是重讲业务

**正文**

换 AI 工具，最贵的一次不是订阅费，是你把业务重讲一遍。

## 小红书

**标题**

AI 工具怎么选 先做迁移测试

**正文**

先说结论：选工具之前，先做一次迁移测试。三个字段，二十分钟。
""")
    os.makedirs(os.path.join(d, proj, "output", "qc"), exist_ok=True)
    open(os.path.join(d, proj, "output", "final.mp4"), "w").close()
    try:
        from PIL import Image
        for n in ("cover-douyin.png", "cover-xhs.png"):
            Image.new("RGB", (1080, 1920), (30, 30, 30)).save(
                os.path.join(d, proj, "output", "qc", n))
    except ImportError:
        pass
    cmd(d, "vflow_state.py", "final", slug, "--video", "output/final.mp4")
    cmd(d, "vflow_state.py", "set", slug, "05", "done")
    cmd(d, "qc.py", "package", slug)
    cmd(d, "qc.py", "cover", slug)
    return slug


def suite_package():
    d = workspace()
    try:
        # 没准备好：拒绝出包
        slug0 = new_proj(d, "没准备的")
        r = cmd(d, "package.py", "build", slug0)
        data = jout(r)
        assert data.get("blocked") is True and r.returncode == 1
        assert any("质检" in b or "检查" in b or "制作" in b
                   for b in data["blockers"]), data["blockers"]

        slug = make_ready_project(d)
        r = cmd(d, "package.py", "build", slug, "--zip")
        data = jout(r)
        assert r.returncode == 0 and data.get("ok"), data
        pdir = os.path.join(d, "projects", slug, "publish")
        for f in ("video.mp4", "copy-douyin.md", "copy-xhs.md",
                  "checklist.md", "manifest.json"):
            assert os.path.isfile(os.path.join(pdir, f)), "缺 " + f
        assert any(f.endswith(".zip") for f in os.listdir(pdir))
        man = jout(cmd(d, "package.py", "show", slug))
        assert man["platforms"]["douyin"]["title"]
        assert man["platforms"]["xhs"]["matrix"], "小红书关键词矩阵应进 manifest"
        assert "AI 辅助" in man["platforms"]["douyin"]["ai_decl"]

        # 发布队列：默认人工
        q = jout(cmd(d, "publish.py", "queue", slug, "--platform", "douyin"))
        assert q["mode"] == "manual"
        # auto 请求被退回（allow_auto 没开）
        q2 = jout(cmd(d, "publish.py", "queue", slug, "--platform", "douyin",
                      "--mode", "auto"))
        assert q2["mode"] == "manual" and q2["fallback"], q2
        run_manual = jout(cmd(d, "publish.py", "run", slug, "--platform",
                              "douyin"))
        assert run_manual["mode"] == "manual"
        assert "publish" in run_manual["package"]
        # done → 自动登记发布
        dn = jout(cmd(d, "publish.py", "done", slug, "--platform", "douyin"))
        st = jout(cmd(d, "vflow_state.py", "show", slug))
        assert st["published"].get("douyin"), "done 应自动登记发布"
        assert st["review"]["pending"] is True
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---------- 套件：内容日历与系列 ----------

def suite_calendar():
    d = workspace()
    try:
        s = jout(cmd(d, "content_calendar.py", "series", "add", "选型系列",
                     "--goal", "3", "--start", "2026-11-02"))
        assert s["id"] == "S1"
        jout(cmd(d, "content_calendar.py", "plan", "第一条", "--date",
                 "2026-11-02", "--platform", "douyin", "--series", "S1"))
        jout(cmd(d, "content_calendar.py", "plan", "第二条", "--date",
                 "2026-11-06", "--platform", "xhs", "--series", "S1"))
        lst = jout(cmd(d, "content_calendar.py", "list"))
        assert lst["total"] == 2 and lst["by_status"]["待做"] == 2
        # 轨道由平台推
        rows = {p["title"]: p for p in lst["plans"]}
        assert rows["第一条"]["track"] == "发现轨"
        assert rows["第二条"]["track"] == "深度轨"
        # 系列进度
        chk = jout(cmd(d, "content_calendar.py", "check"))
        assert chk["series"][0]["planned"] == 2 and not chk["series"][0]["ok"]
        # 同平台同日冲突
        jout(cmd(d, "content_calendar.py", "plan", "撞车", "--date",
                 "2026-11-02", "--platform", "douyin", "--series", "S1"))
        chk = jout(cmd(d, "content_calendar.py", "check"))
        assert chk["issues"], "同平台同日应报冲突"
        # 开项目 → 回填 slug
        st = jout(cmd(d, "content_calendar.py", "start", "第一条"))
        assert st.get("slug"), st
        lst = jout(cmd(d, "content_calendar.py", "list"))
        row = [p for p in lst["plans"] if p["title"] == "第一条"][0]
        assert row["status"] == "已排" and row["slug"] == st["slug"]
        # done
        jout(cmd(d, "content_calendar.py", "done", "第一条",
                 "--slug", st["slug"]))
        lst = jout(cmd(d, "content_calendar.py", "list"))
        row = [p for p in lst["plans"] if p["title"] == "第一条"][0]
        assert row["status"] == "已发"
        # 系列不存在
        bad = jout(cmd(d, "content_calendar.py", "plan", "x", "--date",
                       "2026-11-09", "--platform", "xhs", "--series", "S9"))
        assert "error" in bad
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---------- 套件：版本库 ----------

def suite_version():
    d = workspace()
    try:
        # workspace 里复制了根目录的 versions 和 VERSION
        r = run(d, os.path.join("scripts", "version.py"), "check")
        data = jout(r)
        assert data["current"] == "1.0.0"
        # 技能源文件有 version，但没有复制进 temp 的 skills 目录；直接检查源仓库
        r = run(ROOT, os.path.join("scripts", "version.py"), "check")
        data = jout(r)
        assert data["ok"], "版本校验失败：%s" % data["problems"]
        assert "1.0.0" in [v["version"] for v in
                           jout(run(ROOT, os.path.join("scripts", "version.py"),
                                    "list"))["versions"]]
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---------- 套件：技能契约（定位锁）----------

SUITES = {
    "state": suite_state,
    "review": suite_review,
    "qc": suite_qc,
    "backlog": suite_backlog,
    "doctor": suite_doctor,
    "script": suite_script,
    "claims": suite_claims,
    "package": suite_package,
    "calendar": suite_calendar,
    "version": suite_version,
    "contracts": suite_contracts,
}


def main():
    ap = argparse.ArgumentParser(description="Vflow 回归测试")
    ap.add_argument("--only", choices=list(SUITES))
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    names = [args.only] if args.only else list(SUITES)
    print("Vflow 回归测试 · %d 个套件" % len(names))
    for n in names:
        print("\n[%s]" % n)
        test(n, SUITES[n], args.verbose)
    print("\n%s" % ("全部通过" if not FAILS else
                    "失败 %d 项：%s" % (len(FAILS), "、".join(FAILS))))
    sys.exit(0 if not FAILS else 1)


if __name__ == "__main__":
    main()
