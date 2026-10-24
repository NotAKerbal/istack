#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync, realpathSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const pluginName = 'linux-computer-use', marketplaceName = 'linux-desktop-local';
const pluginRoot = realpathSync(fileURLToPath(new URL('../', import.meta.url)));

// The marketplace lives at the repository root (for example istack/.agents/plugins/marketplace.json),
// not in this plugin folder. Use the nearest ancestor whose marketplace lists this exact folder.
function findMarketplaceRoot() {
  for (let dir = pluginRoot; ; dir = dirname(dir)) {
    const file = join(dir, '.agents/plugins/marketplace.json');
    if (existsSync(file)) {
      const marketplace = JSON.parse(readFileSync(file, 'utf8'));
      const entry = marketplace.plugins?.find(plugin => plugin.name === pluginName);
      if (marketplace.name === marketplaceName && entry?.source?.source === 'local'
        && existsSync(resolve(dir, entry.source.path)) && realpathSync(resolve(dir, entry.source.path)) === pluginRoot) return dir;
    }
    if (dirname(dir) === dir) throw new Error(`No ${marketplaceName} marketplace lists ${pluginRoot}. Expected .agents/plugins/marketplace.json at the repository root.`);
  }
}

function codex(args, options = {}) {
  const result = spawnSync('codex', args, { encoding: 'utf8', ...options });
  if (result.error) throw new Error(`Could not run codex: ${result.error.message}`);
  if (result.status !== 0) {
    if (options.stdio !== 'inherit') process.stderr.write((result.stdout || '') + (result.stderr || ''));
    process.exit(result.status || 1);
  }
  return result;
}

const root = findMarketplaceRoot();
// Codex copies the plugin folder, including node_modules, into its plugin cache.
if (!existsSync(join(pluginRoot, 'node_modules/@modelcontextprotocol/sdk/package.json')))
  throw new Error(`Dependencies are missing in ${pluginRoot}. Run npm ci there (or npm install at the istack root) first.`);
if (existsSync(join(pluginRoot, 'artifacts')))
  console.warn(`Warning: ${join(pluginRoot, 'artifacts')} exists and will be copied into the Codex plugin cache. It may contain desktop screenshots; remove it first if that is not wanted.`);

// The CLI handles TOML safely and preserves all unrelated configuration.
const doctor = spawnSync('/usr/bin/python3', [join(pluginRoot, 'native/worker.py'), '--doctor'], { encoding: 'utf8' });
if (doctor.status !== 0 || !JSON.parse(doctor.stdout).ready) {
  process.stderr.write(doctor.stdout + doctor.stderr);
  throw new Error('Desktop prerequisites are not ready. See README.md.');
}

// Codex refuses to re-add a marketplace name from a different source, so replace a stale registration
// (for example an earlier checkout location) and leave a matching one untouched.
const { marketplaces = [] } = JSON.parse(codex(['plugin', 'marketplace', 'list', '--json']).stdout);
const existing = marketplaces.find(marketplace => marketplace.name === marketplaceName);
const sameRoot = existing?.root && existsSync(existing.root) && realpathSync(existing.root) === root;
if (existing && !sameRoot) {
  console.log(`Replacing ${marketplaceName} marketplace source ${existing.root} with ${root}`);
  codex(['plugin', 'marketplace', 'remove', marketplaceName], { stdio: 'inherit' });
}
if (!sameRoot) codex(['plugin', 'marketplace', 'add', root], { stdio: 'inherit' });
codex(['plugin', 'add', `${pluginName}@${marketplaceName}`], { stdio: 'inherit' });
const verified = spawnSync(process.execPath, [join(pluginRoot, 'scripts/verify-codex.mjs')], { stdio: 'inherit' });
if (verified.status !== 0) process.exit(verified.status || 1);
console.log('Installed and verified. Restart the Codex/T3 agent process to reload plugin tools, then ask to use Linux Computer Use.');
