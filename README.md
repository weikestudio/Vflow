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
| `projects/` | 每条内容一个目录 |
| `assets/` | 跨项目复用素材：字体、BGM、封面模板 |
| `skills/` | Vflow 技能集合源码 |
| `scripts/` | 开项脚本、仪表盘 |

## 第一步：改 profile.md

`profile.md` 是人格底座，所有选题和文案都从它长出来。空着用 `skills/_shared/profile-template.md` 填一份。当前目录里已有一份填好的实例，按自己情况改。

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
PY=/Users/v1/.workbuddy/binaries/python/envs/default/bin/python
SS=~/Vflow/skills/vflow-produce/scripts
bash $SS/build_video.sh ~/Vflow/projects/<slug>/deck --tts edge --voice zh-CN-YunxiNeural
```

竖版模板在 `assets/deck-template-vertical.html`，示例成片见 `projects/20261016-示例-竖版/output/deck.mp4`。

必需环境：`ffmpeg` / `ffprobe`、Playwright + Chromium、Pillow。TTS 可选 `say`（内置）/ `edge-tts`（免费，中文好）/ Voicebox（克隆自己声音）。

## 风险提示

`skills/all-in-one` 是第三方逆向接口工具，涉及平台 cookie，有合规、账号安全和 ToS 风险。**只做公开内容调研，不要拿它批量发布或刷量。** 不装不影响主流程。
