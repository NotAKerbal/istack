# istack

istack is Isaac's collection of local agent plugins. Each active plugin lives in its own folder under `plugins/`. The repository root holds one shared Codex marketplace, `.agents/plugins/marketplace.json`, that lists every active plugin.

## Plugins

| Plugin | Folder | Summary |
| --- | --- | --- |
| `linux-computer-use` 0.2.0 | [`plugins/linux-computer-use`](plugins/linux-computer-use/README.md) | Native GNOME desktop control over MCP (screenshots, input, AT-SPI accessibility), using a per-user service with an XDG portal fallback |
| `coworker-brief` 0.1.0 | [`plugins/coworker-brief`](plugins/coworker-brief/README.md) | Skill-only catch-up brief: the agent explains its current thread like it would to a coworker, to cut context-switching cost |
| `ui-simplify` 0.1.0 | [`plugins/ui-simplify`](plugins/ui-simplify/README.md) | Skill-only lean-UI rules: no extra text, duplicate information, or decorative chrome, applied while building and when simplifying |

Retired plugins move to `archive/` and leave the marketplace. `ui-improvement-review` is archived there; use `ui-simplify` instead.

For compatibility with existing installs, the marketplace keeps the ID `linux-desktop-local`; its display name is **istack**. Plugins are installed as `<plugin-name>@linux-desktop-local`.

## Quick setup

The commands below set up `linux-computer-use`. Requires Node 20+, plus the desktop prerequisites listed in the [plugin README](plugins/linux-computer-use/README.md#run).

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
