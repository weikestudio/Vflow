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
检查阶段包含**封面和成片的机器质检**（`qc.py`），制作之后必须**登记发布**，
48 小时后项目会出现在「待复盘」里——不填数据，这条就不算完。

## 目录

| 文件 | 是什么 |
|---|---|
| `profile.md` | 账号设定：人设、受众、主线、语气、红线。**先改这个** |
| `WORKFLOW.md` | 全链路 SOP、命令速查 |
| `pipeline/` | 各阶段作业模板 |
| `VERSION` / `versions/` | 版本库：每个版本改了什么、为什么、影响面 |
| `projects/<slug>/.vflow.json` | 单个项目的状态真源：阶段、版本、最终版指针 |
| `assets/` | 跨项目资产：风格卡、钩子库、敏感词表、字体、BGM |
| `backlog.md` | 选题池：候选 / 在做 / 已发 / 已毙（毙掉必须写原因） |
| `calendar.md` | 内容日历：系列与排期 |
| `claims.md` | 声明-证据台账：每个对外数字的来源、口径、核验日期 |
| `docs/content-strategy.md` | 内容策略：双轨北极星、平台角色、配比、关键词矩阵 |
| `ledger/` | 证据台账：观察攒够三条才准改成默认 |
| `skills/` | Vflow 技能集合源码 |
| `scripts/` | 开项、状态机、复盘、质检、自检、工作台 |
| `tests/` | 回归测试：改脚本或改技能后跑 `bash tests/run_regression.sh` |

## 资产层：会越用越值钱的部分

这几样不是文档，是有结构的资产，每做一条内容都在给它们加数据：

| 资产 | 干什么 |
|---|---|
| **声音档案** | 从你自己写过的 2–3 篇成稿里提取文风数字（平均句长、语气标记频率、你从不用词）。写稿前读它，写完跑 `compare` 看有没有跑偏——**照数字写才像你，照规则写像 AI** |
| **钩子库** | 九类开头钩子，用了就记、复盘回填数据。攒够之后 `best` 会告诉你哪类对你真的有效 |
| **敏感词表** | 四层分级（红线 / 广告法 / 平台敏感 / 自己踩过的），发布前机器先扫一遍，模型判断兜底 |
| **证据台账** | 观察先记候选，**三条可比证据才准升级为默认**，不够会被直接拒绝。防的是"一条爆了就改方法、下一条照抄就扑了" |
| **选题池** | 想法先记候选，**毙掉要写清原因**。开工前先看池子，不从空白页开始；30 天没动的会被 `review` 点名 |
| **结构库** | 六个口播结构模板（T1–T6），每个带节拍和"最常见的死法"。写稿前先选模板，不临场发明 |
| **钩子库（12 类）** | 除原来 9 类，新增 H1 重新定义题、H10 结果先行、H11 代价坦白。按轨道回填 5 秒留存和收藏率 |
| **声明台账** | 每条内容里的数字/功能/结论，都要能说清来源、口径、什么时候核过。没核过的事实不许进成片 |
| **内容日历** | 系列 + 排期。系列的价值是复访率：观众看完一条会去找同系列的其他条 |

```bash
PY=python3
cd ~/Vflow

$PY scripts/voice_profile.py build && $PY scripts/voice_profile.py compare projects/<slug>/03-script.md
$PY scripts/risk_scan.py projects/<slug>/
$PY scripts/similarity.py <对标原稿> <你的稿子>
$PY scripts/hooks.py best
$PY scripts/ledger.py list
$PY scripts/vflow_state.py show <slug>
$PY scripts/backlog.py list
$PY scripts/doctor.py                          # 环境自检，装完先跑一次
```

## 口播稿 V2：结构模板 + 双轨留存

写稿不是从句子开始，是从**结构模板**开始。六选一：

| 模板 | 节拍 | 最适合 |
|---|---|---|
| T1 重新定义题 | 你以为 → 其实 → 证据 → 新判断 → 动作 | 观点 |
| T2 判断先行 | 判断 → 三个理由 → 边界 → 落到个人 | 趋势、结构 |
| T3 拆解三步 | 现象 → 归因 → 方法 → 证据 → 动作 | 方法、工具 |
| T4 自证实验 | 我做了 X → 过程 → 结果 → 代价 → 结论 | 演示、实录 |
| T5 对比评测 | A vs B → 判据 → 结果 → 谁该选 | 工具选型 |
| T6 清单避坑 | 预告 → 每条一个证据 → 收口 | 搜索长尾 |

然后按**双轨**写两版：抖音发现轨 45–90 秒（判断前置，5 秒定生死），
小红书深度轨 90–180 秒（步骤完整，搜索词铺满）。不是把短的拉长，是换一种给法。

写完跑机器自检：

```bash
python3 ~/Vflow/scripts/script_check.py <slug>
```

查慢热开头、缺开放循环 / re-hook、前 1/3 无可保存物、CTA 指向点赞、句长、时长偏差、
AI 味、重复、钩子变体不足。B 拆解型**没有可保存物不许进制作**。

## 复盘闭环：不做完这条就不算交付

复盘不发生，上面那几样资产就全是空转。所以把它做成流水线上的硬步骤：

```bash
# 发布当天登记（两条平台各一次）
$PY scripts/review.py published <slug> --platform douyin
$PY scripts/review.py published <slug> --platform xhs

# 48 小时后：谁该复盘了
$PY scripts/review.py pending

# 数据回填：表格、 .vflow.json、钩子库、台账一次写完
$PY scripts/review.py fill <slug> --platform douyin \
  --play 12000 --ret5 45 --finish 28 --like 300 --comment 40 --save 120 --share 20 --follow 15 \
  --good "开头具体痛点" --bad "第 6 页堆太多" --action "方法页压到 3 页" \
  --observation "具体痛点开头留人更好"

# 双轨指标（发现轨看 5 秒留存，深度轨看收藏率）
$PY scripts/review.py fill <slug> --platform xhs --play 8000 --collect-rate 3.4 --revisit 21 --track 深度轨

# 同轨均值 / 汇总表
$PY scripts/review.py stats --track 深度轨
$PY scripts/review.py report
```

工作台右侧「回填数据」有表单，不用记参数。

## 内容策略：双轨北极星

完整版在 `docs/content-strategy.md`。核心三条：

- **发现轨（抖音）** 第一指标是 **5 秒留存**（≥45% 有效）；**深度轨（小红书）** 第一指标是 **收藏率**（方法类 ≥3%、观点类 ≥1.5%）。
- **点赞不做目标**——2026 年第三方整理的权重里它排最后，追它等于给最不值钱的指标打工。
- **可保存物是入场券**：B 拆解型必须有判断标准 / 对照表 / 决策树；A 演示型必须有步骤或参数；C 实录型至少一个判断或动作。

口径说明：平台权重和阈值来自公开报道与第三方整理，**平台不公布完整算法**。
拿它定方向，最终用你自己过去 20 条的同轨中位数当基线。

## 声明台账：数字要能查

```bash
$PY scripts/claims.py scan <slug>        # 找稿件里没登记来源的数字
$PY scripts/claims.py add "49.5%" --source "IDC 2026-06" --caliber "大模型服务市场份额" --slug <slug>
$PY scripts/claims.py stale --days 90    # 超过 90 天没核的
```

## 发布包与发布队列

```bash
# 一键出包：质检没过会拒绝生成
$PY scripts/package.py build <slug> --zip
# publish/ 里有 video.mp4、双平台封面、双平台文案、检查清单、manifest.json

# 默认人工：只给包，你自己发
$PY scripts/publish.py queue <slug> --platform douyin
$PY scripts/publish.py run <slug> --platform douyin

# 半自动：打开创作页 + 复制文案，仍然你亲手点发布
$PY scripts/publish.py config --mode assisted

$PY scripts/publish.py done <slug> --platform douyin   # 登记，自动进复盘队列
```

**auto 模式三条硬门槛**：`publish.config.json` 开 `allow_auto`、本机有 Playwright、
这条内容质检全过，还要显式加 `--i-understand-the-risk`。缺一条退回人工。
即使 auto 也不代你点提交——失败方式通常是"发出去一条错内容"，不值得。

## 内容日历与系列化

```bash
$PY scripts/content_calendar.py series add "AI 工具怎么选" --goal 4 --start 2026-11-02 --end 2026-11-23
$PY scripts/content_calendar.py plan "换工具最贵的是重讲业务" --date 2026-11-02 --platform douyin --series S1
$PY scripts/content_calendar.py week      # 本周排期（工作台顶栏也有）
$PY scripts/content_calendar.py due       # 到期没做的
$PY scripts/content_calendar.py check     # 同平台同日冲突 / 系列进度
$PY scripts/content_calendar.py start "<关键词>"   # 从排期开项目
```

## 版本库

```bash
cat ~/Vflow/VERSION                          # 当前版本
python3 ~/Vflow/scripts/version.py check     # 技能版本号是否一致
python3 ~/Vflow/scripts/version.py list      # 所有版本
python3 ~/Vflow/scripts/version.py bump 1.1.0 --note "..."
```

每个版本在 `versions/vX.Y.Z.md` 记录改了什么、为什么、影响面。改了技能没升版本，
`check` 会报错——防止"改了没记"。

工作台顶栏有「待复盘」队列，登记过的项目没填数据会一直挂在那里。

## 最后一公里质检：封面和成片

检查阶段不只查文字。封面和成片有机器兜底：

```bash
$PY scripts/qc.py cover <slug>     # 字数 / 与标题重复 / 极限词 / 字体折行 + 手机缩略图
$PY scripts/qc.py video <slug>     # 音轨 / 分辨率 / 音画时长差 / 黑帧 / 静音 / 响度
$PY scripts/qc.py all <slug>       # 一起跑，写进 05-check.md
$PY scripts/qc.py template         # 生成 9:16 和 3:4 封面底图
```

有 FAIL 退出码为 1，工作台会标出来。缩略图在 `output/qc/`，打开看一眼——信息流里就是那么大。

## 第一次用

两种方式，任选：

**跟 AI 说一句**（推荐）——它发现没有 `profile.md` 会自动引导你走三步，一次问一个问题：

> 「我第一次用，帮我建起来」

**自己在终端填**：

```bash
python3 ~/Vflow/scripts/setup.py           # 问 8 个问题，生成 profile.md
python3 ~/Vflow/scripts/setup.py --check   # 随时看三步进度
python3 ~/Vflow/scripts/doctor.py          # 装完先自检：依赖、字体、状态、技能死链
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
- **右侧属性面板**：阶段信息、标记完成、**跑质检**、**登记发布**、打开目录
- **待复盘队列**：顶栏右上，已发布没回填数据的都在这
- **资产面板**：钩子库（按你的数据排序）、敏感词表、证据台账、风格卡

项目状态读的是 `projects/<slug>/.vflow.json`，不靠猜文件在不在。
状态是**三态**：没写（empty）/ 写了没定稿（wip）/ 定稿（done）。定稿之后又改了稿子，
会自动退回 wip——不会假装还是定稿。

## 回归测试

改脚本、改技能、发布前都跑一遍。每个用例在临时目录里跑，不碰你的真实项目。

```bash
bash ~/Vflow/tests/run_regression.sh
python3 ~/Vflow/tests/runner.py --only state    # 只跑一个套件
```

覆盖 11 个套件：状态机三态与指纹失效、复盘回填与台账门槛、封面/成片/发布包质检、
选题池、doctor 漂移检测、口播稿自检、声明台账、发布包与发布队列、内容日历、版本一致性，
以及 **技能契约（定位锁）**——哪条铁律被改掉了，测试会红。

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

不确定缺什么就跑 `python3 ~/Vflow/scripts/doctor.py`，它会把每个依赖、字体、路径、技能引用逐项列出来。

## 风险提示

`skills/all-in-one` 是第三方逆向接口工具，涉及平台 cookie，有合规、账号安全和 ToS 风险。**只做公开内容调研，不要拿它批量发布或刷量。** 不装不影响主流程。
