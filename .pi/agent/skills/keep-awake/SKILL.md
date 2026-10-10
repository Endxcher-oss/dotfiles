---
name: keep-awake
description: 'Keep a machine from suspending / going to sleep / blanking the screen while work is in progress (playing media, long downloads, builds, presentations, dashboards), and debug why an idle suspend or screen blank still happens. Covers the logind Inhibit() fd lock, org.freedesktop.ScreenSaver, org.gnome.SessionManager, xdg-desktop-portal Inhibit, systemd-inhibit, kwin/PowerDevil/gnome-session internals, macOS IOPMAssertion/caffeinate and Windows SetThreadExecutionState/PowerRequest. Use for sleep inhibit, wake lock, 阻止睡眠, 阻止息屏, 不要休眠, "为什么还在挂起/还在锁屏", "caffeinate", "keep the display on".'
---

# Keeping the machine awake (sleep / screen inhibition)

Goal: pick the **smallest lock that satisfies the requirement**, verify it at the right layer,
and never leave a lock behind when the work stops or the process dies.

## 0. Decide first: which inhibition do you actually want?

"Don't sleep" and "don't blank the screen" are different locks with different side effects. Getting
this wrong is the #1 cause of "it works, but the screen never locks" and of "the screen stays on
but it sleeps anyway".

| Requirement | Take this | Side effects to accept |
|---|---|---|
| No suspend while busy; screen may blank and lock normally | logind `what="sleep"`, `mode="block"` | none |
| Screen must stay on as well (video, presentation, dashboard) | logind `what="sleep:idle"` **plus** a desktop screen lock (`ScreenSaver.Inhibit`, GNOME flag 8, portal flag 8) | screen will not blank **or lock** |
| Sandboxed / Flatpak / portal-only app | `org.freedesktop.portal.Inhibit` flags `4` (suspend) / `8` (idle) | portal shows a "blocking" indicator |
| Only for the duration of one shell command | `systemd-inhibit --what=sleep --who=… --why=… --mode=block <cmd>` | none |
| Must save state before suspend | `mode="delay"` + watch `PrepareForSleep` | must release within `InhibitDelayMaxUSec` (default 5s) |
| macOS / Windows | `IOPMAssertion` / `SetThreadExecutionState` or `PowerRequest` | see `references/platforms.md` |

**Rule of thumb:** request `sleep` **only**, unless the user explicitly asked for the display to stay
on. `sleep:idle` is not "sleep, but stronger" — it also stops the session from ever counting as idle,
which is exactly what blanking and locking are driven by.

## 1. Linux: the two calls that matter

```bash
# what is holding the machine awake right now
systemd-inhibit --list
busctl get-property org.freedesktop.login1 /org/freedesktop/login1 \
       org.freedesktop.login1.Manager BlockInhibited

# hold a sleep lock around a command (the only sane shell-level way)
systemd-inhibit --what=sleep --who="$USER script" --why="long download" \
                --mode=block rsync -a src/ dst/
```

From C: `Inhibit(what, who, why, mode)` on `org.freedesktop.login1.Manager` returns a **file
descriptor**; the lock lives exactly as long as that fd (and its duplicates) stays open. That is the
whole lifecycle management — closing it releases the lock, so even `SIGKILL` cannot leave a stale
inhibitor behind. Use `<skill-dir>/scripts/inhibit.c` (a tested implementation, drop-in beside
`inhibit.h`); it takes the logind lock and falls back to `org.freedesktop.ScreenSaver` only when
logind is absent.

```bash
# build-check the bundled implementation
gcc -DCONFIG_INHIBIT -std=gnu11 -Wall -Wextra -Werror \
    $(pkg-config --cflags libsystemd) -c <skill-dir>/scripts/inhibit.c
```

`Inhibit()` arguments (from `man org.freedesktop.login1`):
- `what` — colon-separated subset of `shutdown`, `sleep`, `idle`, `handle-power-key`,
  `handle-suspend-key`, `handle-hibernate-key`, `handle-lid-switch`.
- `mode` — `block`, `block-weak` (ignored for the user owning the lock), or `delay`
  (operation is postponed by up to `InhibitDelayMaxUSec` so you can save data).
- polkit actions are `org.freedesktop.login1.inhibit-block-sleep`, `inhibit-delay-sleep`,
  `inhibit-block-idle`, `inhibit-handle-*`; allowed by default for local active sessions.
- Since systemd 257 a `block` lock is honoured for privileged requesters too; before that only
  unprivileged requesters other than the lock owner were blocked, which is what `block-weak` keeps.

**Do not** try to hold a lock with a one-shot `dbus-send` / `gdbus call`: the returned fd is closed
when that process exits, so the lock is gone immediately. Those are useful for probing permissions
only.

## 2. Verify — at the layer that actually decides

Checking that your own call succeeded proves nothing about whether the desktop honours it.
`<skill-dir>/scripts/check-inhibit.sh` prints every layer at once; `--watch [secs]` polls once a
second, which is how you catch enforcement delays:

```bash
<skill-dir>/scripts/check-inhibit.sh
<skill-dir>/scripts/check-inhibit.sh --watch 20     # take the lock while this runs
```

- Linux/logind: `sleep`/`idle` must appear in `BlockInhibited` **immediately**.
- KDE Plasma: `InterruptSession` is the gate for "suspend after N minutes of idle". **PowerDevil
  enforces a newly taken inhibition about 5 s after the fact** — a check made earlier reports
  uninhibited and will make you believe the lock is ignored. Release is visible within ~1 s.
- GNOME: `org.gnome.SessionManager.IsInhibited(flags)`, `4` = suspend, `8` = idle.
- Never present "the function returned success" as evidence the machine stays awake. Finish with the
  user-visible test: set a short idle-suspend timeout (1–2 min), leave it idle, watch what happens.

## 3. Traps that have already burned real time

- **KDE mis-mapping.** PowerDevil maps logind `sleep` → `InterruptSession` (the suspend gate) and
  `idle` → `ChangeScreenSettings` (dim/blank), and *`ChangeScreenSettings` implies `InterruptSession`
  internally* (`daemon/powerdevilpolicyagent.cpp:718-722`). So on KDE `idle` and `sleep:idle` behave
  identically, and `sleep` is the only one that leaves the screen alone.
- **The 5 s delay.** Detailed table and the measurement recipe: `references/desktop-internals.md`.
- **kwin only reads `org.freedesktop.ScreenSaver`.** Taking that lock also suppresses blanking and
  locking — never take it "just to be sure" on top of logind.
- **In KDE, lid and power-button suspend are not gated at all**: only `SuspendSession::onIdleTimeout()`
  (`daemon/actions/bundled/suspendsession.cpp:65`) consults `InterruptSession`; `triggerImpl()`
  (`suspendsession.cpp:78-130`) suspends directly. So this technique blocks *idle* suspend only.
- **Do not fake user activity** with `xdotool`/FakeInput to defeat the screensaver: it also defeats
  screen locking. Take a real inhibitor.
- Release the lock when the work stops (pause/stop/exit), not at program exit only. Hold nothing
  while idle: users hate a machine that neither plays music nor sleeps.

Full API-level notes per platform (Linux DEs, portals, X11/SDL, macOS, Windows) are in
`references/platforms.md`; DE internals, the PowerDevil source map and the debugging cookbook are in
`references/desktop-internals.md`.
