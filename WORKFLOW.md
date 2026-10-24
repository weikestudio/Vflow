# WORKFLOW.md · 全链路 SOP

一句话：**选题 → 结构 → 剧本 → 包装 → 检查 → 制作 → 复盘**，每步落一个文件，三步停一次。

对着 AI 说人话就行，它会自己判断在哪个阶段。比如说「我要做一条讲 Skill 是什么的视频」，它会从选题开始带你走。

## 流程图

```
想法
  │
  ├─ 阶段1 选题 ────→ 01-topic.md        ⏸ 停：确认选题
  │   对标调研 / 观众任务 / 价值预估
  │
  ├─ 阶段2 结构 ────→ 02-outline.md      ⏸ 停：确认框架
  │   选结构模板 T1–T6 / 四个大刺激点 / 可保存物定位 / 双轨差异
  │
  ├─ 阶段3 剧本 ────→ 03-script.md
  │   钩子三变体 / 双轨两版 / 四个大刺激点 / 留存五项
  │   └─ script_check.py  机器自检（慢热开头/无可保存物/CTA/节奏/AI味）
  │
  ├─ 阶段4 包装 ────→ 04-package.md
  │   标题 / 封面 / 开头3秒 / 小红书关键词矩阵 / AI 声明
  │
  ├─ 阶段5 检查 ────→ 05-check.md
  │   脚本自检 + 风险 + 实质 + AI味 + 声明台账 + 封面/成片/发布包质检   ⛔ 没过不许制作
  │
  ├─ 阶段6 制作 ────→ output/final-*.mp4  ⏸ 停：确认成片
  │   路线A AI生成 / 路线B 手绘 / 路线C 真人
  │   ├─ qc.py video  成片技术质检（黑帧/静音/响度/音画同步）
  │   ├─ publish-copy.md  分平台文案
  │   ├─ package.py build  一键发布包（成片/封面/双平台文案/清单/manifest）
  │   └─ publish.py queue → run  发布（人工 / 半自动 / auto 需显式开启）
  │
  └─ 阶段7 复盘 ────→ 06-review.md        48 小时后必做
      review.py fill 回填双轨指标 → .vflow.json、钩子回填、观察进台账
      review.py stats --track 看同轨均值
      攒够三条可比证据才写回 profile.md
```

## 能力对照表

各环节由 Vflow 自己的阶段 skill 承担，不依赖外部技能包：

| 环节 | 调用 | 说明 |
|---|---|---|
| 全流程调度 | `vflow` | 判断在哪一阶段、路由、落盘 |
| 选题与对标 | `vflow-topic` | 三问筛查 + 对标三层筛 + 二创边界自检 |
| 结构框架 | `vflow-outline` | 选 T1–T6 模板、四个大刺激点、可保存物、双轨差异 |
| 口播逐字稿 | `vflow-script` | 六模板 + 钩子三变体 + 双轨 + 留存五项 + 机器自检 |
| 标题封面开头 | `vflow-package` | 三件套 + 钩子库 + 小红书关键词矩阵 + 兑现检查 |
| 发布前检查 | `vflow-check` | 脚本自检 + 词表 + 实质 + AI 味 + 声明台账 + 质检 |
| 生成成片 | `vflow-produce` | HTML deck + TTS + 录屏 + 字幕 |
| 数据复盘 | `vflow-review` | 双轨归因 + 证据台账 + 钩子数据回填 |
| 选题池 | `backlog.md` | 候选 / 在做 / 已发 / 已毙，毙掉写原因 |
| 机器质检 | `qc.py` | 封面 + 成片 + 发布包 |
| 发布包 | `package.py` | 成片/封面/双平台文案/清单/manifest |
| 发布队列 | `publish.py` | manual 默认 / assisted / auto 需显式开启 |
| 内容日历 | `content_calendar.py` | 系列与排期 |

## 资产层（越用越值钱的部分）

| 资产 | 位置 | 怎么攒 |
|---|---|---|
| 风格卡 | `assets/voice-card.md` | 放 2–3 篇自己的成稿进 `assets/voice-samples/`，跑 `voice_profile.py build` |
| 钩子库 | `assets/hooks.md` | 用了就 `hooks.py use`，复盘时 `hooks.py fill` 回填数据 |
| 敏感词表 | `assets/wordlist.md` | 踩到坑往 `mine` 层加，写清后果 |
| 证据台账 | `ledger/evidence.md` | 复盘时 `ledger.py add`，攒够三条才准 `promote` |
| 选题池 | `backlog.md` | 有想法就 `backlog.py add`，毙掉 `kill --why` |
| 结构库 | `assets/structures.md` | 写稿前选模板 |
| 声明台账 | `claims.md` | 发前登记数字来源和口径 |
| 内容日历 | `calendar.md` | 系列与排期 |

```bash
PY=python3
cd ~/Vflow

# 声音档案：从自己的稿子里提取文风数字，写完比对有没有跑偏
$PY scripts/voice_profile.py build
$PY scripts/voice_profile.py show
$PY scripts/voice_profile.py compare projects/<slug>/03-script.md

# 敏感词扫描（发布前必跑）
$PY scripts/risk_scan.py projects/<slug>/

# 二创边界：跟对标原稿比，>0.5 就是照搬
$PY scripts/similarity.py <原稿> <你的稿子>

# 钩子库：挑、记、回填
$PY scripts/hooks.py best
$PY scripts/hooks.py use H7 <slug>
$PY scripts/hooks.py fill H7 <slug> --ret3 48 --finish 31 --verdict 有效

# 证据台账：一条数据不准改默认
$PY scripts/ledger.py add "观察到的现象" --slug <slug>
$PY scripts/ledger.py add x --slug <slug> --again E1
$PY scripts/ledger.py promote E1        # 不够三条会被拒绝
$PY scripts/ledger.py list

# 口播稿自检
$PY scripts/script_check.py <slug> [--track 深度轨]

# 复盘闭环
$PY scripts/publish.py done <slug> --platform douyin   # 发完登记（自动进复盘队列）
$PY scripts/review.py pending                          # 谁该复盘了（发布满 48h）
$PY scripts/review.py fill <slug> --platform douyin --play 12000 --ret5 45 --finish 28 --collect-rate 2.7 --track 发现轨
$PY scripts/review.py stats --track 深度轨              # 同轨均值
$PY scripts/review.py report                           # dashboard/review.md

# 封面 / 成片 / 发布包质检
$PY scripts/qc.py cover <slug>                     # 封面四项 + 手机缩略图
$PY scripts/qc.py video <slug>                     # 成片九项
$PY scripts/qc.py package <slug>                   # 标题/标签/关键词矩阵/AI 声明/导流
$PY scripts/qc.py all <slug>
$PY scripts/qc.py template                         # 封面底图

# 声明台账
$PY scripts/claims.py scan <slug>
$PY scripts/claims.py add "49.5%" --source "IDC 2026-06" --caliber "市场份额" --slug <slug>
$PY scripts/claims.py stale --days 90

# 发布包 / 发布队列
$PY scripts/package.py build <slug> --zip
$PY scripts/publish.py queue <slug> --platform douyin [--mode manual|assisted|auto]
$PY scripts/publish.py run <slug> --platform douyin
$PY scripts/publish.py done <slug> --platform douyin

# 内容日历
$PY scripts/content_calendar.py series add "主题" --goal 4 --start 2026-11-02
$PY scripts/content_calendar.py plan "选题" --date 2026-11-02 --platform douyin --series S1
$PY scripts/content_calendar.py week / due / check

# 版本
$PY scripts/version.py check

# 选题池
$PY scripts/backlog.py add "一句话想法" --type B
$PY scripts/backlog.py list
$PY scripts/backlog.py start "<关键词>"
$PY scripts/backlog.py kill "<关键词>" --why "答不了第二问"
$PY scripts/backlog.py review                      # 30 天没动的

# 环境自检 / 回归
$PY scripts/doctor.py [--fix] [--json]
bash tests/run_regression.sh

# 项目状态机（唯一真源 .vflow.json）
$PY scripts/vflow_state.py show <slug>
$PY scripts/vflow_state.py set <slug> 03 done      # 定稿后改稿会自动回 wip
$PY scripts/vflow_state.py migrate [--write]       # 补/对齐状态文件
$PY scripts/vflow_state.py archive <slug> 03-script.md
$PY scripts/vflow_state.py sync <slug> --from 03-script.md
$PY scripts/vflow_state.py final <slug> --video output/final.mp4

# 可视化工作台
$PY scripts/workbench.py
```

可选外接能力（没有就用人工，不要卡住）：

| 用途 | 依赖 |
|---|---|
| 下载对标视频 | `skills/video-download`（需 yt-dlp） |
| 平台数据抓取 | `skills/all-in-one`（需 aione CLI + cookie，有 ToS 风险） |

## 命令速查

```bash
# 开新项目
bash ~/Vflow/scripts/new_project.sh "选题短名"

# ── 竖版视频生成（抖音 / 小红书 1080x1920）──
# 上游 build_video.sh 默认 16:9，工作台自己接管了竖版录屏 + 字幕安全区
bash ~/Vflow/scripts/make_vertical.sh \
  ~/Vflow/projects/<slug>/deck

# 竖版带 BGM
bash ~/Vflow/scripts/make_vertical.sh \
  ~/Vflow/projects/<slug>/deck \
  --bgm ~/Vflow/assets/music.mp3

# ── 横版视频生成（路线 A，默认 1920x1080）──
SS=~/Vflow/skills/vflow-produce/scripts
PY=python3

# 首次试跑：零安装，用 macOS say
bash $SS/build_video.sh ~/Vflow/projects/<slug>/deck --tts say

# 正式：edge-tts 中文音色（已装）
bash $SS/build_video.sh ~/Vflow/projects/<slug>/deck \
  --tts edge --voice zh-CN-YunxiNeural

# 看有哪些音色
$PY $SS/tts.py --engine edge --list

# 只重做某几步
bash $SS/build_video.sh <deck> --only mix,compose --bgm-volume 0.12
bash $SS/build_video.sh <deck> --from record
bash $SS/build_video.sh <deck> --force

# 交付前校验
$PY $SS/validate_project.py ~/Vflow/projects/<slug>/deck

# 抽帧看效果
ffmpeg -ss 3 -i output/xxx.mp4 -frames:v 1 /tmp/f.png

# 下载对标视频
python3 ~/Vflow/skills/video-download/scripts/download.py "<链接>"
```

## 环境状态

| 依赖 | 状态 | 用途 |
|---|---|---|
| ffmpeg / ffprobe | ✅ 8.0.1 | 合成、抽帧、校验 |
| Pillow | ✅ | 字幕渲染 |
| macOS say | ✅ 内置 | TTS 兜底，机械感重 |
| edge-tts | 安装中 | 免费中文神经音色，推荐 |
| Playwright + Chromium | 安装中 | 幻灯片录屏，必需 |
| 中文字体 | ✅ | 封面质检字宽测算、字幕渲染 |
| yt-dlp | ❌ 未装 | `brew install yt-dlp` |
| aione CLI | ❌ 未装 | 逆向接口，装前看风险说明 |

实际状态以 `python3 scripts/doctor.py` 为准（它会逐项检测，不靠手写表格）。

## 竖版交付参数（抖音 / 小红书）

- 画幅 1080×1920，30fps
- 字幕安全区：底部留 240px
- 竖版字幕渲染 `--width 1080 --height 1920 --font-size 44 --margin 240`
- 人声 `loudnorm=I=-16`，BGM `volume=0.20`，总输出 `alimiter=limit=0.97`
- ffmpeg 常见坑：`amix` 默认归一化会把 BGM 压没，必须 `normalize=0`；Homebrew 版可能没编 libass，`subtitles=` 滤镜不可用，走 Pillow 渲染 PNG 叠加
