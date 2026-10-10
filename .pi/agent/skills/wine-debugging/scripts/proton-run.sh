#!/usr/bin/env bash
# Launch a Windows executable through Steam's Proton + Steam Linux Runtime.
# Usage: proton-run.sh <exe> [game_dir] [proton_dir]
#   exe        path to .exe (absolute, or relative to game_dir/cwd)
#   game_dir   directory to run from (default: dirname of exe)
#   proton_dir Proton install dir (default: first of Proton 9.0/10.0/Hotfix/Experimental)
# Env:
#   STEAM_DIR (default ~/.local/share/Steam)
#   STEAM_COMPAT_DATA_PATH (default ~/.local/share/proton-<exe base name>)
#   PROTON_LOG=1 to write $HOME/steam-*.log
set -euo pipefail

[ $# -ge 1 ] || { echo "usage: $0 <exe> [game_dir] [proton_dir]" >&2; exit 2; }

EXE="$1"
GAME_DIR="${2:-$(dirname "$(realpath "$EXE")")}"
STEAM_DIR="${STEAM_DIR:-$HOME/.local/share/Steam}"
COMMON="$STEAM_DIR/steamapps/common"

if [ $# -ge 3 ]; then
    PROTON="$3"
else
    for cand in "Proton 9.0 (Beta)" "Proton 10.0" "Proton Hotfix" "Proton - Experimental"; do
        if [ -x "$COMMON/$cand/proton" ]; then PROTON="$COMMON/$cand"; break; fi
    done
fi
[ -n "${PROTON:-}" ] && [ -x "$PROTON/proton" ] || { echo "no usable Proton found under $COMMON" >&2; exit 3; }

RUNTIME="$COMMON/SteamLinuxRuntime_sniper/run"
[ -x "$RUNTIME" ] || { echo "missing Steam Linux Runtime: $RUNTIME" >&2; exit 4; }

export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_DIR"
export STEAM_COMPAT_DATA_PATH="${STEAM_COMPAT_DATA_PATH:-$HOME/.local/share/proton-$(basename "${EXE%.*}")}"
mkdir -p "$STEAM_COMPAT_DATA_PATH"

cd "$GAME_DIR"
echo "proton : $PROTON"
echo "exe    : $EXE"
echo "prefix : $STEAM_COMPAT_DATA_PATH"
exec "$RUNTIME" -- "$PROTON/proton" run "$(basename "$EXE")"
