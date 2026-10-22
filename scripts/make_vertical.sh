#!/usr/bin/env bash
# 竖版视频生成入口（抖音 / 小红书 1080x1920）
# 因为上游 build_video.sh 默认 16:9，这里把录屏和字幕尺寸单独接管。
#
# 用法:
#   bash make_vertical.sh projects/<slug>/deck
#   bash make_vertical.sh projects/<slug>/deck --bgm path/to/music.mp3

set -euo pipefail

PROJECT="${1:-}"; shift || true
[[ -n "$PROJECT" ]] || { echo "usage: make_vertical.sh <project-dir> [--bgm path|synth]"; exit 2; }
PROJECT="$(cd "$PROJECT" && pwd)"

cd "$PROJECT"

PY="${VFLOW_PY:-/Users/v1/.workbuddy/binaries/python/envs/default/bin/python}"
SS="${VFLOW_HOME:-$HOME/Vflow}/skills/vflow-produce/scripts"
BGM="none"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bgm) BGM="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[[ -f "index.html" ]] || { echo "no index.html in $PROJECT" >&2; exit 1; }
[[ -f "narration.txt" ]] || { echo "no narration.txt in $PROJECT" >&2; exit 1; }

echo "=== tts + srt + timeline ==="
PY="$PY" bash "$SS/build_video.sh" . --tts edge --voice zh-CN-YunxiNeural --bgm none --only tts,srt,timeline

echo "=== record 9:16 ==="
$PY "$SS/deck_capture.py" video --project . --width 1080 --height 1920

AUDIO="audio/voice.wav"
if [[ "$BGM" != "none" ]]; then
  echo "=== mix bgm ==="
  bash "$SS/mix_bgm.sh" --voice audio/voice.wav --bgm "$BGM" --out audio/voice_with_bgm.wav
  AUDIO="audio/voice_with_bgm.wav"
fi

echo "=== compose vertical ==="
mkdir -p record final
LEAD=$($PY -c 'import json,sys; d=json.load(open(sys.argv[1])); print(max(0.0, round(float(d.get("recommended_lead_sec", 0)), 3)))' record/capture_meta.json)
AUDIO_DUR=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$AUDIO")
echo "lead=${LEAD}s audio=${AUDIO_DUR}s"

# trim the raw webm to the real audio clock, normalize to 30fps yuv420p
TRIMMED="record/aligned.mp4"
ffmpeg -y -hide_banner -loglevel error \
  -ss "$LEAD" -i record/animated_capture.webm -t "$AUDIO_DUR" \
  -vf "fps=30,format=yuv420p,tpad=stop_mode=clone:stop_duration=1" \
  -c:v libx264 -preset veryfast -crf 18 -an \
  "$TRIMMED"

# burn captions with vertical-safe params (240px bottom band)
VIDEO_TRACK="record/captioned.mp4"
$PY "$SS/render_captions.py" \
  --srt audio/voice.srt --project . --input "$TRIMMED" --output "$VIDEO_TRACK" \
  --width 1080 --height 1920 --font-size 44 --margin 240
bash record/burn_caps.sh

# mux final
OUT="final/deck.mp4"
ffmpeg -y -hide_banner -loglevel error \
  -i "$VIDEO_TRACK" -i "$AUDIO" \
  -map 0:v -map 1:a \
  -c:v copy -c:a aac -b:a 192k \
  -t "$AUDIO_DUR" -shortest \
  "$OUT"

echo "final: $OUT"
ffprobe -v error -show_entries format=duration:stream=codec_type,codec_name,width,height \
  -of default=nw=1 "$OUT"
