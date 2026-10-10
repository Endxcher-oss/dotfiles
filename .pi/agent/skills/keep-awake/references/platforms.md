# Platform APIs for sleep / screen inhibition

Legend: **[verified]** = actually exercised on a live machine while writing this skill
(Linux, logind 262, Plasma 6.7.5 / kwin, systemd-inhibit). **[docs]** = from the vendor API
documentation; correct to the best of knowledge but not executed here — test before relying on it.

---

## Linux — layer 1: logind (systemd / elogind)

The primary lock. Works regardless of desktop environment, no portal needed, and its lifetime is tied
to a file descriptor, so a crashed client cannot leave a stale inhibitor. **[verified]**

```
org.freedesktop.login1 (system bus)
  /org/freedesktop/login1
  org.freedesktop.login1.Manager
    Inhibit(in s what, in s who, in s why, in s mode, out h fd)
```

- `what` — colon-separated subset of `shutdown`, `sleep`, `idle`, `handle-power-key`,
  `handle-suspend-key`, `handle-hibernate-key`, `handle-lid-switch`. Pass only what the requirement
  needs; `sleep` is the usual answer for "don't suspend".
- `mode` — `block` (honoured), `block-weak` (same, but ignored for the user owning the lock),
  `delay` (the operation is postponed by up to `InhibitDelayMaxUSec`, default **5 s** = 5000000 µs
  **[verified]**, so the client can save state).
- Return value is a D-Bus `h` (unix fd). **The lock exists exactly while that fd — and every
  duplicate of it — stays open.** Close it to release. `SIGKILL` of the client therefore releases the
  lock automatically. **[verified]**
- polkit actions: `org.freedesktop.login1.inhibit-block-sleep`, `inhibit-delay-sleep`,
  `inhibit-block-idle`, `inhibit-block-shutdown`, `inhibit-handle-*`. Allowed by default for local
  active sessions (**[docs]**).
- Manager properties: `BlockInhibited`, `BlockWeakInhibited`, `DelayInhibited` (each a
  colon-separated `shutdown:sleep:idle` list), `InhibitDelayMaxUSec`. **[verified]**
- `ListInhibitors(out a(ssssuu))` → `(what, who, why, mode, uid, pid)`. **[verified]**
- Signal `PrepareForSleep(bool)` — for `mode=delay` clients. **[docs]**
- systemd ≥ 257: a `block` inhibitor is honoured for privileged requesters as well; older versions
  applied it only to unprivileged requesters other than the lock owner, which is the behaviour
  `block-weak` still has. **[docs]**
- elogind exposes the same API, so a program supporting both needs no extra branch.

```bash
# probe permissions without holding anything (the fd closes with the process)
dbus-send --system --print-reply --dest=org.freedesktop.login1 /org/freedesktop/login1 \
  org.freedesktop.login1.Manager.Inhibit string:sleep string:"$USER probe" string:probe string:block

# the honest way to hold the lock for a shell command
systemd-inhibit --what=sleep --who="$USER rsync" --why="copying photos" --mode=block rsync -a src/ dst/
systemd-inhibit --list --no-pager     # who is holding what, right now
```

A one-shot `desktop`-style call (`dbus-send`, `gdbus call`, `busctl call`) **cannot** hold a logind
lock: the fd is closed when that short-lived process exits, so the inhibitor disappears immediately.
Use `systemd-inhibit` or hold a persistent connection in your own process. **[verified]**

## Linux — layer 2: desktop screensaver interfaces

Only needed when the **screen** must stay on, or when logind is not available. These stop blanking
and the idle-driven screen lock; on some desktops they also stop idle suspend.

| Interface | Signature | Notes |
|---|---|---|
| `org.freedesktop.ScreenSaver` @ `/ScreenSaver` or `/org/freedesktop/ScreenSaver` | `Inhibit(s app_name, s reason) → u cookie`, `UnInhibit(u cookie)` | The classic one. kwin implements it **[verified]**; GNOME and most others do too **[docs]**. |
| `org.gnome.SessionManager` @ `/org/gnome/SessionManager` | `Inhibit(s app_id, u toplevel_xid, s reason, u flags) → u`, `Uninhibit(u)`, `IsInhibited(u flags) → b` | flags: `1` logout, `2` user switch, `4` suspend, `8` idle **[docs]** |
| `org.freedesktop.PowerManagement` @ `/org/freedesktop/PowerManagement/Inhibit` | `Inhibit(s app, s reason) → u`, `UnInhibit(u)` | Legacy; PowerDevil still exports it **[verified]** |
| `org.kde.Solid.PowerManagement.PolicyAgent` | `AddInhibition(u types, s who, s why) → u`, `ReleaseInhibition(u)`, `HasInhibition(u) → b` | KDE-private. **`1` = InterruptSession (suspend), `4` = ChangeScreenSettings (dim/blank)** **[verified]** — see `desktop-internals.md` before using it. |

### Sandboxed apps (Flatpak / Snap / portals)

```
org.freedesktop.portal.Desktop
  org.freedesktop.portal.Inhibit(window s, flags u) -> o request_handle
```
flags: `1` logout, `2` user switch, `4` suspend, `8` idle. **Release by letting the returned request
handle be closed/disposed** — there is no explicit un-inhibit call. The portal proxies to whatever the
session actually uses (on KDE that ends up as a PowerDevil `AddInhibition`) **[verified from the portal
XML and the PowerDevil source]**. It also shows a user-visible "blocking" indicator, which is the
correct, policy-respecting route for sandboxed apps; a Flatpak can otherwise be granted
`--talk-name=org.freedesktop.login1`.

### X11 / Wayland / SDL

- X11: `XScreenSaverSuspend(display, True/False)` (MIT-SCREEN-SAVER), or `SDL_DisableScreenSaver()`
  **[docs]**. Legacy, still works for X11 sessions.
- Wayland: **no core protocol for this.** Use logind or the portal — that is the whole reason the
  D-Bus path is the right default. **[verified: no such protocol; every DE routes to D-Bus]**
- Do **not** fake user activity (`xdotool`, `ydotool`, FakeInput) to defeat a screensaver: it also
  defeats screen locking, which is a security regression.

---

## macOS **[docs]**

```c
#include <IOKit/pwr_mgt/IOPMLib.h>

IOPMAssertionID id;
IOPMAssertionCreateWithName(kIOPMAssertionTypeNoIdleSleep,       /* or ...NoDisplaySleep */
                            kIOPMAssertionLevelOn,
                            CFSTR("cmus: playing audio"), &id);
...
IOPMAssertionRelease(id);          /* also released if the process dies */
```

- Newer spellings: `kIOPMAssertionTypePreventUserIdleSystemSleep` and
  `...PreventUserIdleDisplaySleep` (10.9+), same behaviour.
- `kIOPMAssertionTypeNoIdleSleep` alone lets the display sleep and lock — use it unless the screen
  must stay on.
- `IOPMAssertionDeclareUserActivity(name, kIOPMUserActiveLocal, &id)` resets the idle timer without
  taking a permanent assertion (the equivalent of "I am being used").
- Assertions are per-process and vanish on exit; there is no stale-lock problem.
- CLI: `caffeinate -i <cmd>` (prevent idle sleep), `-d` (display), `-m` (disk), `-s` (system, only
  while on AC), `-u` (declare user active), `-t <sec>` (timeout), `-w <pid>` (until that pid exits).
- Verify with `pmset -g assertions` — it lists the assertion name and the owning process.

## Windows **[docs]**

```c
SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED);          /* keep awake, screen may off */
SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED);
SetThreadExecutionState(ES_CONTINUOUS);                               /* release */
```

- The state is **per-thread**; it stays in force while that thread lives (that is what `ES_CONTINUOUS`
  means) and is cleared when the thread exits. Call it from a long-lived thread, not a worker that
  returns.
- Modern replacement: `PowerCreateRequest` + `PowerSetRequest(handle, PowerRequestSystemRequired |
  PowerRequestDisplayRequired | PowerRequestExecutionRequired)`, released by closing the handle
  (so again a dying process cannot leak the lock). `PowerRequestExecutionRequired` (Win8+) is the
  app-scoped "my background work must finish" request.
- Media playback in UWP/WinRT uses `Windows.System.Display.DisplayRequest` (per-request object).
- Verify with `powercfg /requests` (live) and `powercfg /energy` (report over time).

---

## Which name answers on a typical Linux session

Collected from `busctl --user list` on a Plasma 6 / Wayland session **[verified]**:

```
org.freedesktop.ScreenSaver            kwin_wayland     -> present (the one kwin reads)
org.kde.screensaver                    kwin_wayland     -> present
org.kde.Solid.PowerManagement          org_kde_powerdevil -> PowerDevil PolicyAgent lives here
org.freedesktop.PowerManagement        org_kde_powerdevil -> legacy inhibit interface
org.gnome.ScreenSaver                  (absent on KDE)
org.freedesktop.portal.Desktop         -> present (xdg-desktop-portal, for sandboxed apps)
```

`<skill-dir>/scripts/check-inhibit.sh` prints exactly this, plus the live inhibition state.
