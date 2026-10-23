#!/usr/bin/env python3
"""首次使用引导：把 profile.md 建起来，把目录备齐。

用法：
    python3 scripts/setup.py                 交互式引导（问答 → 生成 profile.md）
    python3 scripts/setup.py --check         只看状态，不改任何东西（输出 JSON）
    python3 scripts/setup.py --reset         清掉引导标记，重新走一遍
    python3 scripts/setup.py --non-interactive   非交互：只建目录和骨架，不问答

Agent 用的时候不用这个脚本填空——它读 `skills/_shared/profile-template.md`
直接跟使用者对话填更自然。这个脚本是给"想自己在终端里填"的人用的。

零依赖。
"""
import argparse
import json
import os
import sys
from datetime import datetime

ROOT = os.path.abspath(
    os.environ.get("VFLOW_HOME") or os.path.expanduser("~/Vflow")
)
PROFILE = os.path.join(ROOT, "profile.md")
TEMPLATE = os.path.join(ROOT, "skills", "_shared", "profile-template.md")
SETUP_JSON = os.path.join(ROOT, ".vflow-setup.json")
SAMPLES = os.path.join(ROOT, "assets", "voice-samples")
CARD = os.path.join(ROOT, "assets", "voice-card.json")

QUESTIONS = [
    ("name", "你叫什么 / 账号名叫什么",
     "例：威克，账号「小V智谈」"),
    ("direction", "你在做什么方向（一句话）",
     "例：AI 工作室，方向是 AI Skill 服务"),
    ("path", "你打算怎么走到变现（一句话，没有就写「还在找」）",
     "例：开源仓库建可信度 → 自媒体传播 → 企业付费服务"),
    ("audience", "内容主要做给谁看",
     "越具体越好。例：个体创业者、小团队负责人、想把 AI 用进业务的人"),
    ("stuck", "他们的卡点是什么（他们卡在哪一步）",
     "例：试过 ChatGPT，发现它只能聊天，干不了具体的活"),
    ("tone", "你想要什么语气（可以自己写）",
     "例：说人话，先给结论，可以吐槽，不许喊口号"),
    ("platforms", "主平台（抖音 / 小红书 / 两端）", "两端"),
    ("style", "出镜方式（露脸 / 不露脸 / 按选题类型选）", "按选题类型选"),
]


def read_text(p):
    try:
        with open(p, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def profile_filled():
    """profile.md 存在且真填了（不是空模板）。"""
    t = read_text(PROFILE)
    if not t.strip():
        return False
    if "vflow-template" in t:
        return False
    # 填了的话至少有几个字段不是空的
    return len(t.strip()) > 400


def count_samples():
    if not os.path.isdir(SAMPLES):
        return 0
    return len([f for f in os.listdir(SAMPLES)
                if f.endswith((".md", ".txt"))
                and not f.startswith(("."))
                and not f.lower().startswith("readme")])


def count_projects():
    p = os.path.join(ROOT, "projects")
    if not os.path.isdir(p):
        return 0
    return len([d for d in os.listdir(p)
                if os.path.isdir(os.path.join(p, d)) and not d.startswith(".")])


def status():
    steps = {
        "profile": {
            "done": profile_filled(),
            "title": "填账号设定",
            "why": "所有选题和文案都从这份设定长出来。不填的话 AI 只能凭空猜你是谁。",
            "how": "打开 profile.md 按里面的字段填，或照 skills/_shared/profile-template.md 从空白开始",
            "action": {"label": "打开 profile.md", "open": "profile.md"},
        },
        "voice": {
            "done": count_samples() >= 2 and os.path.isfile(CARD),
            "title": "放 2–3 篇你自己的成稿",
            "why": "系统会从你的稿子里提取文风数字（平均句长、语气标记、你从不用的词）。"
                   "写稿时照数字对齐才像你——照规则写只像 AI。",
            "how": "把自己写过的 2–3 篇稿子放进 assets/voice-samples/，"
                   "然后跑 python3 scripts/voice_profile.py build",
            "action": {"label": "打开样本目录", "open": "assets/voice-samples"},
        },
        "firstProject": {
            "done": count_projects() > 0,
            "title": "开第一条内容",
            "why": "流水线是围着项目跑的。开了项目才有地方落选题卡、剧本、成片。",
            "how": "跑 bash scripts/new_project.sh \"选题短名\"，"
                   "或者直接在对话里说「我要做一条讲 XX 的视频」",
            "action": {"label": "新建项目", "newProject": True},
        },
    }
    done = all(s["done"] for s in steps.values())
    return {
        "done": done,
        "profileExists": profile_filled(),
        "voiceSamples": count_samples(),
        "voiceCardExists": os.path.isfile(CARD),
        "projectCount": count_projects(),
        "steps": steps,
    }


def ensure_dirs():
    for d in (os.path.join(ROOT, "assets"),
              os.path.join(ROOT, "assets", "voice-samples"),
              os.path.join(ROOT, "ledger"),
              os.path.join(ROOT, "projects")):
        os.makedirs(d, exist_ok=True)
    # 台账文件不在就建一个
    ev = os.path.join(ROOT, "ledger", "evidence.md")
    if not os.path.isfile(ev):
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        try:
            import ledger
            ledger.ensure_file()
        except Exception:
            pass
    # 样本目录放个说明，免得空目录让人不知道放什么
    readme = os.path.join(SAMPLES, "README.md")
    if not os.path.isfile(readme):
        with open(readme, "w", encoding="utf-8") as fh:
            fh.write("# 声音样本\n\n"
                     "放 2–3 篇**你自己写过**的成稿进来（口播稿、公众号正文都行，"
                     ".md 或 .txt）。\n\n"
                     "AI 生成的不算——要的是你的文风，不是模型的文风。\n\n"
                     "放完跑：\n\n"
                     "```bash\npython3 scripts/voice_profile.py build\n```\n")


def generate_profile(answers):
    today = datetime.now().strftime("%Y-%m-%d")
    return f"""# profile.md · 账号设定

> 流水线的人格底座。每次开工前 AI 读这个文件，所有选题、剧本、文案都从这里长出来。
> 建立于：{today}

## 0. 当前阶段

- **阶段**：找方向期。目标是建立可信度，不是涨粉，也不是变现
- 内容按顺序服务三件事：① 证明我会做 ② 让人记住我 ③ 让潜在客户找得到我
- 推论：宁可少发，不发没有信息增量的内容

## 1. 我是谁

- {answers.get('name', '（待填）')}
- 在做：{answers.get('direction', '（待填）')}
- 路径：{answers.get('path', '（待填）')}
- **出镜方式**：{answers.get('style', '按选题类型选')}

## 2. 我做给谁看

**主受众**：{answers.get('audience', '（待填）')}

- 不是 AI 从业者，是有自己的业务、想让 AI 真的干上活的人
- 卡点：{answers.get('stuck', '（待填）')}

**不服务**：想靠 AI 一夜暴富的人、纯 AI 工具测评流量党

## 3. 内容主线

围绕一句话：**把 AI 变成真的能干活的东西**

| 类型 | 干什么 | 配比 |
|---|---|---|
| A 演示型 | 展示 AI 真的干完了一件事 | 40% |
| B 拆解型 | 拆一个方法 / 概念 / 工具 | 40% |
| C 实录型 | 我在做什么、踩了什么坑 | 20% |

A 拉流量，B 立专业，C 建信任。

**选题筛选三问**（有一条不满足就不做）：

1. 这条能让观众拿走一个具体动作吗？
2. 这条能证明**我会做**，而不只是会说吗？
3. 这条三个月后还有人搜吗？

## 4. 语气

{answers.get('tone', '说人话。先给结论，再给理由。')}

- 禁用词：赋能、抓手、底层逻辑、闭环、颗粒度、对齐
- 可以吐槽，可以承认翻车，但要具体到哪一步翻的
- 不喊口号，不贩卖焦虑，不吹"AI 取代你"
- 标准：**像一个干过这事儿的朋友在讲，不像老师在上课**

## 5. 平台策略

**主平台**：{answers.get('platforms', '两端')}

- 抖音：走流量。前 3 秒是生死线，节奏要快
- 小红书：走搜索长尾。标题铺搜索词，正文可以写细

同一条内容两端分发时**必须改文案**，不能一套标题贴两边。

## 6. 红线

- 不承诺收益，不教"用 AI 月入 X 万"
- 不碰医疗功效、投资建议、时政
- 不贬低具体同行
- 推荐工具先说免费边界（限什么、哪部分要钱），再推荐
- 不管露不露脸，每条都要有"我"的判断在里面

## 7. 积累区（跑起来之后往这儿填）

发布 5 条以上后，把真实规律写回这里。**只有攒够三条可比证据才准写进来**——
规则见 `ledger/evidence.md`。

- 哪类选题数据好：
- 什么开头留人：
- 什么长度完播高：
- 平台对什么敏感：
- 已验证的公式：
"""


def ask_interactive():
    print("Vflow 首次使用引导")
    print("=" * 46)
    print("问 8 个问题，生成你的 profile.md。")
    print("不想答的直接回车跳过，之后可以自己打开文件改。\n")
    answers = {}
    for key, question, hint in QUESTIONS:
        print("· %s" % question)
        print("  （%s）" % hint)
        try:
            v = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            v = ""
        answers[key] = v
        print()
    return answers


def main():
    ap = argparse.ArgumentParser(description="Vflow 首次使用引导")
    ap.add_argument("--check", action="store_true", help="只看状态")
    ap.add_argument("--reset", action="store_true", help="清掉引导标记")
    ap.add_argument("--non-interactive", action="store_true",
                    help="只建目录骨架，不问答")
    args = ap.parse_args()

    if args.check:
        json.dump(status(), sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return

    if args.reset:
        if os.path.isfile(SETUP_JSON):
            os.remove(SETUP_JSON)
        print("已清掉引导标记，重跑 python3 scripts/setup.py 再来一遍")
        return

    ensure_dirs()

    if args.non_interactive:
        json.dump({"ok": True, "dirs": True, "status": status()},
                  sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return

    if profile_filled():
        print("profile.md 已经有了，不用重填。")
        print("想重写就删掉它再跑，或用 --reset 清标记。\n")
        st = status()
        for k, s in st["steps"].items():
            print("  [%s] %s" % ("x" if s["done"] else " ", s["title"]))
        return

    answers = ask_interactive()
    with open(PROFILE, "w", encoding="utf-8") as fh:
        fh.write(generate_profile(answers))
    with open(SETUP_JSON, "w", encoding="utf-8") as fh:
        json.dump({"setup_version": 1,
                   "profile_created": datetime.now().isoformat()},
                  fh, ensure_ascii=False, indent=2)

    print("profile.md 已生成：%s" % PROFILE)
    print("\n接下来两步：")
    print("  1. 把 2–3 篇你自己的成稿放进 assets/voice-samples/，"
          "跑 python3 scripts/voice_profile.py build")
    print("  2. 开第一条：bash scripts/new_project.sh \"选题短名\"")
    print("\n想在浏览器里看进度：python3 scripts/workbench.py")


if __name__ == "__main__":
    main()
