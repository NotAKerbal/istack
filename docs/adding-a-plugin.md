# Adding a plugin

1. **Create the folder** `plugins/<plugin-name>/`. Use the plugin's name as the folder name.
2. **Add manifests.** Provide `.codex-plugin/plugin.json` with `name`, `version`, `description`, and `interface` metadata. If the plugin ships an MCP server, point `mcpServers` at a `.mcp.json` whose `command`/`args` paths are relative to the plugin folder. Optional skills go in `skills/<skill-name>/SKILL.md`, referenced by `"skills": "./skills/"`. Use `plugins/linux-computer-use` as a working example.
3. **Keep it self-contained.** Put all runtime code and dependencies inside the folder.
   - For Node, add a `package.json` and commit a `package-lock.json`; `npm install` at the root then runs `npm ci` inside the folder.
   - Non-Node plugins need no `package.json`; document their own setup in the plugin README.
4. **List it in the marketplace.** Add an entry to `.agents/plugins/marketplace.json`:

   ```json
   {
     "name": "<plugin-name>",
     "source": { "source": "local", "path": "./plugins/<plugin-name>" },
     "policy": { "installation": "AVAILABLE", "authentication": "ON_INSTALL" },
     "category": "Productivity"
   }
   ```

   Keep the marketplace `name` (`linux-desktop-local`) unchanged; existing installs depend on it.
5. **Document it.** Give the plugin its own `README.md`, and add a row to the Plugins table in the root README. Add root forwarding scripts (`npm --prefix plugins/<plugin-name> run <script>`) only for commands people will run often. Prefix the script names (for example `<plugin-name>:test`) if they would clash with existing ones.
6. **Install in Codex.** If the root is already registered as a marketplace, `codex plugin add <plugin-name>@linux-desktop-local` installs the new plugin. Otherwise run `codex plugin marketplace add /path/to/istack` first. Restart the Codex/T3 agent process to load the new tools.
7. **Tests.** Keep `npm test` in each plugin free of GUI, network, and system-service side effects. Put anything that needs a live desktop or a service behind a separate, explicitly named script.
