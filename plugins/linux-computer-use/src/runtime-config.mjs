import { homedir } from 'node:os';
import { join } from 'node:path';
import { readFileSync } from 'node:fs';

export const serviceName = 'linux-computer-use.service';
export const configPath = join(process.env.XDG_CONFIG_HOME || join(homedir(), '.config'), 'linux-computer-use/config.json');
export const userRuntimeDir = `/run/user/${process.getuid()}`;
export const runtimeDir = join(process.env.XDG_RUNTIME_DIR || userRuntimeDir, 'linux-computer-use');
export const socketPath = join(runtimeDir, 'control.sock');
export function runtimeConfig() {
  try { return JSON.parse(readFileSync(configPath, 'utf8')); }
  catch (error) { if (error.code === 'ENOENT') return {}; throw error; }
}
