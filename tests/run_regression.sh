#!/usr/bin/env bash
# Vflow 一键回归。改脚本、改 skill、发布前都跑一遍。
# 用法: bash tests/run_regression.sh [--only state]
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
PY="${VFLOW_PY:-python3}"

echo "数据目录：$ROOT"
"$PY" - <<'EOF'
import sys
v = sys.version_info
if v < (3, 8):
    sys.exit("需要 Python 3.8+，当前 %d.%d" % v[:2])
print("Python %d.%d.%d" % v[:3])
EOF

# 先编译一遍，语法错误立即暴露
"$PY" -m py_compile "$ROOT"/scripts/*.py "$HERE"/runner.py || {
  echo "编译失败，先修语法" >&2
  exit 1
}

cd "$ROOT"
"$PY" "$HERE/runner.py" "$@"
code=$?

echo ""
if [ $code -eq 0 ]; then
  echo "== 回归通过 =="
else
  echo "== 回归失败（exit $code）==" >&2
fi
exit $code
