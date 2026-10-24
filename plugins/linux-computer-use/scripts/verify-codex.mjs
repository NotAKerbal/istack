#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

const listed = spawnSync('codex', ['mcp', 'list', '--json'], { encoding: 'utf8' });
if (listed.status !== 0) throw new Error(listed.stderr || 'Codex MCP discovery failed');
const config = JSON.parse(listed.stdout).find(server => server.name === 'linux-computer-use');
if (!config?.enabled || config.transport?.type !== 'stdio') throw new Error('Linux Computer Use is not installed and enabled. Run npm run setup:codex.');
const launch = config.transport;
const env = { ...launch.env };
for (const name of launch.env_vars || []) if (process.env[name] !== undefined) env[name] = process.env[name];
const client = new Client({ name: 'codex-plugin-verifier', version: '0.1.0' });
const transport = new StdioClientTransport({ command: launch.command, args: launch.args,
  cwd: launch.cwd, env, stderr: 'inherit' });
try {
  await client.connect(transport);
  const { tools } = await client.listTools();
  const result = await client.callTool({ name: 'computer_status', arguments: {} });
  if (result.isError) throw new Error(result.content[0].text);
  const status = JSON.parse(result.content[0].text);
  console.log(JSON.stringify({ installedServer: true, tools: tools.map(tool => tool.name),
    ready: status.ready, active: status.active, backend: status.backend, portal: status.portal }, null, 2));
  if (!status.ready || tools.length !== 8) throw new Error('Installed server loaded, but desktop prerequisites or tool discovery are incomplete. Run npm run doctor.');
} finally { await client.close(); }
