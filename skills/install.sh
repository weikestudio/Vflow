#!/usr/bin/env bash
# Vflow skill installer — 把 Vflow 技能集合装进各个 Agent 的技能目录。
#
# 用法：
#   bash install.sh                      # 装进所有已存在的宿主目录
#   bash install.sh workbuddy claude     # 只装指定的
#   bash install.sh all                  # 装进所有已知目录（不管存不存在，会创建）
#   bash install.sh --link claude        # 用软链而不是复制
#   bash install.sh --list               # 看有哪些目标、当前状态
#
# 目标：workbuddy · claude · codex · doubao · doubao-work · gemini · agents
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="$HERE"
LINK=0

declare -a NAMES=(vflow vflow-topic vflow-outline vflow-script vflow-package vflow-check vflow-produce vflow-review)

target_dir() {
  case "$1" in
    workbuddy)  echo "$HOME/.workbuddy/skills" ;;
    claude)     echo "$HOME/.claude/skills" ;;
    codex)      echo "$HOME/.codex/skills" ;;
    doubao)     echo "$HOME/Doubao/skills" ;;
    doubao-work) echo "$HOME/.doubao-work/skills" ;;
    gemini)     echo "$HOME/.gemini/skills" ;;
    agents)     echo "$HOME/.agents/skills" ;;
    *) return 1 ;;
  esac
}

ALL_TARGETS=(workbuddy claude codex doubao doubao-work gemini agents)

list_targets() {
  printf "%-12s %-8s %s\n" TARGET STATUS DIR
  for t in "${ALL_TARGETS[@]}"; do
    d="$(target_dir "$t")"
    if [[ -d "$d" ]]; then
      if [[ -d "$d/vflow" ]]; then s="已安装"; else s="目录存在"; fi
    else
      s="未创建"
    fi
    printf "%-12s %-8s %s\n" "$t" "$s" "$d"
  done
}

install_to() {
  local t="$1" d
  d="$(target_dir "$t")" || { echo "未知目标: $t" >&2; return 1; }
  mkdir -p "$d"
  local n=0
  for name in "${NAMES[@]}"; do
    [[ -d "$SKILLS_DIR/$name" ]] || { echo "  跳过 ${name}（源不存在）"; continue; }
    rm -rf "$d/$name"
    if [[ $LINK == 1 ]]; then
      ln -s "$SKILLS_DIR/$name" "$d/$name"
    else
      cp -R "$SKILLS_DIR/$name" "$d/$name"
    fi
    n=$((n+1))
  done
  # _shared 给各子 skill 读（profile 模板）
  if [[ -d "$SKILLS_DIR/_shared" ]]; then
    rm -rf "$d/vflow-shared"
    if [[ $LINK == 1 ]]; then ln -s "$SKILLS_DIR/_shared" "$d/vflow-shared"
    else cp -R "$SKILLS_DIR/_shared" "$d/vflow-shared"; fi
  fi
  echo "  ✓ $t → $d （$n 个 skill）"
}

# ── 解析参数 ──
TARGETS=()
EXPLICIT=0
for arg in "$@"; do
  case "$arg" in
    --link) LINK=1 ;;
    --list) list_targets; exit 0 ;;
    all) TARGETS=("${ALL_TARGETS[@]}"); EXPLICIT=1 ;;
    -h|--help) sed -n '2,16p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) TARGETS+=("$arg"); EXPLICIT=1 ;;
  esac
done

if [[ ${#TARGETS[@]} -eq 0 ]]; then
  # 自动模式：只装进已经存在的宿主目录，不在机器上乱建目录
  for t in "${ALL_TARGETS[@]}"; do
    [[ "$t" == "agents" ]] && continue
    [[ -d "$(target_dir "$t")" ]] && TARGETS+=("$t")
  done
  [[ ${#TARGETS[@]} -eq 0 ]] && { echo "没找到任何已存在的 Agent 技能目录，用 'bash install.sh all' 强制安装。"; exit 1; }
fi

echo "Vflow 安装 —— 源目录: ${SKILLS_DIR}"
for t in "${TARGETS[@]}"; do
  d="$(target_dir "$t")" || { echo "未知目标: $t" >&2; continue; }
  if [[ $EXPLICIT == 0 && ! -d "$d" ]]; then
    echo "  · $t 目录不存在，跳过（先装对应的 Agent 再跑）"
    continue
  fi
  install_to "$t"
done

echo
echo "装完。新装的 skill 在部分客户端需要重启会话或手动信任后才生效。"
echo "数据目录默认 ~/Vflow/，可用环境变量 VFLOW_HOME 覆盖。"
