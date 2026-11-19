# Repository layout

```text
istack/
├── .agents/plugins/marketplace.json   # Shared Codex marketplace (ID linux-desktop-local, display name istack)
├── package.json                       # Private root: bootstrap and forwarding scripts only, no dependencies
├── scripts/bootstrap.mjs              # Runs `npm ci` in every plugins/* folder that has a package-lock.json
├── docs/                              # Repository-level documentation
├── archive/                           # Retired plugins, kept for reference and not listed in the marketplace
└── plugins/
    └── linux-computer-use/            # One self-contained plugin
        ├── .codex-plugin/plugin.json  # Codex manifest
        ├── .mcp.json                  # Codex MCP launch config (paths relative to the plugin folder)
        ├── plugin.json, mcp.json      # Portable manifests (${PLUGIN_ROOT} placeholder)
        ├── package.json, package-lock.json
        └── src/, native/, scripts/, skills/, tests/
```

## Conventions

- **Self-contained plugins.** Codex installs a plugin by copying its whole folder, including `node_modules` and any untracked files, into `~/.codex/plugins/cache/<marketplace>/<plugin>/<version>/`. A plugin must not import anything from outside its own folder. This is why the root does not use npm workspaces: hoisting would move dependencies out of the plugin folder.
- **Relative launch paths.** MCP commands in a plugin's `.mcp.json` refer to files relative to the plugin folder (for example `./src/server.mjs`). Codex runs them with the installed plugin folder as the working directory.
- **One marketplace.** The root `.agents/plugins/marketplace.json` is the only marketplace file. Plugin folders don't contain their own. Each entry's `source.path` is relative to the repository root.
- **Local output stays untracked.** `artifacts/`, `node_modules/`, compressed archives, `.env*`, and local config files are ignored. Because Codex copies untracked files too, remove local output such as `artifacts/` from a plugin folder before reinstalling it.
- **No GUI in hosted CI.** Tests that need a real desktop session, systemd user services, or a signed-in Codex stay behind explicit scripts (for example `test:desktop`) and are not run automatically.
