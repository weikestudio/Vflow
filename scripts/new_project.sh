#!/usr/bin/env bash
# 开一条新视频项目
# 用法: bash ~/Vflow/scripts/new_project.sh "选题短名"
# 例:   bash ~/Vflow/scripts/new_project.sh "ai-skill-不露脸"

set -euo pipefail

STUDIO="${VFLOW_HOME:-$HOME/Vflow}"
NAME="${1:-}"
PY="${VFLOW_PY:-python3}"

if [ -z "$NAME" ]; then
  echo "用法: new_project.sh \"选题短名\""
  exit 1
fi

SLUG="$(date +%Y%m%d)-${NAME}"
DIR="$STUDIO/projects/$SLUG"

if [ -d "$DIR" ]; then
  echo "已存在: $DIR"
  exit 1
fi

mkdir -p "$DIR"/{assets,output,deck}

for f in "$STUDIO"/pipeline/*.md; do
  cp "$f" "$DIR/$(basename "$f")"
done

cat > "$DIR/README.md" <<EOF
# $NAME

- 创建: $(date +%Y-%m-%d)
- 状态: 选题中

## 进度

- [ ] 01 选题
- [ ] 02 结构
- [ ] 03 剧本
- [ ] 03b 提词稿（露脸才需要）
- [ ] 04 包装
- [ ] 05 检查
- [ ] 06 制作
- [ ] 07 复盘
EOF

# 立刻写状态文件，并把选题池里同名条目转成「在做」
VFLOW_HOME="$STUDIO" "$PY" "$STUDIO/scripts/vflow_state.py" init "$SLUG" >/dev/null 2>&1 || true
if [ -f "$STUDIO/scripts/backlog.py" ] && [ -f "$STUDIO/backlog.md" ]; then
  VFLOW_HOME="$STUDIO" "$PY" "$STUDIO/scripts/backlog.py" start "$NAME" \
    --slug "$SLUG" >/dev/null 2>&1 || true
fi
# 排期里如果有同名条目，标成「已排」（不递归调用 calendar.py start）
if [ -f "$STUDIO/scripts/content_calendar.py" ] && [ -f "$STUDIO/calendar.md" ]; then
  VFLOW_HOME="$STUDIO" "$PY" - "$STUDIO" "$NAME" "$SLUG" <<'PYEOF' >/dev/null 2>&1 || true
import sys, os
root, name, slug = sys.argv[1:4]
sys.path.insert(0, os.path.join(root, "scripts"))
import content_calendar as C
series, plans = C.parse()
for p in plans:
    if p["title"] == name and p["status"] == "待做":
        p["status"] = "已排"
        p["slug"] = slug
        C.save(series, plans)
        break
PYEOF
fi

echo "✅ 项目已创建: $DIR"
echo ""
ls -1 "$DIR"
echo ""
echo "下一步：跟 AI 说做选题，项目 ${SLUG}，或自己填 01-topic.md"
