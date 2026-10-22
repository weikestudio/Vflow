#!/usr/bin/env bash
# 开一条新视频项目
# 用法: bash ~/Vflow/scripts/new_project.sh "选题短名"
# 例:   bash ~/Vflow/scripts/new_project.sh "ai-skill-不露脸"

set -euo pipefail

STUDIO="${VFLOW_HOME:-$HOME/Vflow}"
NAME="${1:-}"

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

echo "✅ 项目已创建: $DIR"
echo ""
ls -1 "$DIR"
echo ""
echo "下一步：跟 AI 说做选题，项目 ${SLUG}，或自己填 01-topic.md"
