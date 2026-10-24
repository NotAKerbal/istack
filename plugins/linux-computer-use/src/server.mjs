#!/usr/bin/env node
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { NativeBridge } from './bridge.mjs';
import { registerTools } from './tools.mjs';
import { DaemonBridge } from './daemon-bridge.mjs';
import { runtimeConfig } from './runtime-config.mjs';

const bridge = (process.env.LINUX_CUA_TRANSPORT || runtimeConfig().transport) === 'daemon'
  ? new DaemonBridge() : new NativeBridge();
const server = new McpServer({ name: 'linux-computer-use', version: '0.2.0' }, {
  instructions: 'Linux desktop control. Check computer_status for backend and lock state. The configured GNOME native service starts automatically on screenshot/input and persists across agents without the portal picker. Portal fallback requires computer_start and user sharing approval. Use screenshot image pixels and frameId for pointer actions. Observe after changes. Input affects the user’s live desktop and focused app. computer_stop globally suspends service control until computer_start.',
});
registerTools(server, bridge);
for (const signal of ['SIGINT', 'SIGTERM']) {
  process.once(signal, () => { bridge.close ? bridge.close() : bridge.stop(); process.exit(0); });
}
process.stdin.once('end', () => { bridge.close ? bridge.close() : bridge.stop(); });
await server.connect(new StdioServerTransport());
