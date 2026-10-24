import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { fileURLToPath } from 'node:url';

const workerPath = fileURLToPath(new URL('../native/worker.py', import.meta.url));

export class NativeBridge {
  constructor({ python = process.env.LINUX_CUA_PYTHON || '/usr/bin/python3', worker = workerPath,
    killTimeoutMs = 1000, exitTimeoutMs = 2000 } = {}) {
    this.python = python;
    this.worker = worker;
    this.killTimeoutMs = killTimeoutMs;
    this.exitTimeoutMs = exitTimeoutMs;
    this.child = null;
    // Retired helpers that may still hold the desktop lock or be mid-input.
    this.retiring = new Set();
    this.pending = new Map();
    this.nextId = 1;
    this.tail = Promise.resolve();
    this.epoch = 0;
  }

  ensureWorker() {
    if (this.child) return this.child;
    const args = this.python === process.execPath ? [this.worker] : ['-u', this.worker];
    const proc = spawn(this.python, args, {
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' },
    });
    const child = { proc, retired: false, gone: null };
    // A failed spawn emits close but never exit.
    child.exited = new Promise(resolve => { proc.once('exit', resolve); proc.once('close', resolve); });
    this.child = child;
    // GStreamer and native diagnostics go to stderr; never corrupt MCP stdout.
    proc.stderr.on('data', data => process.stderr.write(data));
    const lines = createInterface({ input: proc.stdout });
    lines.on('line', line => {
      try {
        const message = JSON.parse(line);
        const pending = this.pending.get(message.id);
        if (!pending || pending.child !== child) return;
        clearTimeout(pending.timer);
        this.pending.delete(message.id);
        if (message.error) pending.reject(new Error(message.error));
        else pending.resolve(message.result);
      } catch {
        this.retire(child, new Error('Invalid response from native desktop helper'));
      }
    });
    proc.stdin.on('error', error => this.retire(child, error));
    proc.on('error', error => this.retire(child, error));
    child.exited.then(() => {
      lines.close();
      this.retiring.delete(child);
      this.retire(child, new Error(`Desktop helper exited (${proc.signalCode || proc.exitCode})`));
    });
    return child;
  }

  // Detach a helper, reject its calls, and terminate it. Idempotent per helper.
  retire(child, error) {
    if (this.child === child) this.child = null;
    for (const [id, pending] of this.pending) {
      if (pending.child !== child) continue;
      clearTimeout(pending.timer);
      pending.reject(error);
      this.pending.delete(id);
    }
    if (child.retired) return;
    child.retired = true;
    const { proc } = child;
    if (proc.exitCode !== null || proc.signalCode !== null) return;
    this.retiring.add(child);
    let escalate;
    child.gone = new Promise((resolve, reject) => {
      const kill = setTimeout(() => {
        proc.kill('SIGKILL');
        escalate = setTimeout(() => reject(new Error('Previous desktop helper did not exit; refusing to start another')),
          this.exitTimeoutMs);
        escalate.unref();
      }, this.killTimeoutMs);
      kill.unref();
      child.exited.then(() => { clearTimeout(kill); clearTimeout(escalate); resolve(); });
    });
    child.gone.catch(() => {});
    proc.kill('SIGTERM');
  }

  // Resolves once every retired helper has exited, so a replacement never races the old one.
  async teardown() {
    await Promise.all([...this.retiring].map(child => child.gone));
  }

  call(method, params = {}, timeoutMs = 20000) {
    const epoch = this.epoch;
    const task = this.tail.then(async () => {
      if (epoch !== this.epoch) throw new Error('Desktop operation cancelled by stop');
      await this.teardown();
      if (epoch !== this.epoch) throw new Error('Desktop operation cancelled by stop');
      return this.request(method, params, timeoutMs);
    });
    this.tail = task.catch(() => {});
    return task;
  }

  request(method, params, timeoutMs) {
    const child = this.ensureWorker();
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        // A timed-out input must never keep running unseen or race the next call.
        this.stop('Desktop helper timed out; its session was closed').catch(() => {});
      }, timeoutMs);
      this.pending.set(id, { child, resolve, reject, timer });
      child.proc.stdin.write(`${JSON.stringify({ id, method, params })}\n`, error => {
        if (error) this.retire(child, error);
      });
    });
  }

  // Cancels in-flight and queued work immediately; resolves after the helper has exited.
  stop(reason = 'Desktop session stopped') {
    ++this.epoch;
    if (this.child) this.retire(this.child, new Error(reason));
    return this.teardown();
  }
}
