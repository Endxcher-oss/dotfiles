#!/usr/bin/env bash
# check-inhibit.sh - what is keeping this machine awake right now?
#
# Answers "why does it still suspend / still blank the screen?" by dumping
# every layer that can inhibit idle and suspend:
#
#   logind (system bus)  -> the lock most apps take
#   PowerDevil (KDE)     -> what Plasma actually acts on
#   gnome-session (GNOME)-> what GNOME actually acts on
#
# usage:
#   check-inhibit.sh              one shot
#   check-inhibit.sh --watch [N]  poll once a second for N seconds (default 15)
#
# --watch is how you catch KDE's ~5s enforcement delay: take the lock, then
# watch InterruptSession flip from no to yes a few seconds later.

set -u

LOGIN1_SVC=org.freedesktop.login1
LOGIN1_PATH=/org/freedesktop/login1
LOGIN1_IF=org.freedesktop.login1.Manager

KDE_SVC=org.kde.Solid.PowerManagement
KDE_PATH=/org/kde/Solid/PowerManagement/PolicyAgent
KDE_IF=org.kde.Solid.PowerManagement.PolicyAgent

GNOME_SVC=org.gnome.SessionManager
GNOME_PATH=/org/gnome/SessionManager
GNOME_IF=org.gnome.SessionManager

have_busctl=0
command -v busctl >/dev/null 2>&1 && have_busctl=1

user_service() { # user_service <name> [substring]
	local pat="${2:-^${1}$}"
	busctl --user list --no-pager 2>/dev/null | awk '{print $1}' | grep -q "$pat"
}

logind_prop() { # logind_prop <Property>
	busctl get-property "$LOGIN1_SVC" "$LOGIN1_PATH" "$LOGIN1_IF" "$1" 2>/dev/null |
		sed 's/^s //; s/^"//; s/"$//'
}

logind_blocked() {
	local props
	props=$(logind_prop BlockInhibited)
	[ -z "$props" ] && props="-"
	printf '%s' "$props"
}

# compact form for the watch table: which of sleep/idle are blocked
logind_short() {
	local p s=""
	p=$(logind_prop BlockInhibited)
	case "$p" in *sleep*) s="sleep" ;; esac
	case "$p" in *idle*) s="${s:+$s:}idle" ;; esac
	[ -z "$s" ] && s="-"
	printf '%s' "$s"
}

kde_has() { # kde_has <bitmask>  -> true/false/?
	# 1 = InterruptSession (gates "suspend after N minutes of idle")
	# 4 = ChangeScreenSettings (gates dimming/blanking; implies 1 internally)
	local out
	out=$(busctl --user call "$KDE_SVC" "$KDE_PATH" "$KDE_IF" HasInhibition u "$1" 2>/dev/null)
	[ -z "$out" ] && { echo "?"; return; }
	[ "${out##* }" = true ] && echo "yes" || echo "no"
}

gnome_has() { # gnome_has <bitmask>: 4 = suspend, 8 = idle
	local out
	out=$(busctl --user call "$GNOME_SVC" "$GNOME_PATH" "$GNOME_IF" IsInhibited u "$1" 2>/dev/null)
	[ -z "$out" ] && { echo "?"; return; }
	[ "${out##* }" = true ] && echo "yes" || echo "no"
}

if [ "$have_busctl" = 0 ]; then
	echo "check-inhibit: busctl not found, only 'systemd-inhibit --list' is shown" >&2
fi

one_shot()
{
	echo "=== systemd-inhibit --list ==="
	if command -v systemd-inhibit >/dev/null 2>&1; then
		systemd-inhibit --list --no-pager 2>&1 | sed 's/[[:space:]]\+/ /g'
	else
		echo "(systemd-inhibit not installed)"
	fi

	echo
	echo "=== logind properties ==="
	if [ "$have_busctl" = 1 ]; then
		for p in BlockInhibited BlockWeakInhibited DelayInhibited InhibitDelayMaxUSec \
			 IdleHint IdleSinceHint; do
			printf '%-22s %s\n' "$p" "$(logind_prop "$p")"
		done
		printf '%-22s\n' "ListInhibitors:"
		busctl call "$LOGIN1_SVC" "$LOGIN1_PATH" "$LOGIN1_IF" ListInhibitors 2>/dev/null |
			sed 's/^a(ssssuu) //'
	fi

	echo
	echo "=== KDE PowerDevil (the gate Plasma actually checks) ==="
	if [ "$have_busctl" = 1 ] && user_service "$KDE_SVC"; then
		printf 'InterruptSession(1)     %s   <- "suspend after N min of idle" is gated on this\n' "$(kde_has 1)"
		printf 'ChangeScreenSettings(4) %s   <- dim/blank; implies InterruptSession in KDE\n' "$(kde_has 4)"
		printf 'ActiveInhibitions       %s\n' \
			"$(busctl --user get-property "$KDE_SVC" "$KDE_PATH" "$KDE_IF" ActiveInhibitions 2>/dev/null)"
		echo "NOTE: PowerDevil enforces an inhibition ~5s after it is requested;"
		echo "      re-run with --watch to see a fresh lock arrive."
	else
		echo "(org.kde.Solid.PowerManagement not on the session bus)"
	fi

	echo
	echo "=== GNOME session manager (GNOME only) ==="
	if [ "$have_busctl" = 1 ] && user_service "$GNOME_SVC"; then
		printf 'Suspend(4) %s\n' "$(gnome_has 4)"
		printf 'Idle(8)    %s\n' "$(gnome_has 8)"
	else
		echo "(org.gnome.SessionManager not on the session bus)"
	fi

	echo
	echo "=== session bus screensaver interfaces ==="
	if [ "$have_busctl" = 1 ]; then
		for s in org.freedesktop.ScreenSaver org.gnome.ScreenSaver \
			 org.freedesktop.portal.Desktop; do
			if user_service "$s"; then echo "$s  present"; else echo "$s  -"; fi
		done
	fi
}

watch()
{
	local secs=$1 i=0
	echo "time       logind    KDE:susp  KDE:screen  GNOME:susp/idle"
	while [ "${i:-0}" -lt "$secs" ]; do
		local kde_s="" kde_screen="" gnome_s="" gnome_i=""
		if [ "$have_busctl" = 1 ] && user_service "$KDE_SVC"; then
			kde_s=$(kde_has 1); kde_screen=$(kde_has 4)
		fi
		if [ "$have_busctl" = 1 ] && user_service "$GNOME_SVC"; then
			gnome_s=$(gnome_has 4); gnome_i=$(gnome_has 8)
		fi
		printf '%-10s %-9s %-9s %-11s %s\n' "$(date +%T)" "$(logind_short)" \
			"${kde_s:--}" "${kde_screen:--}" "${gnome_s:--}/${gnome_i:--}"
		sleep 1
		i=$((i + 1))
	done
}

case "${1:-}" in
--watch)
	watch "${2:-15}"
	;;
-h|--help)
	sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
	;;
*)
	one_shot
	;;
esac
