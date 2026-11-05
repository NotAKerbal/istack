# UI Improvement Review

A skill-only Codex plugin that scores an existing product UI with an independent council of distinct AI models against an anchored rubric, benchmarks comparable flows against strong peers, and reports evidence-backed improvements. It is review only unless changes are authorized for the task.

This plugin is part of the [istack](../../README.md) collection at `plugins/ui-improvement-review`. It has no MCP server, runtime, or dependencies. The skill is in [`skills/ui-improvement-review`](skills/ui-improvement-review/SKILL.md).

## Council

The default council is GPT-6.1 Sol, Claude Opus 5.5, and Grok 4.7. Fable 5.1 joins only when explicitly requested, and a roster the user chooses overrides the default. Each run checks that its models are actually available and can open image evidence, and any replacement or reduced council needs the user's agreement.

## Install

```bash
codex plugin add ui-improvement-review@linux-desktop-local
```

Run `codex plugin marketplace add /path/to/istack` first if the repository root is not already registered, then restart the Codex/T3 agent process to load the skill.
