# Codebase Design

A skill-only plugin that packages Matt Pocock's [`codebase-design`](https://github.com/mattpocock/skills/tree/main/skills/engineering/codebase-design) skill. It gives agents one vocabulary for designing **deep modules**: a lot of behaviour behind a small interface, placed at a clean seam, and testable through that interface.

This plugin is part of the [istack](../../README.md) collection at `plugins/codebase-design`. It has no MCP server, runtime, or dependencies.

## Contents

- [`SKILL.md`](skills/codebase-design/SKILL.md): the glossary (module, interface, implementation, depth, seam, adapter, leverage, locality), deep versus shallow modules, principles such as the deletion test, and designing for testability.
- [`DEEPENING.md`](skills/codebase-design/DEEPENING.md): how to deepen a cluster of shallow modules, by dependency category, with replace-don't-layer testing.
- [`DESIGN-IT-TWICE.md`](skills/codebase-design/DESIGN-IT-TWICE.md): spawn parallel sub-agents to design an interface several radically different ways, then compare them and recommend one.

`DESIGN-IT-TWICE.md` mentions a project `GLOSSARY.md` for domain language. That file belongs to the project being designed, not to this skill. Skip it when a project has none.

Invoke it with `$codebase-design` in Codex or `/codebase-design` in Claude Code, or ask an agent to design a module's interface, find deepening opportunities, or decide where a seam goes.

## Source

The files under `skills/codebase-design/` are copied unchanged from [mattpocock/skills](https://github.com/mattpocock/skills) at commit [`abeeaf9`](https://github.com/mattpocock/skills/tree/abeeaf95660ba9e8b7c753eb38f441ca707a8823/skills/engineering/codebase-design). The upstream project is MIT licensed, and its license is kept in [`LICENSE`](LICENSE).

To update, copy the folder from a newer upstream commit, update the commit link above, and bump the plugin version.

## Install

For Codex:

```bash
codex plugin add codebase-design@linux-desktop-local
```

Run `codex plugin marketplace add /path/to/istack` first if the repository root is not already registered, then restart the Codex/T3 agent process to load the skill.

For Claude Code, link the skill into your user skills folder. Grok Build also reads skills from this folder.

```bash
mkdir -p ~/.claude/skills
ln -s /path/to/istack/plugins/codebase-design/skills/codebase-design ~/.claude/skills/codebase-design
```
