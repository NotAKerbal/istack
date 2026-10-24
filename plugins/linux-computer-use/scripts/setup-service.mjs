#!/usr/bin/env node
import { cp, mkdir, writeFile, readFile, rename, rm, chmod } from 'node:fs/promises';
import { join, dirname, isAbsolute } from 'node:path';
import { homedir } from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { execFileSync, spawnSync } from 'node:child_process';
import { setTimeout as sleep } from 'node:timers/promises';
import { configPath, serviceName } from '../src/runtime-config.mjs';

// systemd unit syntax differs per setting: ExecStart= splits words with C-style quoting and expands
// $VARS, while path settings such as WorkingDirectory= take the raw value (quotes are literal).
// Both expand %-specifiers. See systemd.service(5) "Command lines" and systemd.unit(5) "Specifiers".
const checkValue = value => {
  if (/[\x00-\x1f\x7f]/.test(value)) throw new Error(`Unit value contains control characters: ${JSON.stringify(value)}`);
  return value;
};
export const execArg = value => '"' + checkValue(value).replace(/\\/g, '\\\\').replace(/"/g, '\\"')
  .replace(/%/g, '%%').replace(/\$/g, '$$$$') + '"';
export const unitPath = value => {
  if (!isAbsolute(checkValue(value)) || value !== value.trim()) throw new Error(`Unit path must be absolute without surrounding whitespace: ${value}`);
  return value.replace(/%/g, '%%');
};

export function renderUnit({ node, runtime }) {
  return `[Unit]
Description=Linux Computer Use native desktop service
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=exec
ExecStart=${execArg(node)} ${execArg(join(runtime, 'src/daemon.mjs'))}
WorkingDirectory=${unitPath(runtime)}
Environment=LINUX_CUA_BACKEND=mutter
RuntimeDirectory=linux-computer-use
RuntimeDirectoryMode=0700
RuntimeDirectoryPreserve=restart
UMask=0077
NoNewPrivileges=yes
Restart=on-failure
RestartSec=2
KillMode=control-group
TimeoutStopSec=5

[Install]
WantedBy=graphical-session.target
`;
}

async function install() {
  const source = fileURLToPath(new URL('../', import.meta.url)).replace(/\/$/, '');
  const target = join(process.env.XDG_DATA_HOME || join(homedir(), '.local/share'), 'linux-computer-use/runtime');
  const unitFile = join(process.env.XDG_CONFIG_HOME || join(homedir(), '.config'), 'systemd/user', serviceName);
  const unit = renderUnit({ node: process.execPath, runtime: target });

  // Validate before touching the installed unit, so a bad render never replaces a working one. A distinct
  // name keeps diagnostics about any currently installed (possibly broken) unit out of this check.
  const scratch = join(dirname(target), 'unit-check');
  const checkName = 'linux-computer-use-check.service';
  await rm(scratch, { recursive: true, force: true });
  await mkdir(scratch, { recursive: true, mode: 0o700 });
  await writeFile(join(scratch, checkName), unit, { mode: 0o600 });
  const verify = spawnSync('systemd-analyze', ['--user', 'verify', join(scratch, checkName)], { encoding: 'utf8' });
  await rm(scratch, { recursive: true, force: true });
  // The runtime may not exist yet on first install, so a missing ExecStart binary is tolerable here only.
  const problems = (verify.stderr + verify.stdout).split('\n').filter(line => line.includes(checkName)
    && !line.includes('is not executable') && !line.includes('No such file'));
  if (verify.error || problems.length) throw new Error('systemd rejected the generated unit:\n' + (problems.join('\n') || verify.error?.message));

  if (source !== target) {
    // Stage a complete copy, then swap, so stale files from older installs never linger.
    const staged = target + '.new', previous = target + '.old';
    await rm(staged, { recursive: true, force: true });
    await mkdir(staged, { recursive: true, mode: 0o700 });
    for (const file of ['src', 'native', 'node_modules', 'scripts', 'package.json', 'package-lock.json']) {
      await cp(join(source, file), join(staged, file), { recursive: true, verbatimSymlinks: true,
        filter: path => !path.includes('__pycache__') && !path.endsWith('.pyc') });
    }
    await rm(previous, { recursive: true, force: true });
    await rename(target, previous).catch(error => { if (error.code !== 'ENOENT') throw error; });
    await rename(staged, target);
    await rm(previous, { recursive: true, force: true });
  }
  await chmod(target, 0o700);

  await mkdir(dirname(unitFile), { recursive: true });
  await writeFile(unitFile, unit, { mode: 0o600 });
  const after = spawnSync('systemd-analyze', ['--user', 'verify', unitFile], { encoding: 'utf8' });
  const remaining = (after.stderr + after.stdout).split('\n').filter(line => line.includes(serviceName));
  if (after.status !== 0 || remaining.length) throw new Error('Installed unit failed verification:\n' + remaining.join('\n'));

  await mkdir(dirname(configPath), { recursive: true, mode: 0o700 });
  let prior = {};
  try { prior = JSON.parse(await readFile(configPath, 'utf8')); }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
  await writeFile(configPath, JSON.stringify({ ...prior, transport: 'daemon', backend: 'mutter' }, null, 2) + '\n', { mode: 0o600 });

  execFileSync('systemctl', ['--user', 'daemon-reload'], { stdio: 'inherit' });
  spawnSync('systemctl', ['--user', 'reset-failed', serviceName], { stdio: 'ignore' });
  execFileSync('systemctl', ['--user', 'enable', serviceName], { stdio: 'inherit' });
  execFileSync('systemctl', ['--user', 'restart', serviceName], { stdio: 'inherit' });

  // Confirm the service actually answers on its socket, not merely that systemd forked it.
  const { DaemonBridge } = await import(pathToFileURL(join(target, 'src/daemon-bridge.mjs')).href);
  const client = new DaemonBridge({ startService: false });
  let status;
  for (let attempt = 0; !status; ++attempt) {
    try { status = await client.call('status', {}, 15000); }
    catch (error) { if (attempt === 50) throw error; await sleep(100); }
  }
  client.close();
  console.log(`Installed ${unitFile}`);
  console.log(`Service active: pid ${status.servicePid}, backend ${status.backend}, suspended ${status.suspended}.`);
  console.log('Desktop sessions are opened on demand without the portal picker while GNOME is unlocked.');
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) await install();
