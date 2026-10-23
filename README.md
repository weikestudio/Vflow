# Vflow

中文内容创作流水线。从选题到复盘，一条龙，全程有 AI 接手。

自带完整方法论，**不依赖任何外部技能包**——所有阶段能力都是 Vflow 自己的。

## 怎么用

在任意对话里说人话，AI 会自动加载 `vflow` 技能并判断你在哪一步：

- 「我想做一条讲 AI Skill 是什么的视频」→ 从选题开始
- 「帮我写这条的口播稿」→ 进剧本阶段
- 「给这条起个标题」→ 进包装阶段
- 「发布前帮我检查一下」→ 进检查阶段
- 「把它做成视频」→ 进制作阶段
- 「看看上周那条数据」→ 进复盘阶段

也可以自己动手开项目：

```bash
bash ~/Vflow/scripts/new_project.sh "选题短名"
```

## 七阶段

```
想法 → 选题 → 结构 → 剧本 → 包装 → 检查 → 制作 → 复盘
              ⏸      ⏸               ⛔      ⏸
```

| 阶段 | 产出 | 技能 |
|---|---|---|
| 1 选题 | `01-topic.md` | `vflow-topic` |
| 2 结构 | `02-outline.md` | `vflow-outline` |
| 3 剧本 | `03-script.md` | `vflow-script` |
| 4 包装 | `04-package.md` | `vflow-package` |
| 5 检查 | `05-check.md` | `vflow-check` |
| 6 制作 | `output/` + `publish-copy.md` | `vflow-produce` |
| 7 复盘 | `06-review.md` | `vflow-review` |

三个必须停的确认点：选题卡、结构框架、成片交付。检查没过不许进制作。

## 目录

| 文件 | 是什么 |
|---|---|
| `profile.md` | 账号设定：人设、受众、主线、语气、红线。**先改这个** |
| `WORKFLOW.md` | 全链路 SOP、命令速查 |
| `pipeline/` | 各阶段作业模板 |
| `projects/<slug>/.vflow.json` | 单个项目的状态真源：阶段、版本、最终版指针 |
| `assets/` | 跨项目资产：风格卡、钩子库、敏感词表、字体、BGM |
| `ledger/` | 证据台账：观察攒够三条才准改成默认 |
| `skills/` | Vflow 技能集合源码 |
| `scripts/` | 开项、状态机、工作台、各类自检脚本 |

## 资产层：会越用越值钱的部分

这几样不是文档，是有结构的资产，每做一条内容都在给它们加数据：

| 资产 | 干什么 |
|---|---|
| **声音档案** | 从你自己写过的 2–3 篇成稿里提取文风数字（平均句长、语气标记频率、你从不用词）。写稿前读它，写完跑 `compare` 看有没有跑偏——**照数字写才像你，照规则写像 AI** |
| **钩子库** | 九类开头钩子，用了就记、复盘回填数据。攒够之后 `best` 会告诉你哪类对你真的有效 |
| **敏感词表** | 四层分级（红线 / 广告法 / 平台敏感 / 自己踩过的），发布前机器先扫一遍，模型判断兜底 |
| **证据台账** | 观察先记候选，**三条可比证据才准升级为默认**，不够会被直接拒绝。防的是"一条爆了就改方法、下一条照抄就扑了" |

```bash
PY=python3
cd ~/Vflow

$PY scripts/voice_profile.py build && $PY scripts/voice_profile.py compare projects/<slug>/03-script.md
$PY scripts/risk_scan.py projects/<slug>/
$PY scripts/similarity.py <对标原稿> <你的稿子>
$PY scripts/hooks.py best
$PY scripts/ledger.py list
$PY scripts/vflow_state.py show <slug>
```

## 第一次用

两种方式，任选：

**跟 AI 说一句**（推荐）——它发现没有 `profile.md` 会自动引导你走三步，一次问一个问题：

> 「我第一次用，帮我建起来」

**自己在终端填**：

```bash
python3 ~/Vflow/scripts/setup.py           # 问 8 个问题，生成 profile.md
python3 ~/Vflow/scripts/setup.py --check   # 随时看三步进度
```

三步是：

1. **填账号设定** → 生成 `profile.md`。你是谁、给谁看、什么语气、红线在哪
2. **放 2–3 篇你自己的成稿** → 进 `assets/voice-samples/`，跑 `voice_profile.py build` 生成风格卡
3. **开第一条内容** → `bash scripts/new_project.sh "选题短名"`

第 2 步最容易想跳过，**别跳**。没有样本，写出来的稿子就没有"像不像你"的判据，只能靠规则——而规则写出来像 AI。

`profile.md` 是人格底座，所有选题和文案都从它长出来。想从空白重写就用 `skills/_shared/profile-template.md`。开工作台 `python3 scripts/workbench.py`，引导卡会显示这三步的完成状态。

## 可视化工作台

```bash
python3 ~/Vflow/scripts/workbench.py          # 默认 8765 端口，自动开浏览器
VFLOW_PORT=9000 python3 ~/Vflow/scripts/workbench.py   # 换端口
```

零依赖（只用 Python 标准库），只监听 127.0.0.1。界面是深色剪辑软件风格：

- **左栏项目库**：搜索、进度条、当前阶段
- **中间预览区**：有成片直接播，下面一排 tab 切七个阶段的产出原文
- **底部时间线**：七阶段轨道，点哪段跳哪段，状态用颜色区分
- **右侧属性面板**：阶段信息、标记完成、归档版本、打开目录
- **资产面板**：钩子库（按你的数据排序）、敏感词表、证据台账、风格卡

项目状态读的是 `projects/<slug>/.vflow.json`，不靠猜文件在不在。

## 安装到其他 Agent

```bash
bash ~/Vflow/skills/install.sh            # 装进所有已存在的宿主目录
bash ~/Vflow/skills/install.sh --list     # 看有哪些目标
bash ~/Vflow/skills/install.sh all        # 强制安装到所有已知目录
bash ~/Vflow/skills/install.sh --link claude   # 用软链而不是复制
```

覆盖：WorkBuddy · Claude Code · Codex · 豆包 · 豆包工作 · Gemini · 通用 `~/.agents/skills`。

数据目录默认 `~/Vflow/`，可用环境变量 `VFLOW_HOME` 覆盖。

## 成片生成

路线 A（默认，不露脸）：HTML 幻灯片 → TTS → 字幕 → Playwright 录屏 → ffmpeg 合成。

**竖版 1080×1920（抖音 / 小红书）**
```bash
bash ~/Vflow/scripts/make_vertical.sh ~/Vflow/projects/<slug>/deck
```

**通用**
```bash
PY=python3
SS=~/Vflow/skills/vflow-produce/scripts
bash $SS/build_video.sh ~/Vflow/projects/<slug>/deck --tts edge --voice zh-CN-YunxiNeural
```

竖版模板在 `assets/deck-template-vertical.html`。示例成片不随仓库分发（`projects/` 是你的私人目录），你自己跑完一条会生成在 `projects/<slug>/output/` 里。

必需环境：`ffmpeg` / `ffprobe`、Playwright + Chromium、Pillow。TTS 可选 `say`（内置）/ `edge-tts`（免费，中文好）/ Voicebox（克隆自己声音）。

## 风险提示

`skills/all-in-one` 是第三方逆向接口工具，涉及平台 cookie，有合规、账号安全和 ToS 风险。**只做公开内容调研，不要拿它批量发布或刷量。** 不装不影响主流程。
