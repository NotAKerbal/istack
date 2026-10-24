import { test } from 'node:test';
import assert from 'node:assert/strict';
import net from 'node:net';
import { mkdtemp, rm, stat } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { setTimeout as sleep } from 'node:timers/promises';
import { createDesktopDaemon } from '../src/daemon.mjs';
import { DaemonBridge } from '../src/daemon-bridge.mjs';
import { execArg, unitPath, renderUnit } from '../scripts/setup-service.mjs';

// Mimics NativeBridge: stop() rejects in-flight work and resolves once the old helper has exited.
function fakeBridge({ exitMs = 0 } = {}) {
  const state = { starts: 0, stops: 0, alive: false, overlap: false, inflight: new Set(), executed: [] };
  return { state, async call(method, params) {
    state.executed.push(method);
    if (method === 'start') { if (state.alive) state.overlap = true; state.alive = true; ++state.starts; }
    if (params?.slow) {
      return new Promise((resolve, reject) => { const job = { resolve, reject }; state.inflight.add(job); });
    }
    return { method, params, active: true, generation: 'same-native-session' };
  }, stop() {
    ++state.stops;
    for (const job of state.inflight) job.reject(new Error('Desktop session stopped'));
    state.inflight.clear();
    return sleep(exitMs).then(() => { state.alive = false; });
  } };
}

async function setup(options = {}) {
  const dir = await mkdtemp(join(tmpdir(), 'linux-cua-service-'));
  const path = join(dir, 'control.sock');
  const bridge = options.bridge || fakeBridge();
  let daemon = await createDesktopDaemon({ path, bridge, leaseMs: 60, ...options.daemon });
  const clients = [];
  const client = () => { const c = new DaemonBridge({ path, startService: false }); clients.push(c); return c; };
  const first = client(), second = client();
  return { dir, path, first, second, client, bridge, state: bridge.state,
    async restart() { await daemon.close(); daemon = await createDesktopDaemon({ path, bridge, leaseMs: 60, ...options.daemon }); },
    async close() { for (const c of clients) c.close(); await daemon.close(); await rm(dir, { recursive: true }); } };
}

// Exercise the raw protocol, bypassing client-side validation. Resolves once `expected` reply lines
// arrive, or early if the service closes the connection; rejects on socket error or timeout.
async function rawExchange(path, lines, { expected = lines.length, timeoutMs = 2000 } = {}) {
  const socket = net.createConnection(path);
  let data = '';
  const replies = () => data.split('\n').slice(0, -1).filter(Boolean).map(line => JSON.parse(line));
  try {
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error(`Timed out after ${timeoutMs}ms awaiting ${expected} replies; got: ${JSON.stringify(data)}`)), timeoutMs);
      const done = error => { clearTimeout(timer); error ? reject(error) : resolve(); };
      socket.setEncoding('utf8');
      socket.on('data', chunk => { data += chunk; if (data.split('\n').length - 1 >= expected) done(); });
      socket.on('error', done);
      socket.on('close', () => done());
      socket.once('connect', () => { for (const line of lines) socket.write(line + '\n'); });
    });
  } finally { socket.destroy(); }
  return replies();
}

test('Private socket, persistent session handoff, Unicode transport, and exclusive control', async () => {
  const service = await setup();
  try {
    assert.equal((await stat(service.path)).mode & 0o777, 0o600);
    assert.equal((await stat(join(service.path, '..'))).mode & 0o777, 0o700);
    const first = await service.first.call('start');
    await assert.rejects(service.second.call('screenshot'), /Another agent/);
    const text = '✓ café 😊'.repeat(10000);
    assert.equal((await service.first.call('clipboard_set', { text })).params.text, text);
    service.first.close();
    await sleep(30);
    const next = await service.second.call('screenshot');
    assert.equal(first.generation, next.generation);
    assert.equal(service.state.starts, 1);
    assert.equal(service.state.stops, 0);
    const status = await service.second.call('status');
    assert.equal(status.persistentService, true);
    assert.equal(status.controlOwner, 'self');
  } finally { await service.close(); }
});

test('Stop blocks auto input until an explicit start, and works from another client', async () => {
  const service = await setup();
  try {
    await service.first.call('start');
    await service.second.stop();
    await assert.rejects(service.first.call('screenshot'), /was stopped/);
    assert.equal((await service.first.call('status')).suspended, true);
    await service.first.call('start');
    assert.equal((await service.first.call('screenshot')).active, true);
    assert.equal(service.state.stops, 1);
    assert.equal((await service.first.call('status')).suspended, false);
  } finally { await service.close(); }
});

test('Idle ownership can transfer without shutting down the native desktop session', async () => {
  const service = await setup();
  try {
    await service.first.call('start');
    await sleep(90);
    await service.second.call('screenshot');
    await assert.rejects(service.first.call('screenshot'), /Another agent/);
    assert.equal(service.state.stops, 0);
  } finally { await service.close(); }
});

test('Client cancellation aborts only its running work and does not suspend the service', async () => {
  const service = await setup();
  try {
    await service.first.call('start');
    const running = assert.rejects(service.first.call('screenshot', { slow: true }, 5000), /stopped/);
    await sleep(20);
    // An aborted MCP request calls stop(reason): a cancel, not the global computer_stop.
    assert.deepEqual(await service.first.stop('Desktop operation cancelled by MCP client'), { cancelled: true });
    await running;
    const status = await service.first.call('status');
    assert.equal(status.suspended, false);
    assert.equal((await service.first.call('screenshot')).active, true);
    // A non-owner cannot cancel the owner's work.
    const owned = assert.rejects(service.first.call('screenshot', { slow: true }, 5000));
    await sleep(20);
    await service.second.call('status');
    assert.deepEqual(await service.second.stop('cancel'), { cancelled: false });
    service.first.close();
    await owned;
  } finally { await service.close(); }
});

test('Owner disconnect mid-operation cancels the native work; idle disconnect does not', async () => {
  const service = await setup();
  try {
    await service.first.call('start');
    service.first.close();
    await sleep(20);
    assert.equal(service.state.stops, 0, 'Idle disconnect keeps the native session');
    const busyClient = service.client();
    const running = busyClient.call('screenshot', { slow: true }, 5000);
    await sleep(20);
    busyClient.close();
    await assert.rejects(running);
    await sleep(20);
    assert.equal(service.state.stops, 1);
    assert.equal((await service.second.call('status')).suspended, false);
    assert.equal((await service.second.call('screenshot')).active, true, 'Next agent takes over immediately');
  } finally { await service.close(); }
});

test('Client timeout cancels the busy operation in the service', async () => {
  const service = await setup();
  try {
    await service.first.call('start');
    await assert.rejects(service.first.call('screenshot', { slow: true }, 50), /timed out and was cancelled/);
    await sleep(20);
    assert.equal(service.state.stops, 1);
    assert.equal((await service.first.call('screenshot')).active, true, 'Reconnects with a fresh connection');
  } finally { await service.close(); }
});

test('Start after stop waits for the previous native helper to exit', async () => {
  const service = await setup({ bridge: fakeBridge({ exitMs: 80 }) });
  try {
    await service.first.call('start');
    await service.second.call('status');
    const stopping = service.second.stop();
    await sleep(5);
    await service.first.call('start');
    await stopping;
    assert.equal(service.state.overlap, false, 'Never two native sessions at once');
    assert.equal((await service.first.call('status')).suspended, false);
  } finally { await service.close(); }
});

test('Suspension survives a service restart within the login session', async () => {
  const service = await setup();
  try {
    await service.first.call('start');
    await service.first.stop();
    await service.restart();
    await assert.rejects(service.second.call('screenshot'), /was stopped/);
    await service.second.call('start');
    await service.restart();
    assert.equal((await service.first.call('screenshot')).active, true);
  } finally { await service.close(); }
});

test('Connection and per-client queue limits; malformed requests are rejected', async () => {
  const service = await setup({ daemon: { maxClients: 2, maxPending: 2 } });
  try {
    await service.first.call('status');
    await service.second.call('status');
    const third = service.client();
    await assert.rejects(third.call('status'), /Too many local desktop clients/);
    service.second.close();
    await sleep(20);
    assert.equal((await service.client().call('status')).persistentService, true, 'A slot frees on disconnect');

    await service.first.call('start');
    const queued = [1, 2, 3].map(() => service.first.call('screenshot', { slow: true }, 5000));
    const settled = Promise.allSettled(queued);
    await sleep(20);
    assert.deepEqual(await service.first.stop('cancel'), { cancelled: true }, 'Cancel is exempt from the queue limit');
    const results = await settled;
    assert.match(results[2].reason.message, /Too many desktop requests/);

    service.first.close();
    const malformed = ['not json', '{"id":1,"method":"exec"}',
      '{"id":2,"method":"screenshot","params":[1]}', '{"id":3,"method":"batch","params":{"actions":[]}}'];
    let replies;
    // The freed slot is only visible once the service has processed the disconnect, so retry a rejection briefly.
    for (let attempt = 0; attempt < 50; ++attempt) {
      replies = await rawExchange(service.path, malformed);
      if (!/Too many local desktop clients/.test(replies[0]?.error)) break;
      await sleep(20);
    }
    assert.deepEqual(replies.map(reply => reply.id), [null, 1, 2, 3], JSON.stringify(replies));
    assert.ok(replies.every(reply => reply.error && !('result' in reply)), JSON.stringify(replies));
    assert.match(replies[0].error, /Invalid desktop service request/);
    assert.match(replies[1].error, /Invalid desktop service request/);
    assert.match(replies[2].error, /Invalid desktop service parameters/);
  } finally { await service.close(); }
});

test('Oversized request lines close the connection', async () => {
  const service = await setup({ daemon: { maxLineBytes: 1024 } });
  try {
    await assert.rejects(service.first.call('clipboard_set', { text: 'x'.repeat(2048) }), /disconnected/);
    assert.equal((await service.first.call('status')).persistentService, true);
  } finally { await service.close(); }
});

// Holds the client's connection attempt open until release(), like a slow socket connect or service launch.
function deferConnect(client) {
  const real = client.openSocket.bind(client);
  const gate = {};
  gate.opened = new Promise(resolve => { gate.release = resolve; });
  client.openSocket = () => gate.opened.then(real).then(socket => { gate.socket = socket; return socket; });
  return gate;
}
const wait = { type: 'wait', durationMs: 0 };

test('Cancelling a call that is still connecting never sends it, and does not suspend others', async () => {
  const service = await setup();
  try {
    const client = service.client();
    const gate = deferConnect(client);
    const input = client.call('batch', { actions: [wait] });
    await sleep(10);
    assert.deepEqual(await client.stop('Desktop operation cancelled by MCP client'), { cancelled: true });
    gate.release();
    await assert.rejects(input, /cancelled before it was sent/);
    await sleep(30);
    assert.ok(!service.state.executed.includes('batch'), 'Cancelled input never reached the native helper');
    // The connection itself is fine to reuse, and nobody was suspended.
    assert.equal((await client.call('batch', { actions: [wait] })).method, 'batch');
    const status = await service.second.call('status');
    assert.equal(status.suspended, false);
    assert.equal(service.state.stops, 0);
  } finally { await service.close(); }
});

test('Global stop also drops this client\'s own unsent calls', async () => {
  const service = await setup();
  try {
    const client = service.client();
    const gate = deferConnect(client);
    const input = client.call('batch', { actions: [wait] });
    await sleep(10);
    const stopped = client.stop();
    gate.release();
    await assert.rejects(input, /cancelled before it was sent/);
    assert.equal((await stopped).suspended, true);
    assert.ok(!service.state.executed.includes('batch'));
  } finally { await service.close(); }
});

test('Closing during a pending connect discards the late socket; the bridge can reconnect later', async () => {
  const service = await setup();
  try {
    const client = service.client();
    const gate = deferConnect(client);
    const input = client.call('batch', { actions: [wait] });
    await sleep(10);
    client.close();
    gate.release();
    await assert.rejects(input);
    await sleep(30);
    assert.ok(gate.socket?.destroyed, 'Late connection was destroyed');
    assert.equal(client.socket, null);
    assert.ok(!service.state.executed.includes('batch'));
    client.openSocket = DaemonBridge.prototype.openSocket;
    assert.equal((await client.call('status')).persistentService, true, 'Reconnects after close');
  } finally { await service.close(); }
});

test('A client that disconnects while teardown is pending never takes ownership', async () => {
  const service = await setup({ bridge: fakeBridge({ exitMs: 80 }) });
  try {
    await service.first.call('start');
    const late = service.client();
    await late.call('status');
    const stopping = service.second.stop();
    await sleep(5);
    const start = late.call('start');
    await sleep(5);
    late.close();
    await assert.rejects(start);
    await stopping;
    await sleep(20);
    assert.equal(service.state.starts, 1, 'Dead client\'s start never ran');
    const status = await service.second.call('status');
    assert.equal(status.suspended, true, 'Dead client did not clear the stop');
    assert.equal(status.controlOwner, null);
  } finally { await service.close(); }
});

test('Unit rendering escapes ExecStart words and path settings per systemd syntax', () => {
  assert.equal(execArg('/a b/100%$X "q"\\'), '"/a b/100%%$$X \\"q\\"\\\\"');
  assert.equal(unitPath('/a b/100%$X "q"'), '/a b/100%%$X "q"');
  assert.throws(() => unitPath('relative/path'), /absolute/);
  assert.throws(() => unitPath('/a\nExecStartPre=/bin/sh'), /control characters/);
  assert.throws(() => execArg('/a\nb'), /control characters/);
  const unit = renderUnit({ node: '/opt/node/bin/node', runtime: '/home/u/.local/share/linux-computer-use/runtime' });
  assert.match(unit, /^WorkingDirectory=\/home\/u\/\.local\/share\/linux-computer-use\/runtime$/m, 'No quotes on path settings');
  assert.match(unit, /^ExecStart="\/opt\/node\/bin\/node" "\/home\/u\/\.local\/share\/linux-computer-use\/runtime\/src\/daemon\.mjs"$/m);
});
