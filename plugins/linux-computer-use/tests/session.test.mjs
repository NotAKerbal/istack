import { test } from 'node:test';
import assert from 'node:assert/strict';
import { registerTools } from '../src/tools.mjs';

const decode = result => JSON.parse(result.content[0].text);
function setup() {
  const handlers = new Map();
  let finish;
  const calls = [];
  const bridge = {
    call(method) {
      calls.push(method);
      if (method === 'start') return new Promise(resolve => { finish = resolve; });
      return Promise.resolve({ active: true });
    },
    stop() { calls.push('stop'); },
  };
  registerTools({ registerTool: (name, config, handler) => handlers.set(name, handler) }, bridge);
  return { calls, finish: value => finish(value),
    invoke: (name, args = {}) => handlers.get(name)(args, { signal: new AbortController().signal }) };
}

test('Human portal consent returns pending promptly, remains observable, and prevents premature input', async () => {
  const session = setup();
  const start = decode(await session.invoke('computer_start', { clipboard: false }));
  assert.equal(start.starting, true);
  assert.equal(decode(await session.invoke('computer_status')).starting, true);
  assert.equal(decode(await session.invoke('computer_start')).starting, true);
  const input = await session.invoke('computer_input', { actions: [{ type: 'key', keys: ['a'] }] });
  assert.equal(input.isError, true);
  assert.deepEqual(session.calls, ['start'], 'No duplicate request or input should reach the pending helper');
  session.finish({ backend: 'wayland-portal' });
  await Promise.resolve();
  const status = decode(await session.invoke('computer_status'));
  assert.equal(status.active, true);
  assert.equal(status.lastStart.backend, 'wayland-portal');
});

test('Stopping a pending portal request prevents late completion from reviving startup state', async () => {
  const session = setup();
  const starting = session.invoke('computer_start');
  await session.invoke('computer_stop');
  session.finish({ backend: 'old-session' });
  await starting;
  const status = decode(await session.invoke('computer_status'));
  assert.equal(status.lastStart, undefined);
  assert.deepEqual(session.calls, ['start', 'stop', 'status']);
});
