#!/usr/bin/env node
// Install each Node-based plugin's own locked dependencies inside its folder. Plugins are independent
// (no npm workspaces) so that installers which copy a plugin folder get a self-contained runtime.
import { spawnSync } from 'node:child_process';
import { existsSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const plugins = fileURLToPath(new URL('../plugins/', import.meta.url));
const env = { ...process.env };
// Settings from a root `npm install`/`npm ci` (for example --omit) must not leak into the plugin installs.
for (const name of Object.keys(env)) if (name.startsWith('npm_')) delete env[name];
for (const entry of readdirSync(plugins, { withFileTypes: true })) {
  const dir = join(plugins, entry.name);
  if (!entry.isDirectory() || !existsSync(join(dir, 'package-lock.json'))) continue;
  console.log(`istack: npm ci in plugins/${entry.name}`);
  const result = spawnSync('npm', ['ci', '--prefix', dir], { stdio: 'inherit', env });
  if (result.status !== 0) process.exit(result.status || 1);
}
