import { test } from 'node:test';
import assert from 'node:assert/strict';
import { setTimeout as sleep } from 'node:timers/promises';
import { fileURLToPath } from 'node:url';
import { NativeBridge } from '../src/bridge.mjs';
const create = () => new NativeBridge({ python: process.execPath,
  worker: fileURLToPath(new URL('./fixtures/native-helper.mjs', import.meta.url)) });

test('Stop cancels in-flight and queued operations; next request uses a new helper', async () => {
  const bridge = create();
  try {
    const before = await bridge.call('status');
    const results = Promise.allSettled([bridge.call('slow'), bridge.call('must-not-execute')]);
    await sleep(20);
    bridge.stop();
    const cancelled = await results;
    assert.ok(cancelled.every(x => x.status === 'rejected'));
    const after = await bridge.call('status');
    assert.notEqual(before.pid, after.pid);
    assert.equal(after.method, 'status');
  } finally { bridge.stop(); }
});

test('Timeout kills the helper and invalidates queued actions', async () => {
  const bridge = create();
  try {
    const results = await Promise.allSettled([bridge.call('slow', {}, 100), bridge.call('must-not-execute')]);
    assert.ok(results.every(x => x.status === 'rejected'));
    assert.match(results[0].reason.message, /timed out/);
    assert.equal((await bridge.call('status')).method, 'status');
  } finally { bridge.stop(); }
});

test('Native helper crash rejects outstanding call and allows a clean restart', async () => {
  const bridge = create();
  try {
    await assert.rejects(bridge.call('crash'), /exited/);
    assert.equal((await bridge.call('status')).method, 'status');
  } finally { bridge.stop(); }
});

const alive = pid => { try { process.kill(pid, 0); return true; } catch { return false; } };

test('Repeated stop after a timeout waits for the stuck helper to exit', async () => {
  const bridge = new NativeBridge({ python: process.execPath, killTimeoutMs: 150,
    worker: fileURLToPath(new URL('./fixtures/native-helper.mjs', import.meta.url)) });
  const { pid } = await bridge.call('status');
  try {
    // A stopped helper ignores SIGTERM, as a wedged native call would; only SIGKILL ends it.
    process.kill(pid, 'SIGSTOP');
    const timedOut = bridge.call('status', {}, 50);
    await assert.rejects(timedOut, /timed out/);
    // The timeout already detached the helper; a repeated stop must still wait for it to exit.
    assert.equal(alive(pid), true);
    await bridge.stop();
    assert.equal(alive(pid), false);
    assert.notEqual((await bridge.call('status')).pid, pid);
  } finally { try { process.kill(pid, 'SIGKILL'); } catch {} await bridge.stop(); }
});

test('Requests queued behind a timeout wait for teardown before spawning a helper', async () => {
  const bridge = new NativeBridge({ python: process.execPath, killTimeoutMs: 150,
    worker: fileURLToPath(new URL('./fixtures/native-helper.mjs', import.meta.url)) });
  const { pid } = await bridge.call('status');
  try {
    process.kill(pid, 'SIGSTOP');
    await assert.rejects(bridge.call('status', {}, 50), /timed out/);
    const after = await bridge.call('status');
    assert.notEqual(after.pid, pid);
    assert.equal(alive(pid), false, 'replacement responded while the original helper was alive');
  } finally { try { process.kill(pid, 'SIGKILL'); } catch {} await bridge.stop(); }
});

test('Stop during teardown cancels work queued in the previous epoch', async () => {
  const bridge = new NativeBridge({ python: process.execPath, killTimeoutMs: 150,
    worker: fileURLToPath(new URL('./fixtures/native-helper.mjs', import.meta.url)) });
  const { pid } = await bridge.call('status');
  try {
    process.kill(pid, 'SIGSTOP');
    const first = bridge.stop();
    const queued = bridge.call('status');
    const second = bridge.stop();
    await assert.rejects(queued, /cancelled by stop/);
    await Promise.all([first, second]);
    assert.equal(alive(pid), false);
    assert.equal(bridge.child, null, 'cancelled work must not spawn a helper');
  } finally { try { process.kill(pid, 'SIGKILL'); } catch {} await bridge.stop(); }
});

test('Failed spawn rejects and does not wedge later stops', async () => {
  const bridge = new NativeBridge({ python: '/nonexistent/linux-cua-python' });
  await assert.rejects(bridge.call('status'), /ENOENT|exited/);
  await bridge.stop();
  assert.equal(bridge.retiring.size, 0);
});
