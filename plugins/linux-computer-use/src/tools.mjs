import { z } from 'zod';

const point = {
  frameId: z.string().min(1).describe('frameId of the screenshot whose image pixels you are using'),
  x: z.number().finite().nonnegative(),
  y: z.number().finite().nonnegative(),
};
const action = z.discriminatedUnion('type', [
  z.object({ type: z.literal('click'), ...point,
    button: z.enum(['left', 'right', 'middle']).default('left'), count: z.number().int().min(1).max(3).default(1) }).strict(),
  z.object({ type: z.literal('move'), ...point }).strict(),
  z.object({ type: z.literal('drag'), ...point, toX: z.number().finite().nonnegative(),
    toY: z.number().finite().nonnegative(), durationMs: z.number().int().min(100).max(2000).default(500) }).strict(),
  z.object({ type: z.literal('scroll'), ...point,
    dx: z.number().finite().min(-2000).max(2000).default(0),
    dy: z.number().finite().min(-2000).max(2000).default(0) }).strict(),
  z.object({ type: z.literal('key'), keys: z.array(z.string().min(1).max(40)).min(1).max(8)
    .describe('Chord, e.g. ["CTRL", "a"], ["ALT", "Tab"], ["Return"]. XKB key names supported.') }).strict(),
  z.object({ type: z.literal('type'), text: z.string().max(4000)
    .describe('Literal text via keysyms. Newline and tab send Return and Tab. No shell expansion.') }).strict(),
  z.object({ type: z.literal('wait'), durationMs: z.number().int().min(0).max(2000).default(250) }).strict(),
]);

export const batchSchema = z.object({
  actions: z.array(action).min(1).max(30),
  screenshot: z.boolean().default(true),
}).strict().superRefine((value, ctx) => {
  const cost = value.actions.reduce((total, a) => total + (
    a.type === 'wait' || a.type === 'drag' ? a.durationMs :
    a.type === 'type' ? a.text.length * 3 : 150), 0);
  if (cost > 15000) ctx.addIssue({ code: 'custom', message: 'Batch exceeds the 15-second action budget. Split it into smaller batches.' });
});

export function resultContent(result) {
  const { image, ...data } = result;
  const content = [{ type: 'text', text: JSON.stringify(data) }];
  if (image) content.push({ type: 'image', data: image, mimeType: 'image/png' });
  return { content, isError: Boolean(result.error) };
}

export function registerTools(server, bridge) {
  let startup = null;
  const pending = () => ({ starting: true, message: 'Desktop session is starting. Call computer_status shortly. In portal mode, approve the Remote Desktop dialog. Use computer_stop to cancel.' });
  const register = (name, description, schema, method, convert = x => x, readOnly = false, timeout = 20000) => {
    server.registerTool(name, {
      description, inputSchema: schema,
      annotations: { readOnlyHint: readOnly, destructiveHint: !readOnly, openWorldHint: true },
    }, async (args, extra) => {
      if (startup?.state === 'pending') {
        return resultContent(method === 'status' ? pending() : { error: 'Desktop session is still starting. Call computer_status shortly; portal mode may require the system sharing dialog.' });
      }
      const cancel = () => { Promise.resolve(bridge.stop('Desktop operation cancelled by MCP client')).catch(() => {}); };
      if (extra.signal.aborted) return { isError: true, content: [{ type: 'text', text: 'Operation already cancelled' }] };
      extra.signal.addEventListener('abort', cancel, { once: true });
      try {
        const result = await bridge.call(method, convert(args), timeout);
        if (method === 'status' && startup) {
          result.lastStart = startup.result;
          if (startup.error) result.lastStartError = startup.error;
        }
        return resultContent(result);
      }
      catch (error) { return { isError: true, content: [{ type: 'text', text: error.message }] }; }
      finally { extra.signal.removeEventListener('abort', cancel); }
    });
  };
  register('computer_status', 'Inspect desktop readiness, backend, lock state, emergency stop, and current session. In persistent service mode also reports control owner, worker/service IDs, busy state, and whether explicitly stopped. Does not start capture or open dialogs.',
    z.object({}).strict(), 'status', undefined, true);
  server.registerTool('computer_start', {
    description: 'Start or reuse desktop control. The trusted GNOME service uses the primary monitor without a sharing picker while unlocked and survives agent disconnects. Portable portal mode requires user sharing approval. Returns starting=true during setup; check computer_status. Also resumes after computer_stop. Input affects the real focused application.',
    inputSchema: z.object({ clipboard: z.boolean().optional().describe('Clipboard access: native mode defaults enabled; portal mode defaults disabled. Explicit false keeps it disabled.') }).strict(),
    annotations: { readOnlyHint: false, destructiveHint: false, openWorldHint: true },
  }, async (args, extra) => {
    if (startup?.state === 'pending') return resultContent(pending());
    if (extra.signal.aborted) return resultContent({ error: 'Operation already cancelled' });
    const run = { state: 'pending' };
    startup = run;
    const finished = bridge.call('start', args, 210000).then(result => {
      run.state = 'ready'; run.result = result;
      return result;
    }, error => {
      run.state = 'failed'; run.error = error.message;
      return { error: error.message };
    });
    const cancel = () => { startup = null; Promise.resolve(bridge.stop('Desktop start cancelled by MCP client')).catch(() => {}); };
    extra.signal.addEventListener('abort', cancel, { once: true });
    let timer;
    try {
      return resultContent(await Promise.race([finished,
        new Promise(resolve => { timer = setTimeout(() => resolve(pending()), 500); })]));
    } finally {
      clearTimeout(timer);
      extra.signal.removeEventListener('abort', cancel);
    }
  });
  register('computer_screenshot', 'Capture the monitor as an image plus frameId and coordinate metadata. The GNOME service opens control automatically when needed. Coordinates for subsequent actions are pixels in the returned image. Crop coordinates use ORIGINAL capture pixels. Frames expire after 120 seconds.',
    z.object({ maxWidth: z.number().int().min(320).max(3840).default(1440),
      crop: z.object({ x: z.number().int().nonnegative(), y: z.number().int().nonnegative(),
        width: z.number().int().positive(), height: z.number().int().positive() }).strict().optional() }).strict(),
    'screenshot', ({ maxWidth, crop }) => ({ max_width: maxWidth, crop }), true);
  register('computer_input', 'Run a short ordered batch of click, move, drag, scroll, key chord, literal type, or wait actions, then return a screenshot by default. Pointer coordinates require frameId. Scroll units are logical pixels, positive dy scrolls down. All actions are validated before any executes; partial failures report completed/failedIndex. Keyboard targets the focused app. Re-observe after navigation or layout changes.',
    batchSchema, 'batch', undefined, false, 35000);
  register('computer_accessibility', 'Read a bounded native AT-SPI application/element tree with ephemeral refs and available semantic actions. Support varies by app. Does not read text/value interfaces or convert accessibility bounds to screenshot coordinates.',
    z.object({ app: z.string().max(200).optional(), maxNodes: z.number().int().min(1).max(500).default(250),
      maxDepth: z.number().int().min(0).max(12).default(8) }).strict(),
    'accessibility', ({ app, maxNodes, maxDepth }) => ({ app, max_nodes: maxNodes, max_depth: maxDepth }), true);
  register('computer_element_action', 'Perform an exact action name from an accessibility snapshot, focus an element, or set_text on an editable field. Requires active desktop control; references expire after 60 seconds or the next tree snapshot.',
    z.object({ ref: z.string().min(1), action: z.string().min(1).max(100), text: z.string().max(20000).optional() }).strict(),
    'element_action');
  register('computer_clipboard_set', 'Replace the desktop clipboard with UTF-8 text. Requires clipboard permission requested at start. Useful for long Unicode text followed by a Ctrl+V input action. Clipboard contents are not restored automatically.',
    z.object({ text: z.string().max(100000) }).strict(), 'clipboard_set');
  server.registerTool('computer_stop', {
    description: 'Immediately cancel running/queued operations and close desktop capture/input. In service mode globally suspends control until an explicit computer_start; the background service remains installed. Any agent can request a stop.',
    inputSchema: z.object({}).strict(),
    annotations: { readOnlyHint: false, destructiveHint: false, openWorldHint: false },
  }, async () => { startup = null; await bridge.stop(); return resultContent({ active: false, queuedActionsCancelled: true }); });
}
