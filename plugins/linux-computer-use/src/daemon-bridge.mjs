import net from 'node:net';
import { createInterface } from 'node:readline';
import { execFile } from 'node:child_process';
import { existsSync } from 'node:fs';
import { promisify } from 'node:util';
import { setTimeout as sleep } from 'node:timers/promises';
import { socketPath, serviceName, userRuntimeDir } from './runtime-config.mjs';

const execFileAsync = promisify(execFile);
const missing = error => ['ENOENT', 'ECONNREFUSED'].includes(error.code);

export class DaemonBridge {
  constructor({ path = socketPath, startService = true } = {}) {
    this.path = path;
    this.startService = startService;
    this.socket = null;
    this.connecting = null;
    this.pending = new Map();
    this.nextId = 1;
    // epoch: bumped by cancel/stop/close; a call from an older epoch is never sent.
    // generation: bumped by close; a connection opened for an older generation is discarded.
    this.epoch = 0;
    this.generation = 0;
    this.waiting = 0;
  }

  async connect() {
    if (this.socket && !this.socket.destroyed) return this.socket;
    if (this.connecting?.generation !== this.generation) {
      const attempt = { generation: this.generation };
      attempt.promise = this.open(attempt.generation).finally(() => { if (this.connecting === attempt) this.connecting = null; });
      this.connecting = attempt;
    }
    return this.connecting.promise;
  }

  async open(generation) {
    let socket;
    try { socket = await this.openSocket(); }
    catch (error) {
      if (!this.startService || !missing(error)) throw error;
      await this.launchService();
      for (let attempt = 0; ; ++attempt) {
        try { socket = await this.openSocket(); break; }
        catch (retryError) {
          if (!missing(retryError) || attempt === 49) throw retryError;
          await sleep(100);
        }
      }
    }
    if (generation !== this.generation) {
      socket.destroy();
      throw new Error('Local desktop connection closed before it was established');
    }
    this.socket = socket;
    const lines = createInterface({ input: socket });
    // readline re-emits socket errors; they are handled by fail() below and must not crash the MCP server.
    lines.on('error', () => {});
    lines.on('line', line => {
      let message;
      try { message = JSON.parse(line); }
      catch { socket.destroy(new Error('Invalid local desktop service response')); return; }
      // id null: the service rejected the connection or an unparseable request.
      if (message?.id == null) { if (message?.error) socket.destroy(new Error(message.error)); return; }
      const pending = this.pending.get(message.id);
      if (!pending) return;
      clearTimeout(pending.timer);
      this.pending.delete(message.id);
      if (message.error) pending.reject(new Error(message.error));
      else pending.resolve(message.result);
    });
    const fail = error => {
      if (this.socket !== socket) return;
      this.socket = null;
      for (const pending of this.pending.values()) {
        clearTimeout(pending.timer);
        pending.reject(error);
      }
      this.pending.clear();
    };
    socket.on('error', error => fail(error));
    socket.on('close', () => { lines.close(); fail(new Error('Local desktop service disconnected')); });
    return socket;
  }

  async launchService() {
    // MCP hosts often strip the session environment; systemctl --user needs it to find the user manager.
    const runtime = process.env.XDG_RUNTIME_DIR || userRuntimeDir;
    const env = { ...process.env, XDG_RUNTIME_DIR: runtime };
    if (!env.DBUS_SESSION_BUS_ADDRESS && existsSync(runtime + '/bus')) env.DBUS_SESSION_BUS_ADDRESS = `unix:path=${runtime}/bus`;
    const systemctl = existsSync('/usr/bin/systemctl') ? '/usr/bin/systemctl' : 'systemctl';
    try { await execFileAsync(systemctl, ['--user', 'start', serviceName], { timeout: 10000, env }); }
    catch (error) {
      const detail = String(error.stderr || error.message).trim().split('\n')[0];
      throw new Error(`Could not start the local desktop service (${detail}). Run npm run setup:service.`);
    }
  }

  openSocket() {
    return new Promise((resolve, reject) => {
      const socket = net.createConnection(this.path);
      socket.setTimeout(3000, () => socket.destroy(new Error('Local desktop service connection timed out')));
      const failure = error => reject(error);
      socket.once('error', failure);
      socket.once('connect', () => {
        socket.setTimeout(0);
        socket.removeListener('error', failure);
        resolve(socket);
      });
    });
  }

  async call(method, params = {}, timeoutMs = 20000) {
    const epoch = this.epoch;
    let socket;
    ++this.waiting;
    try { socket = await this.connect(); }
    finally { --this.waiting; }
    // Synchronous from this check to the write, so a cancel can never slip in between.
    if (epoch !== this.epoch) throw new Error('Desktop operation cancelled before it was sent');
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        // Closing a busy owner's connection cancels native work in the service.
        socket.destroy();
        reject(new Error('Local desktop operation timed out and was cancelled'));
      }, timeoutMs);
      this.pending.set(id, { resolve, reject, timer });
      socket.write(JSON.stringify({ id, method, params }) + '\n');
    });
  }

  // stop() with no reason is the user's computer_stop: global, suspends until an explicit start.
  // stop(reason) is a client cancellation (aborted MCP request): only this client's running work is cancelled.
  async stop(reason) {
    if (reason === undefined) {
      ++this.epoch; // Unsent calls from this client must not run after its own stop.
      return this.call('stop', {}, 5000);
    }
    return this.cancel();
  }

  async cancel() {
    const unsent = this.waiting > 0;
    ++this.epoch;
    if (!this.socket || this.socket.destroyed) return { cancelled: unsent };
    const result = await this.call('cancel', {}, 5000);
    return { ...result, cancelled: unsent || result.cancelled };
  }

  close() {
    ++this.epoch;
    ++this.generation;
    this.socket?.end();
  }
}
