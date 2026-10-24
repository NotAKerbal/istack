#!/usr/bin/env node
import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { createInterface } from 'node:readline';
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { setTimeout as sleep } from 'node:timers/promises';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { runtimeConfig } from '../src/runtime-config.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const fixture = spawn('/usr/bin/python3', [root + 'scripts/desktop-fixture.py'], { stdio: ['ignore', 'pipe', 'inherit'] });
let state = {};
createInterface({ input: fixture.stdout }).on('line', line => { state = JSON.parse(line); });
const client = new Client({ name: 'desktop-smoke', version: '1.0.0' });
const transport = new StdioClientTransport({ command: process.execPath, args: [root + 'src/server.mjs'], stderr: 'inherit', env: { ...process.env } });
const call = async (name, args = {}, timeout = 30000) => {
  const result = await client.callTool({ name, arguments: args }, undefined, { timeout });
  if (result.isError) throw new Error(result.content[0].text);
  return { data: JSON.parse(result.content[0].text), image: result.content.find(c => c.type === 'image') };
};
try {
  await client.connect(transport);
  console.log(process.env.LINUX_CUA_BACKEND === 'mutter' || runtimeConfig().transport === 'daemon'
    ? 'Testing GNOME native desktop control; no sharing picker is expected.'
    : 'Approve GNOME’s sharing dialog and select the monitor with the Linux Computer Use Test window.');
  let start = await call('computer_start', { clipboard: true });
  if (start.data.starting) {
    const deadline = Date.now() + 195000;
    let status;
    do {
      await sleep(1000);
      status = await call('computer_status');
      if (status.data.lastStartError) throw new Error(status.data.lastStartError);
    } while (status.data.starting && Date.now() < deadline);
    if (!status.data.active) throw new Error('Desktop session did not become active');
    start = { data: status.data.lastStart };
  }
  console.log('Desktop session:', start.data);
  const before = await call('computer_screenshot');
  const detect = spawnSync('/usr/bin/python3', [root + 'scripts/find-marker.py'], { input: Buffer.from(before.image.data, 'base64'), encoding: 'utf8' });
  if (detect.status !== 0) throw new Error(detect.stderr);
  const { x, y } = JSON.parse(detect.stdout);
  await call('computer_input', { actions: [
    { type: 'click', frameId: before.data.metadata.frameId, x, y },
    { type: 'type', text: 'Linux portal input works' },
    { type: 'wait', durationMs: 300 },
  ] });
  assert.equal(state.clicked, 1, 'Real pointer click reached GTK fixture');
  assert.equal(state.text, 'Linux portal input works', 'Real keyboard input reached GTK fixture');
  const tree = await call('computer_accessibility', { app: 'linux-cua-test', maxNodes: 100 });
  assert.ok(tree.data.nodes.some(n => n.name === 'Linux Computer Use Test'), 'AT-SPI sees the fixture window');
  // Test Unicode through the portal clipboard, then a real Ctrl+V shortcut.
  if (start.data.clipboard) {
    await call('computer_clipboard_set', { text: 'Unicode works ✓ café 😊' });
    await call('computer_input', { actions: [
      { type: 'key', keys: ['CTRL', 'a'] },
      { type: 'key', keys: ['CTRL', 'v'] },
      { type: 'wait', durationMs: 300 },
    ] });
    assert.equal(state.text, 'Unicode works ✓ café 😊', 'Portal clipboard and keyboard paste reached GTK fixture');
  }
  const after = await call('computer_screenshot');
  await mkdir(root + 'artifacts', { recursive: true });
  await writeFile(root + 'artifacts/desktop-smoke.png', Buffer.from(after.image.data, 'base64'));
  await writeFile(root + 'artifacts/desktop-smoke.json', JSON.stringify({ passed: true, backend: start.data, fixture: state, metadata: after.data.metadata }, null, 2));
  console.log(`PASS: ${start.data.backend} capture, screenshot coordinates, real pointer, keyboard, accessibility, and optional Unicode clipboard.`);
} finally {
  try { await call('computer_stop'); } catch {}
  await client.close();
  fixture.kill('SIGTERM');
}
