# istack

istack is Isaac's collection of local agent plugins. Each plugin lives in its own folder under `plugins/`. The repository root holds one shared Codex marketplace, `.agents/plugins/marketplace.json`, that lists every plugin.

## Plugins

| Plugin | Folder | Summary |
| --- | --- | --- |
| `linux-computer-use` 0.2.0 | [`plugins/linux-computer-use`](plugins/linux-computer-use/README.md) | Native GNOME desktop control over MCP (screenshots, input, AT-SPI accessibility), using a per-user service with an XDG portal fallback |

For compatibility with existing installs, the marketplace keeps the ID `linux-desktop-local`; its display name is **istack**. The plugin is installed as `linux-computer-use@linux-desktop-local`.

## Skills

Standalone agent skills live under `skills/`. They are not plugins and are not listed in the marketplace.

| Skill | Summary |
| --- | --- |
| [`vercel-pr-previews`](skills/vercel-pr-previews/SKILL.md) | When an agent creates or pushes to a PR in a Vercel project, it first checks that a Convex preview backend will be deployed only if the PR changes Convex. After the push, it finds the exact-commit preview, opens it visibly, and keeps a Previews section in the PR description. |

A skill applies only while it is installed and the agent loads it. To install one for Codex, symlink it into your skills folder; this does not replace an existing skill directory:

```bash
skills_dir="${CODEX_HOME:-$HOME/.codex}/skills"
mkdir -p "$skills_dir"
[ -e "$skills_dir/vercel-pr-previews" ] || ln -s "$PWD/skills/vercel-pr-previews" "$skills_dir/vercel-pr-previews"
```

Run this from the repository root. Use `cp -R` instead of `ln -s` for a copy that does not follow this checkout. For Claude Code, use `~/.claude/skills` as the destination. Then restart the Codex, T3, or Claude Code agent process so it discovers the skill.

## Quick setup

Requires Node 20+, plus the desktop prerequisites listed in the [plugin README](plugins/linux-computer-use/README.md#run).

```bash
npm install            # runs `npm ci` inside each plugin folder that has a package-lock.json
npm run doctor         # check desktop prerequisites
npm test               # automated tests; no GUI actions
npm run setup:service  # install the per-user GNOME desktop service
npm run setup:codex    # register this repository root as a Codex marketplace and install the plugin
npm run verify:service
npm run verify:codex
```

`npm run bootstrap` repeats the per-plugin `npm ci` without a root install. The root scripts `test`, `doctor`, `setup:service`, `setup:codex`, `verify:codex`, `verify:service`, `test:desktop`, `stop`, and `resume` forward to `linux-computer-use` with `npm --prefix plugins/linux-computer-use`.

Some of these commands change your system. `setup:service` installs a systemd user unit. `setup:codex` changes your Codex configuration and plugin cache. `test:desktop` clicks and types on the live desktop and replaces the clipboard. See the plugin README before running them.

## Layout and adding plugins

The plugins are independent folders, not npm workspaces. Each plugin owns its runtime, dependencies, and lockfile, so an installer that copies one plugin folder gets everything it needs. Plugins may use runtimes other than Node.

See [docs/layout.md](docs/layout.md) for the repository layout and [docs/adding-a-plugin.md](docs/adding-a-plugin.md) for adding another plugin.

## License

MIT. See [LICENSE](LICENSE).
