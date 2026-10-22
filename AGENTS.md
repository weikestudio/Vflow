# Vflow 内容创作流水线

这个目录是 Vflow 的数据根目录。任何读 AGENTS.md 的 Agent（豆包工作模式、Codex、Claude Code 等）进来后按下面的规则干活。

## 先读什么

1. `profile.md` —— 账号设定：人设、受众、主线、语气、红线。所有选题和文案从它长出来。不存在就按 `skills/_shared/profile-template.md` 引导使用者填一份。
2. `WORKFLOW.md` —— 全链路 SOP 与命令速查。

## 七阶段

| 阶段 | 产出文件 | 规则来源 |
|---|---|---|
| 1 选题 | `projects/<slug>/01-topic.md` | `skills/vflow-topic/SKILL.md` |
| 2 结构 | `projects/<slug>/02-outline.md` | `skills/vflow-outline/SKILL.md` |
| 3 剧本 | `projects/<slug>/03-script.md` | `skills/vflow-script/SKILL.md` |
| 4 包装 | `projects/<slug>/04-package.md` | `skills/vflow-package/SKILL.md` |
| 5 检查 | `projects/<slug>/05-check.md` | `skills/vflow-check/SKILL.md` |
| 6 制作 | `projects/<slug>/output/` + `publish-copy.md` | `skills/vflow-produce/SKILL.md` |
| 7 复盘 | `projects/<slug>/06-review.md` | `skills/vflow-review/SKILL.md` |

判断不了当前阶段时，看 `projects/<slug>/` 里已有哪些文件——缺哪一步就从哪一步开始。

## 铁律

1. 每步产出必须落盘，不要只在对话里说
2. 不要跳阶段。上一阶段的产出文件不存在，先补上
3. 三个确认点必须停：选题卡、结构框架、成片交付
4. 检查没过不许进制作
5. 抖音和小红书的文案必须分开写
6. 不贩卖焦虑

## 目录约定

- 数据根目录：默认 `~/Vflow/`，可用环境变量 `VFLOW_HOME` 覆盖
- slug 规则：`YYYYMMDD-中文短名`
- 开新项目：`bash ~/Vflow/scripts/new_project.sh "选题短名"`

## 技能安装

不支持技能目录的 Agent，直接读对应阶段的 `SKILL.md` 即可，内容自包含。

支持技能目录的，跑 `bash ~/Vflow/skills/install.sh`。
