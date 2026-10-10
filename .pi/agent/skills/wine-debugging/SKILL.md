---
name: wine-debugging
description: 'Diagnose and fix a Windows .exe that crashes or silently exits under Wine/Proton on Linux (Unhandled page fault, EXCEPTION_PRIV_INSTRUCTION c0000096, "wine: could not load kernel32.dll", exit with no output). Covers new-WoW64 vs old-WoW64 triage, capturing +seh crash logs, reading the PE layout of packed/protected executables, and running a game standalone through Steam''s Proton. Use when wine/proton fails to launch a game with a 汉化/破解 loader, a DRM/packer-wrapped exe, or any legacy 32-bit program.'
---

# Wine / Proton crash debugging (Linux, 32-bit legacy games)

Goal: decide **whether the exe is broken or Wine is**, then hand back a launcher that works.

## 1. Triage (collect these first, in this order)

```bash
wine --version
pacman -Qi wine | grep -E "版本|Version|依赖于|Depends"   # or dpkg -l wine*
ls -d /usr/lib/wine/* /usr/lib32/wine/* 2>/dev/null       # WoW64 layout (see §2)
cd <gamedir> && WINEDEBUG=+seh wine '<game>.exe' > /tmp/w.log 2>&1; echo "exit=$?"
grep -a -cE "Unhandled|c0000096|c0000005" /tmp/w.log
grep -a -E "Unhandled|c0000096|c0000005" /tmp/w.log | head -5
```

Rules that save time:
- **Never** use `WINEDEBUG=+relay` for a crash: logs are hundreds of MB and `tail -c` misses the crash context. `+seh` is the right channel.
- `winedbg --auto` was removed in Wine 11 (prints a usage error). Use `+seh`.
- If the exe exits with **no** wine error at all, that is usually success plus a detached child, or a dialog waiting for input — check for stray processes with `pgrep -af <name>` before declaring failure.
- Reproduce with the *plain engine exe* as well as the loader (e.g. `SiglusEngine.exe` vs `Rewrite+汉化版.exe`). If both crash identically the patch/loader is not the cause.

## 2. new-WoW64 vs old-WoW64 — the #1 cause of "worked before / broken now"

```bash
ls /usr/lib/wine | grep -q i386-unix && echo "OLD WoW64" || echo "NEW WoW64"
```
- **NEW WoW64** (Wine ≥ 10, Arch `wine`): 32-bit PE runs in long-mode compat inside the 64-bit process. Layout: `i386-windows/`, `x86_64-unix/`, `x86_64-windows/`, **no `i386-unix`**, no lib32 deps. Signal logs show `cs=0033` and a 64-bit libc trampoline.
- **OLD WoW64** (Wine ≤ 9.x, all Proton builds): separate 32-bit loader. Layout has `lib/wine/i386-unix/ntdll.so`.

**Packed / DRM / anti-tamper executables frequently die on NEW WoW64** with a repeated `EXCEPTION_PRIV_INSTRUCTION (c0000096)` at many different addresses, then an unwind loop (`RtlUnwindEx` / `RtlRestoreContext` repeats), then exit. Symptoms that point here:
- Crash addresses land in the *last* section or a randomly named section (the packer's VM region), not in plausible game code.
- Dozens of *different* privileged-instruction addresses, each hit once.
- `IsBadReadPtr 0x?????? caused page fault` (deliberate bad-pointer probe = SEH anti-debug self-test).

Faithful fixes, best first:
1. **Run it with Proton** (old WoW64 + Valve's compat patches) — see §4. This is the standard answer and usually just works.
2. Install an old-WoW64 Wine (`wine` ≤ 9.x with lib32, AUR `wine-tkg`/`wine-ge`) into a dedicated prefix.
3. Report/vote the bug upstream with the `+seh` excerpt; do not promise a fix.

Do **not** claim `winetricks` overrides (`win7`, `nocrashdialog`, `wbemprox=...`, dll overrides) will help with this class — verify before suggesting, and say so if you only tried them unsuccessfully. Windows-version emulation is irrelevant: verify by running winxp/win7/win10 if in doubt (in the observed case all three crashed identically).

## 3. Read the PE before theorising

Run the bundled helper on the exe (stdlib only, no dependencies):

```bash
python3 <skill-dir>/scripts/pe-info.py '<game>.exe'
```

It prints ImageBase/EntryPoint/sections plus packer heuristics. Red flags for a protected/自解密 exe:
- 8-character random section names, or a section whose name is spaces/blanks.
- A section with a huge `VirtualSize` but ~0 raw size (uninitialized, filled at runtime).
- Entry point inside the **last** section.
- A section that itself contains an embedded `MZ`/`PE` (e.g. `.detour` holding a `skeleton.dll` image).
- Strings such as `skeleton.dll`, `.detour`, random-looking section names.

Also expect these in `+seh`/debug output — they are **normal** for protected exes and are *not* the crash cause by themselves:
- `fixme:ntdll:NtQuerySystemInformation info_class SYSTEM_PERFORMANCE_INFORMATION`
- `fixme:...:CreateToolhelp32Snapshot` unsupported-flag FIXME, `Heap32ListFirst` stub
- WMI queries (`SELECT ... FROM Win32_OperatingSystem`), `wbemprox`/`winmgmt` activity
- `err:ole:com_server_...` / `CoCreateInstance` errors at startup

Conversely, a game's own readme can be gold: if it lists "an enabled winmgmt/WMI service" and "no debugger running" as prerequisites for *not* crashing at startup, that confirms an anti-debug/anti-VM layer, i.e. this playbook.

## 4. Standalone Proton launcher (the reliable fix)

`scripts/proton-run.sh` in this skill is a ready generic launcher:

```bash
<skill-dir>/scripts/proton-run.sh '/path/to/game.exe' [game_dir] [proton_dir]
```

It does exactly what Steam does:

```bash
export STEAM_COMPAT_CLIENT_INSTALL_PATH="$HOME/.local/share/Steam"
export STEAM_COMPAT_DATA_PATH="$HOME/.local/share/<name>-proton"   # persistent, NOT /tmp
mkdir -p "$STEAM_COMPAT_DATA_PATH"
"$STEAM_DIR/steamapps/common/SteamLinuxRuntime_sniper/run" -- \
  "$PROTON/proton" run "$EXE"
```

Pitfalls observed (do not repeat these):
- **Must** go through `SteamLinuxRuntime_sniper/run`. Calling `Proton .../files/bin/wine` by hand (with hand-rolled `LD_LIBRARY_PATH`/`WINEDLLPATH`) fails with `wine: could not load kernel32.dll, status c0000135` — Wine then pops a modal error dialog, so `timeout` kills it after N seconds and it *looks* like "it ran without crashing". That false positive costs a lot of time.
- Without the runtime wrapper, `proton run` exits in ~2 s with only `wine: using kernel write watches ...` lines and writes **no** PROTON_LOG file.
- Keep `STEAM_COMPAT_DATA_PATH` outside `/tmp` so the prefix (registry, DXVK cache, game config) persists.
- Diagnose with `PROTON_LOG=1` (log lands in `$HOME/steam-*.log`); DXVK's swap-chain lines (`Presenter: Actual swap chain properties`, `D3D9Format`) are good evidence the game actually rendered.
- Check which Protons exist first: `ls ~/.local/share/Steam/steamapps/common | grep -i proton`.

### Systematic launcher: `~/.local/bin/winrun`

The user's machine has a general-purpose wrapper (also handy for any Windows exe, not just games):

```bash
winrun 'game.exe'                 # auto: Steam runtime + Proton (defaults to a wine-9 Proton for legacy compat)
winrun -p 10 'game.exe'           # pick another Proton (substring match)
winrun -w 'setup.exe'             # system wine backend (uses ~/.wine)
winrun -a 1144400 'game.exe'      # reuse Steam's compatdata/<appid> prefix via protontricks-launch
winrun -t cfg 'game.exe'          # winecfg inside that program's prefix (cfg|regedit|explorer|cmd|tricks|kill)
winrun -d 'game.exe'              # WINEDEBUG=+seh ; -d +relay for explicit channels
winrun --desktop -n 'Name' 'game.exe'   # also write a .desktop entry
winrun -l                         # list Protons + runtime + which wine each Proton uses
```

Per-program persistent prefixes live in `~/.local/share/winrun/<slug>` (never touches `~/.wine`).
It already implements every trap below (runtime wrapper, prefix reset, env plumbing), so prefer it over hand-rolling commands. `scripts/proton-run.sh` remains the minimal portable fallback.

### Proton prefixes: `tracked_files` trap (cost me a full round-trip)

- `proton runinprefix <cmd>` calls `init_session(False)` → **skips `setup_prefix()`**. If you use it on a *fresh* prefix, Wine creates `pfx/` but Proton's `tracked_files` is never written.
- A later `proton run` then dies with `Proton: Upgrading prefix from None to 9.0-203` followed by `FileNotFoundError: [Errno 2] No such file or directory: '<prefix>/tracked_files'` (traceback in `proton`, line ~1745 → `init_session` → `setup_prefix` → `update_builtin_libs`). That prefix is unusable for `run` from then on.
- `proton run` is what initializes a prefix (it writes `tracked_files` + `version`). So: **run the program once, then use `runinprefix` tools.**
- Detect/report a broken prefix with: `[ -d "$PREFIX/pfx" ] && [ ! -f "$PREFIX/tracked_files" ]`. Safe repair: `rm -rf "$PREFIX/pfx" "$PREFIX/version"` and let `proton run` rebuild it.

### Proton version choice is not interchangeable (verified on one packed game)

Same prefix content, same command, only the Proton changed:

| Proton | wine | result |
|---|---|---|
| `Proton 9.0 (Beta)` | wine-9.0 | works — log shows `info: Game: SiglusEngine.exe`, `info: Presenter: Actual swap chain properties`, `D3D9Format::X8R8G8B8`, and the game writes its own `savedata/window.ini` |
| `Proton 10.0` | wine-10.0 | first run: prefix upgrade then nothing; second run once initialized: **exit=0 after 20 s, zero output, zero DXVK lines** (silent early exit) |
| system `wine 11.18` | wine-11.18 | `c0000096` privileged-instruction loop (new WoW64) |

So when a legacy/packed title fails, try more than one Proton — and prefer the older wine-9-based one. Silent `exit=0` with no output is a **failure mode**, not success: only DXVK/wined3d swap-chain lines or the game writing its own config prove it actually rendered.

### Verifying a launch actually succeeded

- Capture stdout+stderr to a file and grep for rendering evidence: `Presenter: Actual swap chain properties`, `D3D9Format::`, `Game: <exe>`.
- Watch the game's own files: a title that started will rewrite its config/save files (`savedata/*.ini`, `*.sav`) — check mtimes before/after.
- `PROTON_LOG=1` did **not** produce any `~/steam-*.log` in these runs; do not depend on it — redirect the command's output instead (`winrun -L` also sets it, output still goes to stdout/stderr).
- The launcher may exit `0` while a child process keeps running: poll `ps -eo comm= | grep -c '^<Gamename>'` rather than trusting the exit code. (Beware `pgrep -af <name>` matching your own shell command line — that produced a false "the game is running" reading.)

Alternative with zero scripts: **Steam → Add a Non-Steam Game → the exe → Properties → force compatibility tool (Proton 9.0)**.

On success, deliver a launcher (script in `~/.local/bin/`, optionally a `.desktop` entry) and state clearly what changed and why. Only create a `.desktop` entry if the user asked for one.

## 5. Reporting a diagnosis (what the user needs)

State, with evidence, in this order: **root cause** → **verified fix** → **how to launch it from now on** → **side effects / caveats**. Include the literal error strings and the address/section facts that justify the cause, and explicitly list what you ruled out (loader, 汉化 patch, Windows version) — that is what stops the user from chasing the wrong thing. If something is still uncertain (e.g. which anti-tamper product, why exactly new WoW64 trips it), say so rather than guessing a vendor name.
