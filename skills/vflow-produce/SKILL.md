---
name: vflow-produce
description: 内容制作阶段。把已定稿的口播稿做成成片——路线 A 用 HTML 幻灯片 + TTS + 录屏自动出片，路线 B 白板手绘动画，路线 C 真人出镜提词稿。也用于重做某一步（重录、重混 BGM、重烧字幕、换音色、加封面）。用户要生成视频、出成片、渲染、重录、加字幕封面时使用。产出 projects/<slug>/output/ 与 publish-copy.md。
---

# 阶段 6 · 制作

## 开工前

读 `$VFLOW/profile.md`。**确认 `03-script.md` 已定稿、`05-check.md` 三层全过。** 没过检查不许进制作。

## 三条路线

| 路线 | 适用 | 谁来做 |
|---|---|---|
| **A · AI 生成讲解片**（默认，不露脸） | 演示型、拆解型 | 全自动，本 skill 主流程 |
| **B · 白板手绘动画** | 讲机制、讲流程 | 输入 SRT，外部手绘工具 |
| **C · 真人出镜** | 实录型、需要建立信任 | 交付提词稿，使用者自己拍 |

**A+C 混合（演示型推荐）**：开头露脸 3 秒钩子 + 主体用路线 A 生成，剪到一起。成本最低、效果最稳。

---

## 路线 A · AI 生成讲解片

### 为什么是 HTML 而不是 PPT / 剪映

|  | 拖拽工具 | 这条流水线 |
|---|---|---|
| 改一个字 | 打开软件手动改，重新导出 | 改文本文件，重跑脚本 |
| 做第二条 | 再拖一遍 | 换内容文件，模板不动 |
| 能否 diff / 回滚 | 不能 | 能，就是一堆文本文件 |

代价是第一次要写 CSS。一次性成本。

### Step 1 · 定框架（和使用者一起）

先别打开编辑器。基于 `02-outline.md` 写 `deck/framework.json`：

```json
{
  "concept": "...", "audience": "...", "one_liner": "...",
  "total_pages": 8, "target_duration_sec": 94,
  "structure": [{ "page": 1, "role": "钩子", "point": "..." }]
}
```

8 页 ≈ 90–110 秒。一页一个点。每页给 **role**（钩子/背景/why/总览/方法×N/收尾），不是只给标题。

### Step 2 · 幻灯片和旁白一起写

复制 `references/deck-template.html` 到 `deck/index.html`，改写页面。旁白**写进页面**的 `data-narration`，配 `data-duration`（秒）——这份标记是唯一真源，下游全读它。

然后产出四个平级文件：

| 文件 | 内容 | 被谁消费 |
|---|---|---|
| `index.html` | 幻灯片本体 | 录屏 |
| `narration.json` | 每页 title / narration / duration_sec | 时间轴 |
| `narration.txt` | 连续稿，**一页一段、空行分隔、顺序一致** | TTS + SRT |
| `narration.md` | 人读的稿子 + 页码时间表 | 使用者 |

`narration.txt` 的"一页一段"是承重结构——`build_srt.py` 靠段落边界放页间停顿。幻灯片里按 `E` 可直接导出 `narration.json`。

让使用者读 `narration.md` 点头后再烧 TTS 时间。

### 旁白锁定

使用者改过或点头之后，**不要再独立改三个旁白文件**。以获批文本为源，同步 `narration.txt`、`narration.json` 和每页 `data-narration`，核对段落数、顺序、标点、页标题是否一致。不要悄悄润色已批准的措辞。

旁白一改，**SRT、时间轴、录屏、字幕、成片全部作废**，不能因为文件已存在就复用。

### Step 3 · 装配

```bash
S=$VFLOW/skills/vflow-produce/scripts
bash $S/build_video.sh $VFLOW/projects/<slug>/deck --bgm $VFLOW/assets/music.mp3
```

`--tts auto`（默认）优先本地 Voicebox，其次 edge-tts，最后 macOS `say`。下游不关心用了哪个，所以**第一遍用 `say` 跑通整条线是正当做法**：

```bash
bash $S/build_video.sh <deck> --tts say                              # 零安装试跑
bash $S/build_video.sh <deck> --tts edge --voice zh-CN-YunxiNeural   # 正式，中文音色好
bash $S/build_video.sh <deck> --tts voicebox --voice <profile>       # 克隆自己的声音
python3 $S/tts.py --engine edge --list                               # 有哪些音色
```

每步产物已存在就跳过，迭代很便宜：

```bash
bash $S/build_video.sh <deck> --only mix,compose --bgm-volume 0.12   # BGM 太响，只重混
bash $S/build_video.sh <deck> --from record                          # 幻灯片改了
bash $S/build_video.sh <deck> --only srt,compose                     # 字幕不对
bash $S/build_video.sh <deck> --force                                # 全量重来
```

已有真人录音时，把它当主时钟，别再合成一遍：

```bash
bash $S/build_video.sh <deck> --audio audio/voicebox_manual.wav \
  --srt-file audio/voicebox_whisper.srt --lead 0.57 --bgm none --from srt
```

### 单步脚本

- `tts.py` — 旁白 → `audio/voice.wav`
- `tts_voicebox.py` — Voicebox 后端，`--list` 看音色
- `build_srt.py` — 旁白 + 实测音频时长 → `audio/voice.srt`
- `whisper_align.py` — 词级时间戳 + 获批文本 → 精确字幕
- `deck_capture.py timeline|slides|video` — 时间轴对齐 / 静态 PNG / 录屏 webm
- `render_captions.py` — SRT → 透明 PNG + `record/burn_caps.sh`
- `mix_bgm.sh` — 人声 + 音乐 → `audio/voice_with_bgm.wav`
- `compose.sh` — 对齐、烧字幕、合流 → `final/<slug>.mp4`
- `add_cover.sh` — 首帧封面叠加，不移动音频
- `validate_project.py` — 旁白/幻灯片一致性与成片时长校验

### 竖版交付参数（抖音 / 小红书）

- 画幅 1080×1920，30fps
- 字幕安全区：底部留 240px
- 竖版字幕：`--width 1080 --height 1920 --font-size 44 --margin 240`
- 人声 `loudnorm=I=-16`，BGM `volume=0.20`，总输出 `alimiter=limit=0.97`

竖版快捷脚本：`bash $VFLOW/scripts/make_vertical.sh <deck> [--bgm <music.mp3>]`

---

## 会咬人的地方

**音频时长是主时钟。** 手写的 `data-duration` 只是估算，TTS 决定真实长度。时间轴、字幕、录屏全部按实测 `voice.wav` 缩放，反过来不行。永远 `ffprobe`，不要硬编码时长。

**Playwright 的 webm 会有前导、尾帧和速度漂移。** 录屏在浏览器内一次性调 `deckAPI.playSequence()`；如果用 Python 逐页 `go()` + `wait_for_timeout()`，往返延迟会累积， trimmed 时首页可能直接消失。至少要量 2–3 个可见翻页点对比音频边界：若原始时间 `r` 和音频时间 `t` 满足 `r ≈ a + b·t` 且 `b` 明显不等于 1，先做仿射校正再烧字幕：

```
trim=start=a,setpts=(PTS-STARTPTS)/b
```

实测竖版录屏曾慢约 12.9%（`b≈1.1289`），而首帧并没有 14 秒前导——所以别只看时长差。原始帧率也要 probe。

**ffmpeg 常见坑**：`amix` 默认归一化会把 BGM 压没，必须 `normalize=0`；Homebrew 版可能没编 libass，`subtitles=` 滤镜不可用，走 Pillow 渲染 PNG 叠加。

**封面最后加。** 叠加 0.5–0.7 秒即可，不要 prepend（除非有意配前导音）。

**交付前跑一次** `validate_project.py`，抽帧看首帧、封面后一帧、翻页点、音视频时长是否对齐：

```bash
ffmpeg -ss 3 -i output/xxx.mp4 -frames:v 1 /tmp/f.png
```

---

## 路线 C · 真人出镜

交付 `03b-teleprompter.md`：字号要大、一行 ≤12 字、标注每段预计秒数/换气点/重录提示。附拍摄清单（机位、背景、提词速度、每条拍几条、NG 怎么处理）。

**真人录音是主时钟**，字幕按实际音频对齐，不要按稿子估时间。后期用 `render_captions.py` 烧字幕。

---

## 收尾

1. 成片拷到 `projects/<slug>/output/`
2. **停一次**，让使用者看过再发布
3. 写 `publish-copy.md`：**抖音版和小红书版分开写**，标题、正文、标签各不同。不要把口播稿当文案粘上去
4. 需要时刷新仪表盘：`$VFLOW/scripts/build_dashboard.py`

---

## 环境

- Python：`python3`（其他机器用 `PY=` 或 `VFLOW_PY=` 指定自己的 venv）
- 必需：`ffmpeg` / `ffprobe`、Playwright + Chromium、Pillow
- TTS：`say`（内置，机械感重）/ `edge-tts`（免费，中文好）/ Voicebox（克隆自己声音，质量最好）
