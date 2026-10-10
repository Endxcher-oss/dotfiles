# Desktop internals: who actually acts on an inhibitor

Why "take a logind `sleep` lock" is not automatically "the machine will stay awake": on Linux the
desktop's own power daemon decides, and it may consult logind, its own state, or nothing at all.

---

## KDE Plasma: PowerDevil is the gate

Two processes matter **[verified on Plasma 6.7.5]**:

- `org_kde_powerdevil` — owns `org.kde.Solid.PowerManagement` and the `PolicyAgent` object.
  It decides whether an action may run, and it is the only thing that reacts to logind inhibitors.
- `kwin_wayland` — owns `org.freedesktop.ScreenSaver` and does the blanking / locking. It does **not**
  look at logind at all (see below).

### Policy types

```cpp
// powerdevilpolicyagent.h:83-87
enum RequiredPolicy { None = 0, InterruptSession = 1, ChangeScreenSettings = 4 };
```

- `InterruptSession` (1) — "the session may be interrupted": the gate for **suspend**.
- `ChangeScreenSettings` (4) — "the screen settings may be changed": the gate for **dim / blank / DPMS**.

### How logind `what` maps into those

```cpp
// powerdevilpolicyagent.cpp:423-436
PolicyAgent::RequiredPolicies PolicyAgent::policiesInLogindWhat(const QString &what) const {
    const auto types = what.split(QLatin1Char(':'));
    RequiredPolicies policies{};
    if (types.contains("sleep"_L1)) { policies |= InterruptSession; }        // sleep -> suspend gate
    if (types.contains("idle"_L1))  { policies |= ChangeScreenSettings; }    // idle  -> screen gate
    return policies;
}
```

And in `addInhibitionTypeHelper()` (6.7.5: lines **718-722**):

```cpp
if (types & ChangeScreenSettings) {
    // keep the screen on also implies preventing the session from being interrupted
    types |= InterruptSession;
}
```

**Consequence:** on KDE, `idle` is the *stronger* lock — it stops blanking **and** suspend (and, via
`unavailablePolicies()`, is ignored while the screen locker is active). `sleep` is the minimal lock:
it stops idle-triggered suspend and leaves blanking/locking alone. This is the reason a music player
must ask for **`sleep` only** if it wants the screen to keep locking normally.

### Who consumes the policies

| Consumer | Policy | File |
|---|---|---|
| `SuspendSession::onIdleTimeout()` | `requirePolicyCheck(InterruptSession)` | `daemon/actions/bundled/suspendsession.cpp:65` |
| `SuspendSession` constructor | `setRequiredPolicies(InterruptSession)` | `suspendsession.cpp:38` |
| `DPMS` action | `ChangeScreenSettings` | `daemon/actions/bundled/dpms.cpp:49,67,210` |
| `DimDisplay` action | `ChangeScreenSettings` | `daemon/actions/bundled/dimdisplay.cpp:30,36,122` |
| `RunScript` action | `ChangeScreenSettings` | `daemon/actions/bundled/runscript.cpp:23` |
| freedesktop D-Bus inhibit connector (apps) | `InterruptSession` | `daemon/powerdevilfdoconnector.cpp:81,89,91,112` |
| PowerDevil's own internal use | both | `daemon/powerdevilcore.cpp:398,409` |

**The idle path is the only gated one** — `SuspendSession::onIdleTimeout()` checks the policy, while
`triggerImpl()` (the lid switch / power button / explicit suspend path, ~`suspendsession.cpp:78-130`)
suspends with no policy check. So no inhibitor of any kind stops a lid-close or power-button suspend
in Plasma; only the *idle* suspend and blanking are up for negotiation. **[verified by source]**

`unavailablePolicies()` additionally reports `ChangeScreenSettings` as unavailable while the screen
locker is active — "keeping the screen on is pointless while locked".

### How PowerDevil learns about logind inhibitors

- It calls `ListInhibitors()` and imports every entry with `mode == "block"`, mapping `what` through
  `policiesInLogindWhat()`, skipping ones it already knows (`m_logindInhibitions`), then
  `AddInhibition(policies, who, why)`. Removed entries release the cookie. **[verified:
  `checkLogindInhibitions()`, ~`powerdevilpolicyagent.cpp:505-530`]**
- It re-checks only when the `BlockInhibited` property changes
  (`onManagerPropertyChanged()`, same file) — i.e. it is driven by logind notifications, not a poll
  of your process. If you take a logind lock, logind *must* be the one you talk to; talking only to
  PowerDevil directly (the `PolicyAgent` API) is the alternative route.
- `setupSystemdInhibition()` takes a permanent
  `handle-power-key:handle-suspend-key:handle-hibernate-key:handle-lid-switch` block lock as
  "PowerDevil / KDE handles power events" — that is why those names are normally present in
  `BlockInhibited` on a Plasma box. **[verified]**

### Measured enforcement timing

`<skill-dir>/scripts/check-inhibit.sh --watch` with a holder that takes a logind `sleep` lock for 12s
**[verified, twice, Plasma 6.7.5]**:

| t | logind `BlockInhibited` | PowerDevil `HasInhibition(1)` |
|---|---|---|
| lock taken (t=0) | contains `sleep` | `no` |
| t ≈ 5.0–5.3 s | `sleep` | **`yes`** |
| release (t=12s) | `sleep` gone within the same second | `no` within ~1 s |

So: **PowerDevil honours logind inhibitors, but only ~5 s after they are taken.** Any check done
earlier reports "not inhibited" and invites the wrong conclusion ("KDE ignores logind inhibitors").

One run also showed `HasInhibition(1) == yes` at t≈0.5 s while a *previous* holder had just exited —
PowerDevil can report lingering/known state for a while. Cross-check logind (`systemd-inhibit --list`)
rather than trusting one PowerDevil sample, and prefer watching a **transition**.

### PowerDevil's own D-Bus API

```
org.kde.Solid.PowerManagement
  /org/kde/Solid/PowerManagement/PolicyAgent
  org.kde.Solid.PowerManagement.PolicyAgent
    AddInhibition(u types, s who, s why) -> u cookie     # types: 1 InterruptSession, 4 ChangeScreenSettings
    ReleaseInhibition(u cookie) -> ()
    HasInhibition(u types) -> b
    ActiveInhibitions      property a(ssssu)   # (what, who, why, mode, flags); flags 3 = Active|Allowed
    RequestedInhibitions   property a(ssssu)
    ListInhibitions() -> a{ss}  / InhibitionsChanged  (deprecated)
```

```bash
# is suspend currently inhibited?  (1 = InterruptSession, 5 = InterruptSession|ChangeScreenSettings)
busctl --user call org.kde.Solid.PowerManagement /org/kde/Solid/PowerManagement/PolicyAgent \
       org.kde.Solid.PowerManagement.PolicyAgent HasInhibition u 1
busctl --user get-property org.kde.Solid.PowerManagement /org/kde/Solid/PowerManagement/PolicyAgent \
       org.kde.Solid.PowerManagement.PolicyAgent ActiveInhibitions
```

**busctl argument quirk [verified]:** `AddInhibition` has signature `uss`; `busctl --user call … AddInhibition u 5 s a s b`
fails with `Too many parameters for signature.` — the s-typed args must be passed as `AddInhibition uss`
or with explicit `string:` prefixes. `dbus-send` works and returns a cookie, but a `dbus-send`-style
process exits immediately, and PowerDevil drops inhibitors whose D-Bus client vanished
(`onServiceUnregistered`), so it cannot be used to hold a lock from the shell.

**The Energy KCM can override everything.** PowerDevil keeps a user-configured list of "blocked"
inhibitor applications (`m_configuredToBlockInhibitions`, editable in System Settings → Power →
"Inhibit..."); entries there are simply not imported. If an app's inhibitor is mysteriously ignored
while every other app's works, check that list before writing any code.

### kwin: the screen side

- `strings /usr/lib/libkwin.so.6` contains `org.freedesktop.ScreenSaver` (+ the `/ScreenSaver` path)
  and **no** `org.freedesktop.login1` reference **[verified]**: kwin learns about "don't blank / don't
  lock" only through the screensaver interface. Taking `ScreenSaver.Inhibit` therefore also suppresses
  screen locking, which is exactly the side effect to avoid when the requirement is only "don't
  suspend".
- kwin itself appears in `systemd-inhibit --list` with a `delay`-mode `sleep` inhibitor named
  *"Ensuring that the screen gets locked before going to sleep"* **[verified]** — proof that the lock
  screen is what delays suspend, and a handy marker for spotting which subsystem is which.

### Upstream reports worth knowing (context, not verified here)

- KDE bug 457859 — "Powerdevil does not respect sleep inhibitors created with systemd-inhibit by
  unprivileged users": the canonical complaint this section exists to explain. On current versions
  the import path above does work, with the ~5 s delay.
- KDE bug 464119 — a `sleep` inhibition also disabling screen locking: confirms the layers are not
  cleanly separated on Plasma.
- KDE bug 486506 — the KDE portal relayed the portal's `idle` flag (8) to PowerDevil as
  `InterruptSession` only, so an idle inhibition from a sandboxed app did not stop the screen locker.

### GNOME **[docs]**

- Gate: `org.gnome.SessionManager.IsInhibited(flags)` / the session manager's own idle logic; flags
  `4` = suspend, `8` = idle, `1` = logout, `2` = user switch. An app takes
  `Inhibit(app_id, toplevel_xid, reason, flags) → cookie`.
- There is no equivalent to PowerDevil's delayed import: GNOME reads the inhibitor state at the moment
  it considers suspending/idling.
- `org.gnome.ScreenSaver` (present on GNOME, absent on KDE) is the blank/lock side.

---

## Verification cookbook

Always verify at the layer that decides, and finish with a real idle test — never report success from
your own return code.

```bash
# 1. all layers at once
<skill-dir>/scripts/check-inhibit.sh

# 2. take the lock yourself while watching; expect logind immediately, KDE at ~5s
<skill-dir>/scripts/check-inhibit.sh --watch 20
systemd-inhibit --what=sleep --who=manual --why=test --mode=block sleep 12

# 3. does your own process hold it?
systemd-inhibit --list --no-pager | grep -i <your-app>
busctl get-property org.freedesktop.login1 /org/freedesktop/login1 \
       org.freedesktop.login1.Manager BlockInhibited     # must contain "sleep"
```

Real-effect test: set the idle-suspend timeout to 1–2 minutes, leave the machine idle, and watch.
Do the same **without** the lock active to confirm the timeout actually fires on that machine —
otherwise a "pass" proves nothing.

Release paths, all of which must end with `systemd-inhibit --list` free of your app: pause/stop,
program exit, and an uncatchable kill:

```bash
kill -9 <pid>    # logind's fd-based lock is released by the kernel; verify, do not assume
```

Fallback paths (test them on purpose rather than hoping):

- Simulate "no systemd/logind" and confirm your ScreenSaver/portal fallback engages:
  `DBUS_SYSTEM_BUS_ADDRESS=unix:path=/tmp/nonexistent-bus <your-app>`.
- When asserting on `dbus-monitor` output, note its format uses `;` separators, so the dotted name
  `org.freedesktop.ScreenSaver` is not contiguous — match on `member=Inhibit` / the sender instead.

### Misdiagnoses to avoid (each of these was actually made while writing this skill)

1. "KDE ignores logind inhibitors." — Wrong: measured < 5 s after acquisition it looks ignored. Re-check
   after ≥ 5 s, or watch the transition.
2. "I need `sleep:idle` for suspend." — Wrong on every layer: `sleep` maps to the suspend gate, `idle`
   to the screen gate (and on KDE `idle` also implies the suspend gate). Adding `idle` only buys you a
   screen that never blanks or locks.
3. "`Inhibit()` returned an fd, so the machine will stay awake." — The fd proves logind accepted the
   lock, nothing about the desktop honouring it.
4. "The screensaver lock is a good belt-and-braces addition." — It also disables screen locking, a real
   behaviour change the user will notice.
5. "Lid close is covered too." — No: in Plasma only `onIdleTimeout()` consults the policy agent.
