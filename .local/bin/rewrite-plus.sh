#!/usr/bin/env bash
# 用 Steam 的 Proton 9 (wine 9.0 / 旧 WoW64) 启动 Rewrite+
# 原因：系统 wine 11.x 的“新 WoW64”跑不了这个游戏的壳(会 c0000096 特权指令异常崩掉)
# 用法: rewrite-plus.sh [可执行文件]   默认启动 汉化版
set -euo pipefail

STEAM_DIR="${STEAM_DIR:-$HOME/.local/share/Steam}"
GAME_DIR="${GAME_DIR:-$HOME/Downloads/Rewrite_PLUS}"
EXE="${1:-Rewrite+汉化版.exe}"

# 优先 Proton 9.0 (Beta)，其次 Proton 10.0，再其次 Proton Hotfix
for cand in "Proton 9.0 (Beta)" "Proton 10.0" "Proton Hotfix" "Proton - Experimental"; do
    [ -x "$STEAM_DIR/steamapps/common/$cand/proton" ] && PROTON="$STEAM_DIR/steamapps/common/$cand" && break
done
[ -n "${PROTON:-}" ] || { echo "找不到可用的 Proton，请确认 Steam 已安装 Proton" >&2; exit 1; }

export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_DIR"
export STEAM_COMPAT_DATA_PATH="${STEAM_COMPAT_DATA_PATH:-$HOME/.local/share/rewrite-plus-proton}"
mkdir -p "$STEAM_COMPAT_DATA_PATH"

cd "$GAME_DIR"
echo "使用 Proton: $PROTON"
exec "$STEAM_DIR/steamapps/common/SteamLinuxRuntime_sniper/run" -- "$PROTON/proton" run "$EXE"
