#!/usr/bin/env python3
"""Vflow 最后一公里质检：封面可读性 + 成片技术参数。

「检查没过不许进制作」这条铁律，之前只查文字。封面和成片没有机器兜底，
竖版主战场上最容易翻车的几类问题全靠人眼：字幕超框、黑帧、静音、
音画不同步、封面字在手机上糊成一团。

用法：
    python3 qc.py cover <slug> [--preview]   封面：字数 / 重复 / 极限词 / 字体宽度 / 缩略图
    python3 qc.py video <slug> [--video 路径] 成片：参数 / 音画时长 / 黑帧 / 静音 / 响度
    python3 qc.py all <slug>                 两样都跑
    python3 qc.py template                   生成封面底图（1080×1920 和 1080×1440）

结果写进 05-check.md 的「## 机器质检」一节，同时把摘要写进 .vflow.json。
有 FAIL → 退出码 1，工作台会标出来。

零依赖（Pillow 可选；没装就跳过缩略图）。
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import vflow_state as VS          # noqa: E402

ROOT = VS.ROOT
QC_MARKER = "vflow-qc"
QC_SECTION = "机器质检"
SAFE = {"top": 0.15, "bottom": 0.15, "left": 0.10, "right": 0.10}
COVER = {"douyin": (1080, 1920), "xhs": (1080, 1440)}
ABS_HARD = ["第一", "唯一", "独家", "首个", "顶级", "极致", "100%", "百分百",
            "绝对", "彻底", "永久", "万能", "史无前例", "全国第一", "国家级",
            "最好", "最佳", "最强", "最优", "最高", "最先进", "最领先",
            "最专业", "最便宜", "最划算"]
ABS_SOFT = ["最新", "首选", "顶尖", "领先", "全网", "史上"]
FONT_CANDIDATES = [
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def read(p):
    return VS.read_text(p)


def run(cmd, timeout=120):
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return type("R", (), {"returncode": -1, "stdout": "",
                              "stderr": str(e)})()


def pick_font(size):
    try:
        from PIL import ImageFont
    except ImportError:
        return None
    for cand in FONT_CANDIDATES:
        if os.path.isfile(cand):
            try:
                return ImageFont.truetype(cand, size)
            except OSError:
                continue
    return None


# ---------- 封面解析 ----------

def parse_package(slug):
    """从 04-package.md 里尽量宽松地取标题 / 封面字（兼容两种写法）。"""
    path = os.path.join(VS.slug_dir(slug), "04-package.md")
    text = read(path)
    if not text or VS.TEMPLATE_MARK in text:
        return {}

    out = {}
    cur = None
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^##\s+(抖音|小红书)\s*$", line)
        if m:
            cur = "douyin" if m.group(1) == "抖音" else "xhs"
            out.setdefault(cur, {})
            i += 1
            continue
        if line.startswith("## "):
            cur = None
        if cur:
            nxt_lines = []
            fm = re.match(r"^-?\s*\*\*([^*]+)\*\*[（(]?[^）)]*[）)]?\s*：\s*(.*)$",
                          line)
            if fm:
                label = fm.group(1).strip()
                rest = fm.group(2).strip()
                val = rest
                if not val:
                    nxt = []
                    j = i + 1
                    while j < len(lines) and lines[j].strip().startswith(">"):
                        nxt.append(re.sub(r"^>\s*", "", lines[j].strip()))
                        j += 1
                    val = " ".join(x for x in nxt if x).replace("**", "").strip()
                    nxt_lines = [x.replace("**", "").strip() for x in nxt if x]
                    i = j - 1
                key = None
                if "封面标题" in label:
                    key = "cover"
                    if nxt_lines:
                        out[cur]["cover_lines"] = nxt_lines
                elif "文字标题" in label or "笔记标题" in label:
                    key = "title"
                elif "副字" in label:
                    key = "sub"
                elif "开头 3 秒" in label or "开头3秒" in label:
                    key = "opening"
                elif "话题" in label or "标签" in label:
                    key = "tags"
                if key:
                    val = val.replace("**", "").strip("> ").strip()
                    if val:
                        out[cur][key] = val
        i += 1
    return out


def parse_outline(slug):
    text = read(os.path.join(VS.slug_dir(slug), "02-outline.md"))
    info = {}
    m = re.search(r"总页数\*\*：([^\n]+)", text)
    if m:
        n = re.search(r"\d+", m.group(1))
        if n:
            info["pages"] = int(n.group(0))
    m = re.search(r"目标时长\*\*：([^\n]+)", text)
    if m:
        n = re.search(r"\d+", m.group(1))
        if n:
            info["target_sec"] = int(n.group(0))
    return info


def parse_script_estimate(slug):
    text = read(os.path.join(VS.slug_dir(slug), "03-script.md"))
    m = re.search(r"目标时长\*\*：(\d+)", text)
    if m:
        return int(m.group(1))
    m = re.search(r"字数\*\*：?[^\d]*(\d+)", text)
    if m:
        return round(int(m.group(1)) / 4.2)
    return None


# ---------- 封面检查 ----------

def text_width(text, font):
    if not font:
        return None
    try:
        bb = font.getbbox(text)
        return bb[2] - bb[0]
    except Exception:
        return None


def wrap_lines(text, font, max_width):
    """按字宽折行（中文按字符、英文按词粗切）。"""
    if not font:
        return [text]
    lines, cur = [], ""
    tokens = re.findall(r"[A-Za-z0-9%\-\.]+|\s+|.", text)
    for t in tokens:
        if t.isspace():
            if cur:
                cur += " "
            continue
        if text_width(cur + t, font) <= max_width:
            cur += t
        else:
            if cur.strip():
                lines.append(cur.strip())
            cur = t
    if cur.strip():
        lines.append(cur.strip())
    return lines


def check_cover(slug, preview=False, results=None):
    package = parse_package(slug)
    rows = results if results is not None else []
    if not package:
        rows.append(("封面", "SKIP", "04-package.md 还是空模板，没有封面可查"))
        return rows

    from PIL import Image, ImageDraw
    made = []
    for plat, size in COVER.items():
        data = package.get(plat) or {}
        title = data.get("title")
        cover = data.get("cover")
        sub = data.get("sub") or ""
        name = "抖音" if plat == "douyin" else "小红书"

        if not title:
            rows.append(("%s · 标题" % name, "FAIL", "文字标题没填"))
        else:
            limit = 20
            n = len(re.sub(r"\s", "", title))
            rows.append(("%s · 标题长度" % name,
                         "PASS" if n <= limit else "WARN",
                         "%d 字（上限 %d）" % (n, limit)))

        if not cover:
            rows.append(("%s · 封面字" % name, "FAIL", "封面标题没填"))
            continue
        n = len(re.sub(r"\s", "", cover))
        rows.append(("%s · 封面字数" % name,
                     "PASS" if n <= 14 else ("WARN" if n <= 20 else "FAIL"),
                     "%d 字（建议 ≤12，最多 14）" % n))

        if title and re.sub(r"\s|[，。！？、,.!?]", "", cover) == \
                re.sub(r"\s|[，。！？、,.!?]", "", title):
            rows.append(("%s · 封面≠标题" % name, "FAIL",
                         "封面字和文字标题一模一样，浪费了一个信息位"))

        corpus = (title or "") + cover
        hard = [w for w in ABS_HARD if w in corpus]
        soft = [w for w in ABS_SOFT if w in corpus]
        if hard:
            rows.append(("%s · 极限词" % name, "FAIL",
                         "命中：%s（广告法高风险，改成可验证的具体表述）"
                         % "、".join(hard)))
        elif soft:
            rows.append(("%s · 极限词" % name, "WARN",
                         "命中：%s（看语境，能换成具体事实就换）"
                         % "、".join(soft)))
        else:
            rows.append(("%s · 极限词" % name, "PASS", "无绝对化用语"))

        # 字体宽度：主字占画面 13%，最多两行，左右安全区各 10%
        W, H = size
        font_size = int(W * 0.13)
        font = pick_font(font_size)
        max_w = int(W * (1 - SAFE["left"] - SAFE["right"]))
        cover_lines = data.get("cover_lines") or []
        if cover_lines:
            lines = cover_lines
        elif len(re.sub(r"\s", "", cover)) <= 14 and font \
                and text_width(cover, font) <= max_w:
            lines = [cover]          # 短且放得下：创作者可以排成一行
        else:
            lines = wrap_lines(cover, font, max_w)
        sub_font = pick_font(int(W * 0.055))
        sub_lines = wrap_lines(sub, sub_font, max_w) if sub else []
        total_lines = len(lines) + len(sub_lines)
        if font is None:
            rows.append(("%s · 字体适配" % name, "WARN",
                         "没找到中文字体，跳过宽度测算"))
        elif len(lines) > 2:
            rows.append(("%s · 字体适配" % name, "FAIL",
                         "主字在 %dpt 下折成 %d 行，手机上读不完（≤2 行）"
                         % (font_size, len(lines))))
        elif total_lines > 3:
            rows.append(("%s · 字体适配" % name, "WARN",
                         "主字+副字共 %d 行，手机上会挤（建议 ≤3 行）"
                         % total_lines))
        else:
            rows.append(("%s · 字体适配" % name, "PASS",
                         "%dpt 下主字 %d 行、副字 %d 行，在安全区内"
                         % (font_size, len(lines), len(sub_lines))))

        if preview:
            try:
                made.append(draw_preview(slug, plat, cover, sub, lines,
                                         sub_lines, font_size, size,
                                         Image, ImageDraw))
            except Exception as e:      # 预览失败不影响判定
                rows.append(("%s · 缩略图" % name, "WARN",
                             "预览生成失败：%s" % e))

    if preview and made:
        rows.append(("封面缩略图", "INFO", "已生成：" + "、".join(made)))
    return rows


def draw_preview(slug, plat, cover, sub, lines, sub_lines, font_size, size,
                 Image, ImageDraw):
    W, H = size
    img = Image.new("RGB", (W, H), (18, 18, 18))
    d = ImageDraw.Draw(img)
    # 安全区参考线（浅灰虚线感）
    x0, x1 = int(W * SAFE["left"]), int(W * (1 - SAFE["right"]))
    y0, y1 = int(H * SAFE["top"]), int(H * (1 - SAFE["bottom"]))
    d.rectangle([x0, y0, x1, y1], outline=(60, 60, 60), width=max(2, W // 360))
    font = pick_font(font_size)
    sfont = pick_font(int(W * 0.055))
    lh = int(font_size * 1.28)
    total_h = lh * len(lines) + int(lh * 0.5) * len(sub_lines)
    y = (H - total_h) // 2
    for ln in lines:
        if font:
            w = text_width(ln, font) or 0
            d.text(((W - w) // 2, y), ln, font=font, fill=(255, 255, 255))
        y += lh
    y += int(lh * 0.2)
    for ln in sub_lines:
        if sfont:
            w = text_width(ln, sfont) or 0
            d.text(((W - w) // 2, y), ln, font=sfont, fill=(190, 190, 190))
        y += int(lh * 0.5)

    out_dir = os.path.join(VS.slug_dir(slug), "output", "qc")
    os.makedirs(out_dir, exist_ok=True)
    full = os.path.join(out_dir, "cover-%s.png" % plat)
    img.save(full)
    # 手机缩略图：按 180px 宽缩，模拟信息流里看到的大小
    thumb_w = 180
    thumb = img.resize((thumb_w, int(H * thumb_w / W)))
    thumb.save(os.path.join(out_dir, "cover-%s-thumb.png" % plat))
    return "output/qc/cover-%s.png" % plat


# ---------- 成片检查 ----------

def probe_video(path):
    r = run(["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=codec_type,codec_name,width,height,"
             "r_frame_rate,pix_fmt,sample_rate,channels",
             "-of", "json", path])
    try:
        return json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return {}


def check_video(slug, video=None, results=None):
    rows = results if results is not None else []
    st = VS.build_state(slug)
    video = video or st.get("final", {}).get("video")
    path = os.path.join(VS.slug_dir(slug), video) if video else None
    if not path or not os.path.isfile(path):
        cand = VS.any_video(slug)
        path = os.path.join(VS.slug_dir(slug), cand) if cand else None
    if not path or not os.path.isfile(path):
        rows.append(("成片", "SKIP", "还没有成片，制作阶段出片后再跑"))
        return rows

    rel = os.path.relpath(path, VS.slug_dir(slug))
    info = probe_video(path)
    streams = info.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    dur = float(info.get("format", {}).get("duration", 0) or 0)

    rows.append(("成片文件", "INFO", "%s，%.1f 秒" % (rel, dur)))
    if not a:
        rows.append(("音轨", "FAIL", "没有音轨，口播片不能没有声音"))
    else:
        rows.append(("音轨", "PASS", "%s / %s Hz / %s ch" % (
            a.get("codec_name"), a.get("sample_rate"), a.get("channels"))))

    w, h = v.get("width"), v.get("height")
    if w and h:
        vertical = h > w
        ok = (w, h) in ((1080, 1920), (1080, 1440), (1920, 1080))
        rows.append(("分辨率", "PASS" if ok else "WARN",
                     "%s×%s（%s）" % (w, h, "竖版" if vertical else "横版")))
    if v.get("codec_name") and v.get("codec_name") != "h264":
        rows.append(("编码", "WARN", "%s，建议 h264 yuv420p 兼容性最好"
                     % v.get("codec_name")))
    if v.get("pix_fmt") and v.get("pix_fmt") != "yuv420p":
        rows.append(("像素格式", "WARN", "%s，建议 yuv420p" % v.get("pix_fmt")))
    fps = v.get("r_frame_rate", "")
    if fps:
        try:
            num_, den = fps.split("/")
            f = float(num_) / float(den or 1)
            rows.append(("帧率", "PASS" if 24 <= f <= 60 else "WARN",
                         "%.0f fps" % f))
        except (ValueError, ZeroDivisionError):
            pass

    # 音画时长差
    if a:
        r = run(["ffprobe", "-v", "error", "-select_streams", "a:0",
                 "-show_entries", "stream=duration", "-of",
                 "default=nw=1:nk=1", path])
        try:
            adur = float((r.stdout or "0").strip())
        except ValueError:
            adur = 0.0
        if adur and abs(dur - adur) > 0.3:
            rows.append(("音画同步", "FAIL",
                         "画面 %.2fs / 声音 %.2fs，差 %.2fs（>0.3s）"
                         % (dur, adur, abs(dur - adur))))
        elif adur:
            rows.append(("音画同步", "PASS",
                         "差 %.2fs" % abs(dur - adur)))

    # 和稿子估时比
    est = parse_script_estimate(slug)
    outline = parse_outline(slug)
    target = est or outline.get("target_sec")
    if target and dur:
        diff = abs(dur - target) / target
        rows.append(("时长匹配", "PASS" if diff <= 0.25 else "WARN",
                     "成片 %.0fs / 稿子估 %.0fs（差 %.0f%%）"
                     % (dur, target, diff * 100)))

    # 黑帧
    r = run(["ffmpeg", "-hide_banner", "-i", path, "-vf",
             "blackdetect=d=0.5:pix_th=0.10", "-an", "-f", "null", "-"])
    blacks = re.findall(r"black_start:([\d.]+)\s+black_end:([\d.]+)", r.stderr)
    long_blacks = [(float(s), float(e)) for s, e in blacks if float(e) - float(s) >= 0.5]
    if long_blacks:
        at = "、".join("%.1f–%.1f" % (s, e) for s, e in long_blacks[:5])
        rows.append(("黑帧", "FAIL", "%d 段 ≥0.5s：%s" % (len(long_blacks), at)))
    else:
        rows.append(("黑帧", "PASS", "没有 ≥0.5s 的黑场"))

    # 静音（语音段里 >2s 没人声）
    r = run(["ffmpeg", "-hide_banner", "-i", path, "-af",
             "silencedetect=noise=-45dB:d=2", "-vn", "-f", "null", "-"])
    sil = re.findall(r"silence_start:\s*([\d.]+)", r.stderr)
    if sil:
        rows.append(("静音", "WARN",
                     "%d 段 ≥2s 静音：%s（开头留白可忽略）"
                     % (len(sil), "、".join(sil[:5]))))
    else:
        rows.append(("静音", "PASS", "没有 ≥2s 的静音段"))

    # 响度
    r = run(["ffmpeg", "-hide_banner", "-i", path, "-af",
             "ebur128=peak=true", "-vn", "-f", "null", "-"])
    # ebur128 每帧都会打印瞬时值，取最后一组（Summary）才是整体结果
    mi = re.findall(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", r.stderr)
    tp = re.findall(r"Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", r.stderr)
    mi = type("M", (), {"group": lambda self, i, v=mi: v[-1]})() if mi else None
    tp = type("M", (), {"group": lambda self, i, v=tp: v[-1]})() if tp else None
    if mi:
        lufs = float(mi.group(1))
        ok = -19 <= lufs <= -13
        rows.append(("响度", "PASS" if ok else "WARN",
                     "整体 %.1f LUFS（目标 -16）%s" % (
                         lufs, "" if ok else "，偏离较大")))
    if tp:
        peak = float(tp.group(1))
        if peak > -1.0:
            rows.append(("峰值", "WARN",
                         "真峰值 %.1f dBFS，接近 0 可能削波" % peak))

    return rows


# ---------- 发布包检查 ----------

CONTACT = [r"微信", r"加我", r"私信", r"二维码", r"扫码", r"加V", r"vx",
           r"链接", r"http"]
AI_DECL = [r"AI\s*辅助", r"AI\s*生成", r"AI\s*合成", r"人工智能生成",
           r"内容由\s*AI"]
KEYWORD_ROWS = ["核心词", "长尾词", "问题词", "场景词"]


def parse_matrix(text):
    """小红书关键词矩阵：{维度: 关键词}"""
    out = {}
    m = re.search(r"^##\s*小红书关键词矩阵.*?$", text, re.M)
    if not m:
        return out
    start = m.end()
    nxt = re.search(r"^##\s+", text[start:], re.M)
    chunk = text[start:start + nxt.start()] if nxt else text[start:]
    for line in chunk.split("\n"):
        if not line.startswith("|") or "---" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        for r in KEYWORD_ROWS:
            if cells[0].startswith(r) and cells[1]:
                out[r] = cells[1]
    return out


def tag_count(s):
    if not s:
        return 0
    return len(re.findall(r"#\S+", s)) or len([x for x in re.split(r"[,，、\s]+", s)
                                               if x and x != "—"])


def check_package(slug, results=None):
    rows = results if results is not None else []
    path = os.path.join(VS.slug_dir(slug), "04-package.md")
    text = read(path)
    if not text.strip() or VS.TEMPLATE_MARK in text:
        rows.append(("发布包", "SKIP", "04-package.md 还是空模板"))
        return rows

    package = parse_package(slug)
    dy = package.get("douyin") or {}
    xhs = package.get("xhs") or {}
    matrix = parse_matrix(text)

    for name, data, plat, tag_min, tag_max in (
            ("抖音", dy, "douyin", 3, 5), ("小红书", xhs, "xhs", 5, 10)):
        title = data.get("title") or ""
        if not title:
            rows.append(("%s · 标题" % name, "FAIL", "没填"))
        else:
            n = len(re.sub(r"\s", "", title))
            rows.append(("%s · 标题长度" % name,
                         "PASS" if n <= 20 else "WARN", "%d 字" % n))
        tags = data.get("tags") or ""
        n_tag = tag_count(tags)
        if not tags:
            rows.append(("%s · 标签" % name, "WARN", "没填"))
        else:
            ok = tag_min <= n_tag <= tag_max
            rows.append(("%s · 标签数" % name, "PASS" if ok else "WARN",
                         "%d 个（建议 %d–%d）" % (n_tag, tag_min, tag_max)))

    # 小红书：前 20 字含核心词
    core = matrix.get("核心词", "")
    x_title = xhs.get("title") or ""
    if core:
        first20 = re.sub(r"\s", "", x_title)[:20]
        hit = any(k and k in first20 for k in re.split(r"[，,、/\s]+", core))
        rows.append(("小红书 · 前 20 字核心词",
                     "PASS" if hit else "FAIL",
                     ("命中「%s」" % core) if hit else
                     "标题前 20 字没有核心词「%s」" % core))
    else:
        rows.append(("小红书 · 关键词矩阵", "FAIL", "缺核心词"))

    if matrix:
        missing = [r for r in KEYWORD_ROWS if not matrix.get(r)]
        rows.append(("关键词矩阵", "PASS" if not missing else "WARN",
                     "四维完整" if not missing else
                     "缺：%s" % "、".join(missing)))
    else:
        rows.append(("关键词矩阵", "FAIL", "整张表没填"))

    # AI 声明
    if any(re.search(p, text) for p in AI_DECL):
        rows.append(("AI 生成声明", "PASS", "已声明"))
    else:
        rows.append(("AI 生成声明", "WARN",
                     "没写；平台要求对 AI 生成内容做标识"))

    # 联系方式
    hits = [p for p in CONTACT
            if re.search(p, (dy.get("title", "") + xhs.get("title", "") +
                             dy.get("opening", "") + xhs.get("opening", "")))]
    if hits:
        rows.append(("联系方式", "FAIL",
                     "疑似导流：%s（平台会限流）" % "、".join(hits[:3])))
    else:
        rows.append(("联系方式", "PASS", "标题和开头无导流词"))
    return rows


# ---------- 写入 ----------

def render_report(rows, generated, package_rows=None):
    lines = ["| 检查项 | 结果 | 详情 |", "|---|---|---|"]
    for item, status, detail in rows:
        icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌",
                "SKIP": "⏭", "INFO": "ℹ️"}.get(status, status)
        lines.append("| %s | %s | %s |" % (item, icon + " " + status, detail))
    n_fail = sum(1 for r in rows if r[1] == "FAIL")
    n_warn = sum(1 for r in rows if r[1] == "WARN")
    verdict = "通过" if n_fail == 0 else "有 %d 项未通过" % n_fail
    head = ["<!-- %s %s -->" % (QC_MARKER, json.dumps(
        {"generated": generated, "fail": n_fail, "warn": n_warn},
        ensure_ascii=False)),
        "生成：%s · 结论：**%s**" % (generated, verdict), ""]
    md = head + lines
    if package_rows is not None:
        p_fail = sum(1 for r in package_rows if r[1] == "FAIL")
        md += ["", "### 发布包", "", "| 检查项 | 结果 | 详情 |", "|---|---|---|"]
        for item, status, detail in package_rows:
            icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌",
                    "SKIP": "⏭"}.get(status, status)
            md.append("| %s | %s | %s |" % (item, icon + " " + status, detail))
        n_fail += p_fail
    return "\n".join(md), n_fail


def write_report(slug, block):
    path = os.path.join(VS.slug_dir(slug), "05-check.md")
    text = read(path)
    if not text:
        text = "# 05 · 发布前检查\n\n- **检查时间**：\n- **结论**：\n"
    text = text.replace("<!-- vflow-template: 未填写 -->\n", "")
    section = "## %s\n\n%s" % (QC_SECTION, block.strip())
    m = re.search(r"^## %s\s*$" % re.escape(QC_SECTION), text, re.M)
    if m:
        nxt = re.search(r"^## ", text[m.end():], re.M)
        end = m.end() + nxt.start() if nxt else len(text)
        text = text[:m.start()] + section + "\n\n" + text[end:]
    else:
        text = text.rstrip() + "\n\n" + section + "\n"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text.rstrip() + "\n")


def cmd_run(args, cover=False, video=False, package=False):
    slug = args.slug
    if not os.path.isdir(VS.slug_dir(slug)):
        return {"error": "项目不存在: %s" % slug}, 2
    rows, pkg_rows = [], None
    if cover:
        rows = check_cover(slug, preview=getattr(args, "preview", False),
                           results=rows)
    if video:
        rows = check_video(slug, video=getattr(args, "video", None),
                           results=rows)
    if package:
        pkg_rows = check_package(slug, results=[])
    generated = now()
    block, n_fail = render_report(rows, generated, pkg_rows)
    write_report(slug, block)

    st = VS.build_state(slug)
    scope = "+".join([x for x, on in (("cover", cover), ("video", video),
                                      ("package", package)) if on]) or "none"
    st["qc"] = {
        "generated": generated,
        "fail": n_fail,
        "warn": sum(1 for r in rows + (pkg_rows or []) if r[1] == "WARN"),
        "scope": scope,
    }
    VS.write_state(slug, st)
    return {"slug": slug, "generated": generated, "fail": n_fail,
            "rows": [{"item": i, "status": s, "detail": d}
                     for i, s, d in rows + (pkg_rows or [])],
            "report": "05-check.md#%s" % QC_SECTION}, (1 if n_fail else 0)


def cmd_template(args):
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return {"error": "需要 Pillow：pip install pillow --break-system-packages"}, 2
    out = os.path.join(ROOT, "assets", "cover-templates")
    os.makedirs(out, exist_ok=True)
    made = []
    for plat, (W, H) in COVER.items():
        img = Image.new("RGB", (W, H), (20, 22, 24))
        d = ImageDraw.Draw(img)
        # 顶部 3 秒钩子区 + 中央主字区 + 底部字幕安全区
        d.rectangle([0, 0, W, int(H * 0.15)], fill=(32, 36, 40))
        d.rectangle([0, int(H * 0.85), W, H], fill=(32, 36, 40))
        d.text((int(W * 0.1), int(H * 0.05)),
               "封面主字区（安全区内）",
               font=pick_font(int(W * 0.07)) or None, fill=(200, 200, 200))
        d.text((int(W * 0.1), int(H * 0.87)),
               "底部 15% 留空，别放字（平台 UI 遮挡）",
               font=pick_font(int(W * 0.045)) or None, fill=(150, 150, 150))
        p = os.path.join(out, "cover-template-%s.png" % plat)
        img.save(p)
        made.append(os.path.relpath(p, ROOT))
    return {"ok": True, "templates": made,
            "note": "用 decks 或修图软件在这两张底图上排版，主字占画面宽 70% 以上"}, 0


def main():
    ap = argparse.ArgumentParser(description="Vflow 封面 / 成片质检")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("cover"); p.add_argument("slug")
    p.add_argument("--preview", action="store_true", default=True)
    p.add_argument("--no-preview", dest="preview", action="store_false")
    p.set_defaults(fn=lambda a: cmd_run(a, cover=True))
    p = sub.add_parser("video"); p.add_argument("slug"); p.add_argument("--video")
    p.set_defaults(fn=lambda a: cmd_run(a, video=True))
    p = sub.add_parser("all"); p.add_argument("slug")
    p.add_argument("--preview", action="store_true", default=True)
    p.add_argument("--no-preview", dest="preview", action="store_false")
    p.add_argument("--video")
    p.set_defaults(fn=lambda a: cmd_run(a, cover=True, video=True,
                                        package=True))
    p = sub.add_parser("package"); p.add_argument("slug")
    p.set_defaults(fn=lambda a: cmd_run(a, package=True))
    p = sub.add_parser("template"); p.set_defaults(fn=cmd_template)

    args = ap.parse_args()
    result, code = args.fn(args)
    # 人读的输出走 stderr，stdout 留给脚本/工作台解析 JSON
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    sys.stderr.write("质检结束：%s\n" % (
        "通过" if code == 0 else "有未通过项（见 05-check.md）"))
    sys.exit(code)


if __name__ == "__main__":
    main()
