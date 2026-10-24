#!/usr/bin/env node
// Live check of the installed per-user service through real MCP clients. Leaves the desktop session ready.
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { setTimeout as sleep } from 'node:timers/promises';
import { mkdir, writeFile } from 'node:fs/promises';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

const root = fileURLToPath(new URL('../', import.meta.url));
const clients = new Set();
async function connect(name) {
  const client = new Client({ name: `service-verifier-${name}`, version: '0.3.0' });
  await client.connect(new StdioClientTransport({ command: process.execPath,
    args: [root + 'src/server.mjs'], env: { ...process.env, LINUX_CUA_TRANSPORT: 'daemon' }, stderr: 'inherit' }));
  clients.add(client);
  return client;
}
async function disconnect(client) { clients.delete(client); await client.close(); }
async function call(client, name, args = {}) {
  const result = await client.callTool({ name, arguments: args });
  if (result.isError) throw new Error(result.content[0].text);
  const data = JSON.parse(result.content[0].text);
  if (name === 'computer_screenshot') assert.ok(result.content.some(c => c.type === 'image' && c.data.length > 1000), 'Screenshot returns an image');
  return data;
}
async function rejects(client, name, pattern) {
  const result = await client.callTool({ name, arguments: {} });
  assert.ok(result.isError, `${name} must be refused`);
  assert.match(result.content[0].text, pattern);
  return result.content[0].text;
}
const steps = [];
const step = (name, detail) => { steps.push({ name, ...detail }); console.error(`ok - ${name}`); };

try {
  const a = await connect('a');
  let status = await call(a, 'computer_status');
  assert.equal(status.persistentService, true, 'MCP server uses the installed service');
  assert.equal(status.backend, 'gnome-native');
  assert.notEqual(status.desktopLocked, true, 'GNOME must be unlocked for live verification');
  if (status.suspended) { await call(a, 'computer_start'); step('cleared prior suspension with explicit start', {}); }

  let t = Date.now();
  const frame1 = await call(a, 'computer_screenshot'); // Lazily opens the native session: no picker.
  const statusA = await call(a, 'computer_status');
  assert.equal(statusA.active, true);
  assert.equal(statusA.controlOwner, 'self');
  step('client A screenshot auto-starts native session', { ms: Date.now() - t, generation: frame1.metadata.generation, workerPid: statusA.workerPid });

  const b = await connect('b'); // Second MCP client while A is still connected.
  const statusB = await call(b, 'computer_status');
  assert.equal(statusB.servicePid, statusA.servicePid);
  assert.equal(statusB.workerPid, statusA.workerPid);
  assert.equal(statusB.generation, statusA.generation);
  assert.equal(statusB.controlOwner, 'another-agent');
  await rejects(b, 'computer_screenshot', /Another agent currently controls/);
  step('client B sees same service/worker/generation and is refused input while A holds the lease', {});

  await disconnect(a);
  await sleep(300);
  const frame2 = await call(b, 'computer_screenshot');
  const statusB2 = await call(b, 'computer_status');
  assert.equal(frame2.metadata.generation, frame1.metadata.generation, 'Native session survives MCP client disconnect');
  assert.equal(statusB2.workerPid, statusA.workerPid, 'Same native helper serves the next agent');
  assert.equal(statusB2.controlOwner, 'self');
  step('after A disconnects, B reuses the same worker and generation', { generation: frame2.metadata.generation, workerPid: statusB2.workerPid });

  const c = await connect('c'); // A non-owner may stop globally.
  const stopped = await call(c, 'computer_stop');
  assert.equal(stopped.active, false);
  await rejects(b, 'computer_screenshot', /was stopped\. Call computer_start/);
  await rejects(b, 'computer_accessibility', /was stopped/);
  const statusStopped = await call(b, 'computer_status');
  assert.equal(statusStopped.suspended, true);
  assert.equal(statusStopped.active, false);
  step('global stop from client C blocks B screenshot/accessibility until start', {});

  t = Date.now();
  let started = await call(b, 'computer_start');
  while (started.starting) {
    assert.ok(Date.now() - t < 15000, 'Native start completes without user interaction');
    await sleep(250);
    started = await call(b, 'computer_status');
    if (started.lastStartError) throw new Error(started.lastStartError);
  }
  const startMs = Date.now() - t;
  const frame3 = await call(b, 'computer_screenshot');
  const statusResumed = await call(b, 'computer_status');
  assert.equal(statusResumed.suspended, false);
  assert.equal(statusResumed.active, true);
  assert.equal(statusResumed.backend, 'gnome-native', 'Resumed via Mutter, not the portal picker');
  assert.notEqual(frame3.metadata.generation, frame1.metadata.generation, 'Stop really closed the old session');
  step('explicit start resumes without any dialog', { ms: startMs, generation: frame3.metadata.generation, workerPid: statusResumed.workerPid });

  await disconnect(b);
  await disconnect(c);
  await sleep(300);
  const d = await connect('d');
  const frame4 = await call(d, 'computer_screenshot');
  assert.equal(frame4.metadata.generation, frame3.metadata.generation);
  await disconnect(d);
  step('resumed session is left ready for the next agent', { generation: frame4.metadata.generation });

  const report = { passed: true, backend: statusResumed.backend, persistentService: true,
    servicePid: statusResumed.servicePid, workerPid: statusResumed.workerPid, sameWorkerAcrossClients: true,
    sameGenerationAcrossClients: true, exclusiveLease: true, globalStopBlocks: true, resumedWithoutDialog: true,
    leftActive: true, steps, timestamp: new Date().toISOString() };
  await mkdir(root + 'artifacts', { recursive: true });
  await writeFile(root + 'artifacts/service-verification.json', JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
} finally {
  // Deliberately leave the trusted native session available for the next agent.
  for (const client of clients) await client.close().catch(() => {});
}
