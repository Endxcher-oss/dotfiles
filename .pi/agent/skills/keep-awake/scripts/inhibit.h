/*
 * inhibit.h - keep the machine from suspending while something is going on.
 *
 * Linux-only implementation; see the keep-awake skill for the other
 * platforms.  Everything is best effort: if no D-Bus service can be reached
 * exactly one warning is printed and the program keeps running.
 *
 * Typical use:
 *
 *	inhibit_init(1);                  // option value, default on
 *	... on every state change:
 *	inhibit_update(busy);             // 1 = take the lock, 0 = release it
 *	... on exit:
 *	inhibit_free();                   // never leave a lock behind
 */
#ifndef INHIBIT_H
#define INHIBIT_H

#ifdef CONFIG_INHIBIT

void inhibit_init(int enabled);
void inhibit_set_enabled(int enabled);
void inhibit_update(int active);
void inhibit_free(void);

#else /* !CONFIG_INHIBIT */

static inline void inhibit_init(int enabled) { (void)enabled; }
static inline void inhibit_set_enabled(int enabled) { (void)enabled; }
static inline void inhibit_update(int active) { (void)active; }
static inline void inhibit_free(void) { }

#endif /* CONFIG_INHIBIT */

#endif /* INHIBIT_H */
