/*
 * inhibit.c - keep the machine from suspending while something is going on.
 *
 * This is the Linux implementation extracted from cmus' inhibit.c (commit
 * "Add sleep_inhibit option"), where it is tested against systemd, elogind,
 * KDE Plasma and kwin.  Build with -DCONFIG_INHIBIT, and -DCONFIG_SDBUS_BASU
 * instead of linking libsystemd if you use basu.
 *
 *       gcc -DCONFIG_INHIBIT $(pkg-config --cflags libsystemd) -c inhibit.c
 *
 * Suspend is inhibited, but the *screen* is not: the display is still allowed
 * to blank and to lock, exactly as the power settings say.  That is what
 * "keep playing music" needs - for a presentation you usually want the
 * display locked too, see the skill's references/platforms.md for what to
 * change.
 *
 * Two locks are used, both best effort:
 *
 *  - logind (system bus): Inhibit() returns a file descriptor which is only
 *    valid while it is kept open.  Releasing the lock is just a matter of
 *    closing it, so a crashed program can never leave a stale inhibitor
 *    behind (no unreliable cleanup, no pid files, no leak after SIGKILL).
 *    Only "sleep" is requested.  "idle" is deliberately *not* requested: it
 *    keeps the session from ever counting as idle, which is what blanking and
 *    locking are driven by.
 *
 *    The "what" string is interpreted by the desktop environment as well, and
 *    the mappings differ.  KDE's PowerDevil (daemon/powerdevilpolicyagent.cpp,
 *    policiesInLogindWhat) maps "sleep" to its InterruptSession policy - the
 *    very policy its SuspendSession action requires, i.e. the gate in front of
 *    "suspend after N minutes of inactivity" - while "idle" maps to
 *    ChangeScreenSettings (dimming and blanking).  Asking for "sleep" alone
 *    therefore stops Plasma from suspending on idle without touching the
 *    screen behaviour.
 *
 *  - org.freedesktop.ScreenSaver (session bus): the classic interface
 *    implemented by most desktop environments; Inhibit() returns a cookie
 *    which is passed back to UnInhibit().  This one commonly covers blanking
 *    and locking too (kwin, for instance, feeds nothing but this interface
 *    into its idle handling), so it is only used as a fallback when logind is
 *    not around, and never on top of a working logind.
 *
 * Failure is not fatal: the program keeps running and a single warning is
 * shown.
 */

#include "inhibit.h"

#ifdef CONFIG_INHIBIT

#if defined(CONFIG_SDBUS_BASU) || defined(CONFIG_MPRIS_BASU)
#include <basu/sd-bus.h>
#else
#include <systemd/sd-bus.h>
#endif

#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

/* the calls below are local and normally complete in microseconds, this only
 * guards against a hung or unreachable bus daemon blocking the main loop */
#define INHIBIT_CALL_TIMEOUT_USEC 2000000

/* arguments shown by "systemd-inhibit --list" and friends */
#ifndef INHIBIT_APP_NAME
#define INHIBIT_APP_NAME "myapp"
#endif
#ifndef INHIBIT_REASON
#define INHIBIT_REASON "Busy"
#endif
/* "sleep" blocks suspend; "idle" would stop blanking/locking as well, see
 * the comment at the top of this file */
#define INHIBIT_LOGIND_WHAT "sleep"

#ifdef INHIBIT_DEBUG
static void inhibit_dbg(const char *fmt, ...)
{
	va_list ap;

	fputs("inhibit: ", stderr);
	va_start(ap, fmt);
	vfprintf(stderr, fmt, ap);
	va_end(ap);
}
#else
#define inhibit_dbg(...) do { } while (0)
#endif

static void inhibit_warn(const char *fmt, ...)
{
	va_list ap;

	fputs("inhibit: ", stderr);
	va_start(ap, fmt);
	vfprintf(stderr, fmt, ap);
	va_end(ap);
	fputc('\n', stderr);
}

static sd_bus *system_bus;
static sd_bus *session_bus;
static int logind_fd = -1;
static uint32_t screensaver_cookie;
static const char *screensaver_path;
static int inhibited;
static int inhibit_warned;
static int enabled = 1;
static int hold;

static void logind_release(void)
{
	if (logind_fd != -1) {
		close(logind_fd);
		logind_fd = -1;
	}
}

static int logind_acquire(void)
{
	sd_bus_error err = SD_BUS_ERROR_NULL;
	sd_bus_message *reply = NULL;
	int fd, rc;

	if (!system_bus) {
		rc = sd_bus_open_system(&system_bus);
		if (rc < 0)
			return rc;
		sd_bus_set_method_call_timeout(system_bus,
				INHIBIT_CALL_TIMEOUT_USEC);
	}

	rc = sd_bus_call_method(system_bus, "org.freedesktop.login1",
			"/org/freedesktop/login1", "org.freedesktop.login1.Manager",
			"Inhibit", &err, &reply, "ssss",
			INHIBIT_LOGIND_WHAT, INHIBIT_APP_NAME, INHIBIT_REASON,
			"block");
	if (rc < 0) {
		inhibit_dbg("logind Inhibit() failed: %s\n",
				err.message ? err.message : strerror(-rc));
		sd_bus_error_free(&err);
		return rc;
	}
	sd_bus_error_free(&err);

	rc = sd_bus_message_read(reply, "h", &fd);
	if (rc <= 0) {
		sd_bus_message_unref(reply);
		return rc < 0 ? rc : -EIO;
	}

	/* the fd is owned by the message, keep a copy of our own */
	logind_fd = dup(fd);
	if (logind_fd != -1)
		fcntl(logind_fd, F_SETFD, FD_CLOEXEC);
	rc = logind_fd == -1 ? -errno : 0;
	sd_bus_message_unref(reply);
	if (rc < 0)
		logind_fd = -1;
	return rc;
}

static int screensaver_inhibit(const char *path, uint32_t *cookie)
{
	sd_bus_error err = SD_BUS_ERROR_NULL;
	sd_bus_message *reply = NULL;
	int rc;

	rc = sd_bus_call_method(session_bus, "org.freedesktop.ScreenSaver",
			path, "org.freedesktop.ScreenSaver", "Inhibit", &err,
			&reply, "ss", INHIBIT_APP_NAME, INHIBIT_REASON);
	if (rc >= 0 && reply)
		rc = sd_bus_message_read(reply, "u", cookie);
	sd_bus_error_free(&err);
	if (reply)
		sd_bus_message_unref(reply);
	return rc;
}

static int screensaver_acquire(void)
{
	static const char * const paths[] = {
		"/org/freedesktop/ScreenSaver",
		/* older (ksmserver) implementations use this path */
		"/ScreenSaver",
	};
	uint32_t cookie = 0;
	unsigned int i;
	int rc = -ENOTSUP;

	if (!session_bus) {
		rc = sd_bus_open_user(&session_bus);
		if (rc < 0)
			return rc;
		sd_bus_set_method_call_timeout(session_bus,
				INHIBIT_CALL_TIMEOUT_USEC);
	}

	for (i = 0; i < sizeof(paths) / sizeof(paths[0]); i++) {
		rc = screensaver_inhibit(paths[i], &cookie);
		if (rc > 0) {
			screensaver_cookie = cookie;
			screensaver_path = paths[i];
			return 0;
		}
	}
	inhibit_dbg("org.freedesktop.ScreenSaver.Inhibit() failed\n");
	return rc < 0 ? rc : -EIO;
}

static void screensaver_release(void)
{
	sd_bus_error err = SD_BUS_ERROR_NULL;
	sd_bus_message *reply = NULL;

	if (!session_bus || !screensaver_path)
		return;

	sd_bus_call_method(session_bus, "org.freedesktop.ScreenSaver",
			screensaver_path, "org.freedesktop.ScreenSaver",
			"UnInhibit", &err, &reply, "u", screensaver_cookie);
	sd_bus_error_free(&err);
	if (reply)
		sd_bus_message_unref(reply);
	screensaver_path = NULL;
	screensaver_cookie = 0;
}

static void inhibit_acquire(void)
{
	int acquired = 0;

	if (inhibited)
		return;

	if (logind_acquire() == 0) {
		acquired = 1;
	} else if (screensaver_acquire() == 0) {
		/* fallback only: this one inhibits blanking and locking as well,
		 * which is not what we want when logind can be used instead */
		acquired = 1;
	}

	if (!acquired) {
		if (!inhibit_warned) {
			inhibit_warn("could not inhibit sleep "
					"(no usable D-Bus service found)");
			inhibit_warned = 1;
		}
		return;
	}

	inhibited = 1;
	inhibit_dbg("sleep inhibition acquired\n");
}

static void inhibit_release(void)
{
	if (!inhibited)
		return;

	logind_release();
	screensaver_release();
	inhibited = 0;
	inhibit_dbg("sleep inhibition released\n");
}

void inhibit_init(int enable)
{
	enabled = !!enable;
}

void inhibit_set_enabled(int enable)
{
	enabled = !!enable;
	inhibit_update(hold);
}

void inhibit_update(int active)
{
	hold = !!active;
	if (!enabled || !hold) {
		inhibit_release();
		return;
	}
	inhibit_acquire();
}

void inhibit_free(void)
{
	inhibit_release();

	if (system_bus) {
		sd_bus_unref(system_bus);
		system_bus = NULL;
	}
	if (session_bus) {
		sd_bus_unref(session_bus);
		session_bus = NULL;
	}
}

#endif /* CONFIG_INHIBIT */
