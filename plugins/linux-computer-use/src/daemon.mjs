#!/usr/bin/env node
import net from 'node:net';
import { mkdir, chmod, lstat, unlink, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { randomUUID } from 'node:crypto';
import { pathToFileURL } from 'node:url';
import { NativeBridge } from './bridge.mjs';
import { socketPath } from './runtime-config.mjs';
import { batchSchema } from './tools.mjs';

const methods = new Set(['status', 'start', 'screenshot', 'batch', 'accessibility', 'element_action', 'clipboard_set', 'stop', 'cancel']);
const timeouts = { start: 210000, batch: 35000 };

export async function createDesktopDaemon({ path = socketPath, bridge = new NativeBridge(), leaseMs = 60000,
  maxClients = 16, maxPending = 8, maxLineBytes = 1024 * 1024 } = {}) {
  const dir = dirname(path);
  // Survives service restarts (RuntimeDirectoryPreserve=restart) but not logout.
  const suspendMarker = join(dir, 'suspended');
  await mkdir(dir, { recursive: true, mode: 0o700 });
  const info = await lstat(dir);
  if (info.isSymbolicLink() || info.uid !== process.getuid()) throw new Error('Desktop socket directory must belong to the current user and not be a symlink');
  await chmod(dir, 0o700);
  try {
    const old = await lstat(path);
    if (!old.isSocket() || old.uid !== process.getuid()) throw new Error('Unexpected object at desktop socket path');
    const live = await new Promise(resolve => {
      const probe = net.createConnection(path);
      probe.setTimeout(500, () => { probe.destroy(); resolve(true); });
      probe.once('connect', () => { probe.end(); resolve(true); });
      probe.once('error', error => resolve(error.code !== 'ECONNREFUSED'));
    });
    if (live) throw new Error('A desktop service already owns this socket');
    await unlink(path);
  } catch (error) { if (error.code !== 'ENOENT') throw error; }

  let owner = null;
  let lastUsed = 0;
  let busy = 0;
  let suspended = existsSync(suspendMarker);
  let cachedStatus = { active: false, backend: 'gnome-native' };
  // The native helper holds a desktop lock until it exits; never start a new one before the old is gone.
  let halting = Promise.resolve();
  const halt = () => {
    cachedStatus = { ...cachedStatus, active: false };
    const done = Promise.resolve(bridge.stop('Desktop operation cancelled')).catch(() => {});
    halting = Promise.all([halting, done]).then(() => {});
    return halting;
  };
  const setSuspended = async value => {
    suspended = value;
    if (value) await writeFile(suspendMarker, new Date().toISOString() + '\n', { mode: 0o600 });
    else await unlink(suspendMarker).catch(error => { if (error.code !== 'ENOENT') throw error; });
  };
  const clients = new Set();
  const reply = (socket, message) => { if (!socket.destroyed) socket.write(JSON.stringify(message) + '\n'); };
  const server = net.createServer(socket => {
    if (clients.size >= maxClients) {
      // Drain so EOF is seen, and bound the lifetime, so a rejected socket never lingers.
      socket.on('error', () => {});
      socket.resume();
      socket.setTimeout(1000, () => socket.destroy());
      socket.end(JSON.stringify({ id: null, error: 'Too many local desktop clients are connected.' }) + '\n');
      return;
    }
    clients.add(socket);
    const clientId = randomUUID();
    let buffer = '';
    let pending = 0;
    let connected = true;
    socket.setEncoding('utf8');
    socket.on('error', () => {});
    socket.on('data', chunk => {
      buffer += chunk;
      let newline;
      while ((newline = buffer.indexOf('\n')) >= 0) {
        const line = buffer.slice(0, newline);
        buffer = buffer.slice(newline + 1);
        if (Buffer.byteLength(line) > maxLineBytes) { socket.destroy(); return; }
        void dispatch(line);
      }
      if (Buffer.byteLength(buffer) > maxLineBytes) socket.destroy();
    });
    async function dispatch(line) {
      let request;
      let counted = false;
      ++pending;
      try {
        request = JSON.parse(line);
        if (!request || !Number.isSafeInteger(request.id) || !methods.has(request.method)) throw new Error('Invalid desktop service request');
        const { method } = request;
        const params = request.params ?? {};
        if (typeof params !== 'object' || Array.isArray(params)) throw new Error('Invalid desktop service parameters');
        if (method === 'stop') {
          // Global: any local agent may stop control, and it stays suspended until an explicit start.
          owner = null;
          const halted = halt();
          await setSuspended(true);
          await halted;
          reply(socket, { id: request.id, result: { active: false, suspended: true } });
          return;
        }
        if (method === 'cancel') {
          // Client-side cancellation aborts this client's own running work without suspending the service.
          const cancelled = owner === clientId && busy > 0;
          if (cancelled) await halt();
          reply(socket, { id: request.id, result: { cancelled } });
          return;
        }
        // Stop and cancel above are exempt so a flooded client can always be halted.
        if (pending > maxPending) throw new Error('Too many desktop requests are queued for this client');
        if (method === 'status') {
          if (!busy) cachedStatus = await bridge.call('status');
          reply(socket, { id: request.id, result: { ...cachedStatus, persistentService: true,
            servicePid: process.pid, suspended, busy: Boolean(busy), controlOwner: owner === clientId ? 'self' : owner ? 'another-agent' : null } });
          return;
        }
        if (method === 'batch') batchSchema.parse(params);
        await halting;
        // A client that disconnected during teardown must not take ownership or queue native work.
        if (!connected) throw new Error('Desktop client disconnected');
        // Synchronous from here until the call is queued, so stop/ownership cannot interleave.
        if (suspended && method !== 'start') throw new Error('Desktop control was stopped. Call computer_start to resume.');
        if (owner && owner !== clientId && (busy || Date.now() - lastUsed < leaseMs)) {
          throw new Error('Another agent currently controls the desktop. It must disconnect or leave control idle for 60 seconds.');
        }
        owner = clientId;
        lastUsed = Date.now();
        ++busy; counted = true;
        const call = bridge.call(method, params, timeouts[method] ?? 20000);
        if (method === 'start') await setSuspended(false);
        const result = await call;
        cachedStatus = { ...cachedStatus, active: true, ...(method === 'start' ? result : {}) };
        reply(socket, { id: request.id, result });
      } catch (error) {
        reply(socket, { id: request?.id ?? null, error: error.message });
      } finally {
        --pending;
        if (counted) { --busy; if (owner === clientId) lastUsed = Date.now(); }
      }
    }
    socket.on('close', () => {
      connected = false;
      clients.delete(socket);
      if (owner === clientId) {
        // An idle session survives disconnect; a disconnect mid-operation cancels it.
        if (busy) void halt();
        owner = null;
      }
    });
  });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(path, resolve); });
  await chmod(path, 0o600);
  return { path, async close() {
    for (const client of clients) client.destroy();
    await Promise.resolve(bridge.stop('Desktop service shutting down')).catch(() => {});
    await new Promise(resolve => server.close(resolve));
    await unlink(path).catch(error => { if (error.code !== 'ENOENT') throw error; });
  } };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.umask(0o077);
  process.env.LINUX_CUA_BACKEND = 'mutter';
  const service = await createDesktopDaemon();
  console.error('Linux Computer Use service ready on a private user socket');
  for (const signal of ['SIGTERM', 'SIGINT']) process.once(signal, async () => { await service.close(); process.exit(0); });
}
