import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { fileURLToPath } from 'node:url';
import { batchSchema } from '../src/tools.mjs';

test('MCP handshake, discovery, capabilities, validation, inactive input, and stop', async () => {
  const transport = new StdioClientTransport({ command: process.execPath,
    args: [fileURLToPath(new URL('../src/server.mjs', import.meta.url))], stderr: 'pipe', env: { LINUX_CUA_TRANSPORT: 'direct' } });
  const client = new Client({ name: 'integration-test', version: '1.0.0' });
  try {
    await client.connect(transport);
    const { tools } = await client.listTools();
    assert.equal(tools.length, 8);
    assert.ok(tools.some(t => t.name === 'computer_input'));
    const status = await client.callTool({ name: 'computer_status', arguments: {} });
    assert.equal(Boolean(status.isError), false, status.content[0].text);
    const data = JSON.parse(status.content[0].text);
    assert.equal(data.platform, 'linux');
    assert.equal(data.active, false);
    const inactive = await client.callTool({ name: 'computer_screenshot', arguments: {} });
    assert.equal(inactive.isError, true);
    assert.match(inactive.content[0].text, /No active desktop session/);
    const invalid = await client.callTool({ name: 'computer_input', arguments: {
      actions: [{ type: 'click', x: 1, y: 1 }],
    } });
    assert.equal(invalid.isError, true);
    const stop = await client.callTool({ name: 'computer_stop', arguments: {} });
    assert.equal(JSON.parse(stop.content[0].text).active, false);
  } finally { await client.close(); }
});

test('Batch schemas reject unbounded or ambiguous input and apply defaults', () => {
  const parse = a => batchSchema.safeParse({ actions: a });
  assert.equal(parse([{ type: 'key', keys: ['CTRL', 'a'] }]).success, true);
  assert.equal(parse([{ type: 'click', frameId: 'abc', x: Infinity, y: 2 }]).success, false);
  assert.equal(parse([{ type: 'wait', durationMs: 20000 }]).success, false);
  assert.equal(parse(Array.from({ length: 31 }, () => ({ type: 'key', keys: ['a'] }))).success, false);
  assert.equal(parse(Array.from({ length: 10 }, () => ({ type: 'wait', durationMs: 2000 }))).success, false);
  assert.equal(parse([{ type: 'shell', command: 'anything' }]).success, false);
  assert.equal(parse([{ type: 'type', text: 'test', unexpected: 1 }]).success, false);
  assert.equal(parse([{ type: 'click', frameId: 'abc', x: 5, y: 4 }]).data.actions[0].count, 1);
});
