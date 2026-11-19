# Coworker Brief

A skill-only Codex plugin for getting back into a thread quickly. Ask an agent for a coworker brief and it stops to explain its work the way it would to a coworker who just stopped by: what it is working on, why it matters, where it stands, what comes next, and what it needs from you. It is meant for switching between many agent threads without rereading each one.

This plugin is part of the [istack](../../README.md) collection at `plugins/coworker-brief`. It has no MCP server, runtime, or dependencies. The skill is in [`skills/coworker-brief`](skills/coworker-brief/SKILL.md).

## Behavior

- **Grounded.** The agent checks cheap, read-only state such as git, the PR, and background or delegated work before writing, and it keeps verified results apart from planned or unverified ones.
- **Bottom line first.** The opening sentence says what the work is and why, and any decision you need to make comes next.
- **Report only, not a pause.** The agent takes no new action while writing the brief. It keeps any standing instructions, such as a review loop or a requested merge, and stops the task only if you ask it to.
- **Short updates stay short.** It usually runs 100 to 250 words, and shorter when there is less to say.

Invoke it with `$coworker-brief` in Codex, or ask something like "catch me up" or "what are you working on?"

## Install

```bash
codex plugin add coworker-brief@linux-desktop-local
```

Run `codex plugin marketplace add /path/to/istack` first if the repository root is not already registered, then restart the Codex/T3 agent process to load the skill.
