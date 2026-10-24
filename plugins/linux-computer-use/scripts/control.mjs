#!/usr/bin/env node
import { mkdir, writeFile, unlink } from 'node:fs/promises';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';
const stopFile = join(process.env.XDG_STATE_HOME || join(homedir(), '.local/state'), 'linux-computer-use/STOP');
const action = process.argv[2];
if (action === 'stop') {
  await mkdir(dirname(stopFile), { recursive: true, mode: 0o700 });
  await writeFile(stopFile, new Date().toISOString(), { mode: 0o600 });
  console.log('Emergency stop enabled. Active helpers close within 250 ms while idle, or at the next input checkpoint.');
} else if (action === 'resume') {
  await unlink(stopFile).catch(error => { if (error.code !== 'ENOENT') throw error; });
  console.log('Emergency stop cleared. A new computer_start is required.');
} else {
  throw new Error('Usage: node scripts/control.mjs stop|resume');
}
