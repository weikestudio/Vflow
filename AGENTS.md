# Vflow 内容创作流水线

这个目录是 Vflow 的数据根目录。任何读 AGENTS.md 的 Agent（豆包工作模式、Codex、Claude Code 等）进来后按下面的规则干活。

## 先读什么

1. `profile.md` —— 账号设定：人设、受众、主线、语气、红线。所有选题和文案从它长出来。不存在就按 `skills/_shared/profile-template.md` 引导使用者填一份。
2. `docs/content-strategy.md` —— 北极星指标（双轨）、平台角色、配比节奏、可保存物门槛、关键词矩阵。
3. `WORKFLOW.md` —— 全链路 SOP 与命令速查。
4. `assets/structures.md` —— 六个口播结构模板。写稿前先选模板。

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

判断不了当前阶段时，先读 `projects/<slug>/.vflow.json` 的 `current` 字段——它是唯一真源，
别靠猜文件在不在。状态是 empty / wip / done 三态：写了没定稿是 wip，定稿后又被改会退回 wip。

## 铁律

1. 每步产出必须落盘，不要只在对话里说
2. 不要跳阶段。上一阶段的产出文件不存在，先补上
3. 三个确认点必须停：选题卡、结构框架、成片交付
4. 检查没过不许进制作；检查包含封面和成片的机器质检（`scripts/qc.py`）
5. 抖音和小红书的文案必须分开写
6. 不贩卖焦虑
7. **默认不自动发布。** manual 只出包；assisted 预填不代点；auto 需 `allow_auto` + Playwright + 质检全过 + 显式确认。发布后用 `scripts/publish.py done` 登记，**48 小时内必须复盘**
8. 一条数据不改默认。观察先进 `scripts/ledger.py`，三条可比证据才准升级
9. **B 拆解型没有可保存物不许进制作**（判断标准 / 对照表 / 决策树）；A 演示型要步骤或参数
10. **对外数字要登记来源和口径**（`scripts/claims.py`），没核过的事实不许进成片
11. **AI 生成内容必须声明**（文稿 / 画面 / 配音哪部分用了 AI）

## 目录约定

- 数据根目录：默认 `~/Vflow/`，可用环境变量 `VFLOW_HOME` 覆盖
- slug 规则：`YYYYMMDD-中文短名`
- 开新项目：`bash ~/Vflow/scripts/new_project.sh "选题短名"`（会自动建 `.vflow.json`，并把选题池同名候选转成「在做」）
- 选题池：`backlog.md`，用 `python3 scripts/backlog.py list`
- 环境自检：`python3 scripts/doctor.py`（依赖 / 字体 / 状态 / 技能死链）
- 改完脚本或技能：`bash tests/run_regression.sh`（11 个套件，含技能契约定位锁）
- 改技能必须升 `VERSION` 和 `skills/*/SKILL.md` 的 `version`，跑 `scripts/version.py check`
- 版本记录写进 `versions/vX.Y.Z.md`

## 技能安装

不支持技能目录的 Agent，直接读对应阶段的 `SKILL.md` 即可，内容自包含。

支持技能目录的，跑 `bash ~/Vflow/skills/install.sh`。
