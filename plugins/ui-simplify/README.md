# UI Simplify

A skill-only plugin that keeps agents from adding fluff to UI. Agents tend to ship titles that repeat the header, explainer and disclaimer copy, duplicate information, dividers, nested cards, and decorative chips, and Isaac then removes them one request at a time. This skill turns those requests into defaults, so the first version comes out lean.

This plugin is part of the [istack](../../README.md) collection at `plugins/ui-simplify`. It has no MCP server, runtime, or dependencies. The skill is in [`skills/ui-simplify`](skills/ui-simplify/SKILL.md), with generalized before-and-after examples in [`references/examples.md`](skills/ui-simplify/references/examples.md).

## Behavior

- **Lean by default.** It covers building and changing UI, including mockups and artifact pages, not only cleanup requests.
- **Organized, closed by default.** Settings stay grouped into parts. Secondary settings forms and option lists sit behind a button or a collapsed section, and secrets are never shown by default.
- **Sweeps the category.** When asked to fix one element, the agent fixes every element of that kind on the screens in question, across platforms, themes, and states.
- **Keeps what matters.** Functionality, information people need to proceed, real limitations, accessibility, and required notices stay. Removing in-scope clutter includes its markup, but deleting features, their implementation, or data needs explicit approval.

Invoke it with `$ui-simplify` in Codex or `/ui-simplify` in Claude Code, or ask an agent to "simplify this" or "remove the extra text". Implicit invocation is allowed, so agents can also pick it up on their own when building UI.

## Install

For Codex:

```bash
codex plugin add ui-simplify@linux-desktop-local
```

Run `codex plugin marketplace add /path/to/istack` first if the repository root is not already registered, then restart the Codex/T3 agent process to load the skill.

For Claude Code, link the skill into your user skills folder:

```bash
mkdir -p ~/.claude/skills
ln -s /path/to/istack/plugins/ui-simplify/skills/ui-simplify ~/.claude/skills/ui-simplify
```
