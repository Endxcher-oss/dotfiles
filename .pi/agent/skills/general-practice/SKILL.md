---
name: general-practice
description: 'Default working practice for building, refactoring, and documenting software in any project.'
---

# General practice

Applies to normal implementation, refactor, and documentation work in any repository. Follow it
unless the user's own instructions say otherwise for the task at hand.

The rules below describe how to work and how to lay out the projects you produce. This skill itself
is only `SKILL.md` plus `references/`; it is not a template for the repositories you work in.

## 1. A first request is a draft, not a contract

The first message usually describes a goal, not a specification. Do not start writing code from it.

1. Find the genuine gaps: scope boundaries, target platform/version, data source, interface shape,
   what "done" means, what must not change. Skip cosmetic questions.
2. If a gap changes what you build, ask it now — a few sharp questions, not an interrogation. If a
   gap is minor, pick the obvious default and say which default you picked.
3. Present the plan at a high level: what you will produce, the main steps, what is out of scope.
   No file-by-file detail at this stage.
4. Wait for confirmation. Then build.

Follow-up requests are not drafts. Once a plan or an established direction exists, execute directly —
no re-planning, no re-confirmation, no "here is what I will do next" preamble.

## 2. Documentation layout in the project you are working on

Every project you create or maintain gets a `README.md` and a `docs/` directory, split by audience:

- `README.md` is for people using the thing. Plain prose, short, no badges, no emoji, no marketing
  voice. Cover what it does, how to install/run it, and one worked example. Nothing else.
- Everything written for developers — design decisions, rationale, internal data shapes, ops notes,
  constraints — goes under `docs/`. Never in `README.md`, in CLI help, in UI copy, or in logs.
- Do not keep editing `docs/`. Update it when behavior, interfaces, or configuration actually
  change, and leave it alone otherwise.

## 3. Comments live in the project's docs/, not in its code

- Source files carry exactly one summary comment at the top: what the file is for and how it fits in.
- No inline explanation, no per-function docstrings, no "step 1 / step 2" narration, no commented-out
  code, no change-log comments. When explanation is needed, it belongs in `docs/`.
- Names and structure carry the rest. If a block needs a comment to be readable, refactor it.

## 4. Sleep and timeout values

Both are set by necessity, never by blanket caution:

- Start small: a first `sleep` of **at most 2 seconds**, a first `timeout` of only a few seconds.
- Raise a value **only** after it actually caused a failure — a perceived-too-early poll, a killed
  command, a timeout error in the output. Then raise it slightly and retry.
- Never pre-emptively pad with `sleep 10` or `timeout 600`. If a wait is genuinely long and
  open-ended, poll for the condition instead of sleeping a fixed large amount.

## 5. Verification discipline

- Verify once, at the end, with the real check for the change.
- Re-run the full suite only for large or risky changes. For a small edit, use a targeted check: run
  the single affected case, compile, lint, or grep — not the whole suite on a loop.
- Never re-run tests to "make sure" without a change in between.

## 6. Tools

- Prefer plain file reads, shell commands, and HTTP fetches for research and inspection.
- Use browser automation only when the page needs JavaScript, requires real interaction, or blocks
  non-browser clients. If a fetch already answers the question, stop there.

## 7. Keep design inward

Internal requirements, constraints, trade-off notes, and rationale stay in the repo's `docs/` and in
your messages to the user. The user-facing side of the product — its `README.md`, UI text, help
output, errors, commit messages — states behavior, not the reasoning that produced it.

## 8. Commits

One sentence, English, imperative mood, describing the change itself. No body, no bullet list, no
emoji, no prefix convention unless the repository already enforces one.

## Deliverable check

Before calling work done, for the project you worked on:

- Does the project have a `README.md` a new user understands without reading `docs/`?
- Do the source files contain only a top-level summary comment?
- Are every `sleep` and `timeout` values the smallest that worked?
- Was the suite run once, not repeatedly?
- Is the commit subject one English sentence?
