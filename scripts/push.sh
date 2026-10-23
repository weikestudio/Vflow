#!/usr/bin/env bash
# Vflow 一键推送
# 用途：绕过 macOS com.apple.provenance 扩展属性导致的 .git/*.lock 无法删除问题，
#       把本地提交推到 GitHub。在你自己的终端里跑（IDE 的 shell 走代理，github.com 不通）。
#
#   bash ~/Vflow/scripts/push.sh
#
set -e
cd "$(dirname "$0")/.."

# 1. 清锁文件（本目录里 git 自己删不掉，用 python 强删/挪走）
/usr/bin/python3 - <<'PY' 2>/dev/null || true
import os, glob
for f in glob.glob('/Users/v1/Vflow/.git/*.lock'):
    try: os.remove(f)
    except OSError:
        try: os.rename(f, '/tmp/vflow-%s' % os.path.basename(f))
        except OSError: pass
PY

# 2. remote（大小写与远端仓库名对齐）
REMOTE="https://github.com/weikestudio/Vflow.git"
if git remote | grep -qx origin; then
  git remote set-url origin "$REMOTE"
else
  git remote add origin "$REMOTE"
fi

# 3. 分支
git branch -M main

# 4. 推送
echo "推送到 $REMOTE ..."
if git push -u origin main; then
  echo
  echo "推送成功。查看：https://github.com/weikestudio/Vflow"
else
  echo
  echo "推送失败，通常是没登录。二选一："
  echo "  gh auth login --web        # 浏览器授权后重跑本脚本"
  echo "  或配 SSH：ssh-keygen -t ed25519 -C weikestudio && pbcopy < ~/.ssh/id_ed25519.pub"
  echo "  粘贴到 https://github.com/settings/keys 后："
  echo "  git remote set-url origin git@github.com:weikestudio/Vflow.git && git push -u origin main"
  exit 1
fi
