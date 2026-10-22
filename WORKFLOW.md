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
  │   8页框架 / 每页一个点
  │
  ├─ 阶段3 剧本 ────→ 03-script.md
  │   口播逐字稿 + 流畅度检查
  │
  ├─ 阶段4 包装 ────→ 04-package.md
  │   标题 / 封面文字 / 开头3秒
  │
  ├─ 阶段5 检查 ────→ 05-check.md
  │   发布风险 + AI味                    ⛔ 没过不许制作
  │
  ├─ 阶段6 制作 ────→ output/*.mp4       ⏸ 停：确认成片
  │   路线A AI生成 / 路线B 手绘 / 路线C 真人
  │   └─ publish-copy.md  分平台文案
  │
  └─ 阶段7 复盘 ────→ 06-review.md
      48小时后回填数据，规律写回 STUDIO.md
```

## 能力对照表

各环节由 Vflow 自己的阶段 skill 承担，不依赖外部技能包：

| 环节 | 调用 | 说明 |
|---|---|---|
| 全流程调度 | `vflow` | 判断在哪一阶段、路由、落盘 |
| 选题与对标 | `vflow-topic` | 三问筛查 + 对标三层筛 + 价值预估 |
| 结构框架 | `vflow-outline` | 页面级结构，每页一个角色 |
| 口播逐字稿 | `vflow-script` | 口语稿 + 流畅度五项自检 |
| 标题封面开头 | `vflow-package` | 三件套 + 兑现检查 |
| 发布前检查 | `vflow-check` | 机器风险 + 内容实质 + AI 味 |
| 生成成片 | `vflow-produce` | HTML deck + TTS + 录屏 + 字幕 |
| 数据复盘 | `vflow-review` | 分桶归因 + 规律写回 profile |

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
PY=/Users/v1/.workbuddy/binaries/python/envs/default/bin/python

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
| yt-dlp | ❌ 未装 | `brew install yt-dlp` |
| aione CLI | ❌ 未装 | 逆向接口，装前看风险说明 |

## 竖版交付参数（抖音 / 小红书）

- 画幅 1080×1920，30fps
- 字幕安全区：底部留 240px
- 竖版字幕渲染 `--width 1080 --height 1920 --font-size 44 --margin 240`
- 人声 `loudnorm=I=-16`，BGM `volume=0.20`，总输出 `alimiter=limit=0.97`
- ffmpeg 常见坑：`amix` 默认归一化会把 BGM 压没，必须 `normalize=0`；Homebrew 版可能没编 libass，`subtitles=` 滤镜不可用，走 Pillow 渲染 PNG 叠加
