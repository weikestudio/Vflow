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
root = os.getcwd()          # 本脚本已 cd 到仓库根
for f in glob.glob(os.path.join(root, '.git', '*.lock')):
    try: os.remove(f)
    except OSError:
        try: os.rename(f, '/tmp/vflow-%s' % os.path.basename(f))
        except OSError: pass
PY

# 2. remote（大小写与远端仓库名对齐）
REMOTE="https://github.com/weikestudio/vflow.git"
if git remote | grep -qx origin; then
  git remote set-url origin "$REMOTE"
else
  git remote add origin "$REMOTE"
fi

# 3. 分支
git branch -M main

# 4. 推送（分支 + 标签）
echo "推送到 $REMOTE ..."
if git push -u origin main --follow-tags; then
  echo
  echo "推送成功。查看：https://github.com/weikestudio/vflow"
elif git fetch -q origin main 2>/dev/null && git push --force-with-lease origin main --follow-tags; then
  echo
  echo "本地历史与远端分叉（远端是网页手动上传的单次提交），已用本地完整历史覆盖。"
  echo "查看：https://github.com/weikestudio/vflow"
else
  echo
  echo "推送失败。先确认是哪一类问题："
  echo "  连接层（CONNECT tunnel failed / Operation timed out）→ 网络或代理，换网络再试"
  echo "  认证层（Authentication failed / could not read Username）→ 没登录，二选一："
  echo "    gh auth login --web        # 浏览器授权后重跑本脚本"
  echo "    或配 SSH：ssh-keygen -t ed25519 -C weikestudio && pbcopy < ~/.ssh/id_ed25519.pub"
  echo "    粘贴到 https://github.com/settings/keys 后："
  echo "    git remote set-url origin git@github.com:weikestudio/Vflow.git && git push -u origin main"
  echo "  非快进（rejected / non-fast-forward）→ 本地与远端历史分叉，确认本地是最新后："
  echo "    git push --force-with-lease origin main"
  exit 1
fi
