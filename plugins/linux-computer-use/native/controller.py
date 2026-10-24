"""Desktop operation semantics, independent of the transport and compositor."""
import base64
import ctypes
import ctypes.util
import io
import math
import os
from pathlib import Path
import time
import uuid

STOP_FILE = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'linux-computer-use/STOP'
BUTTONS = {'left': 272, 'right': 273, 'middle': 274}
ALIASES = {'ctrl': 'Control_L', 'control': 'Control_L', 'alt': 'Alt_L',
           'shift': 'Shift_L', 'super': 'Super_L', 'meta': 'Super_L',
           'enter': 'Return', 'return': 'Return', 'escape': 'Escape',
           'esc': 'Escape', 'backspace': 'BackSpace', 'tab': 'Tab',
           'space': 'space', 'delete': 'Delete', 'up': 'Up', 'down': 'Down',
           'left': 'Left', 'right': 'Right', 'home': 'Home', 'end': 'End',
           'pageup': 'Page_Up', 'pagedown': 'Page_Down'}


def keysym(name):
    name = ALIASES.get(name.lower(), name)
    if len(name) == 1:
        code = ord(name)
        return code if code < 256 else 0x01000000 | code
    lib = ctypes.CDLL(ctypes.util.find_library('xkbcommon'))
    lib.xkb_keysym_from_name.argtypes = [ctypes.c_char_p, ctypes.c_int]
    lib.xkb_keysym_from_name.restype = ctypes.c_uint32
    code = lib.xkb_keysym_from_name(name.encode(), 1)
    if not code:
        raise ValueError(f'Unknown key: {name}')
    return code


class Controller:
    def __init__(self, backend, stop_file=STOP_FILE):
        self.backend = backend
        self.stop_file = stop_file
        self.frames = {}
        self.held_keys = set()
        self.held_buttons = set()
        self.generation = uuid.uuid4().hex
        self.last_pixel_size = None

    def check(self):
        pump = getattr(self.backend, 'pump', None)
        if pump:
            pump()
        if self.stop_file.exists():
            self.release()
            self.backend.close()
            self.frames.clear()
            raise RuntimeError('Emergency stop is active. Run npm run resume to allow a new session.')
        if not self.backend.active:
            raise RuntimeError('No active desktop session. Call computer_start first.')

    def reset(self):
        self.release()
        self.frames.clear()
        self.generation = uuid.uuid4().hex
        self.last_pixel_size = None

    def screenshot(self, max_width=1440, crop=None):
        self.check()
        image = self.backend.capture()
        if self.last_pixel_size is not None and image.size != self.last_pixel_size:
            self.frames.clear()
            self.generation = uuid.uuid4().hex
            # Portal logical size may also have changed; restart to refresh its metadata.
            self.backend.close()
            raise RuntimeError('Monitor geometry changed. Restart the desktop session before using coordinates.')
        self.last_pixel_size = image.size
        original = image.size
        box = {'x': 0, 'y': 0, 'width': image.width, 'height': image.height}
        if crop:
            box = crop
            if (box['x'] < 0 or box['y'] < 0 or box['width'] <= 0 or box['height'] <= 0
                or box['x'] + box['width'] > image.width or box['y'] + box['height'] > image.height):
                raise ValueError('Crop is outside the original screenshot pixel bounds')
            image = image.crop((box['x'], box['y'], box['x'] + box['width'], box['y'] + box['height']))
        if image.width > max_width:
            from PIL import Image
            image = image.resize((max_width, max(1, round(image.height * max_width / image.width))), Image.Resampling.LANCZOS)
        frame_id = uuid.uuid4().hex
        meta = {'frameId': frame_id, 'generation': self.generation,
                'timestamp': time.time(), 'width': image.width, 'height': image.height,
                'pixelSize': original, 'logicalSize': self.backend.logical_size,
                'crop': box, 'streamId': self.backend.stream,
                'coordinateSpace': 'pixels in this returned image; stream-relative; no monitor-origin offset'}
        self.frames[frame_id] = meta
        while len(self.frames) > 8:
            del self.frames[next(iter(self.frames))]
        output = io.BytesIO()
        image.save(output, format='PNG')
        return {'metadata': meta, 'image': base64.b64encode(output.getvalue()).decode()}

    def point(self, frame_id, x, y):
        self.check()
        frame = self.frames.get(frame_id)
        if not frame or frame['generation'] != self.generation:
            raise ValueError('Unknown or expired frameId. Take a new screenshot.')
        if time.time() - frame['timestamp'] > 120:
            raise ValueError('Screenshot is over 120 seconds old. Take a new screenshot.')
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (x, y)):
            raise ValueError('Coordinates must be finite numbers')
        if not (0 <= x < frame['width'] and 0 <= y < frame['height']):
            raise ValueError('Coordinates are outside the returned screenshot')
        crop = frame['crop']
        px = crop['x'] + x * crop['width'] / frame['width']
        py = crop['y'] + y * crop['height'] / frame['height']
        return px * frame['logicalSize'][0] / frame['pixelSize'][0], py * frame['logicalSize'][1] / frame['pixelSize'][1]

    def key(self, sym, down):
        if down:
            self.held_keys.add(sym)
        self.backend.key(sym, down)
        if not down:
            self.held_keys.discard(sym)

    def button(self, button, down):
        if down:
            self.held_buttons.add(button)
        self.backend.button(button, down)
        if not down:
            self.held_buttons.discard(button)

    def release(self):
        for sym in list(self.held_keys):
            try:
                self.backend.key(sym, False)
            except Exception:
                pass
        for button in list(self.held_buttons):
            try:
                self.backend.button(button, False)
            except Exception:
                pass
        self.held_keys.clear()
        self.held_buttons.clear()

    def pause(self, seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.check()
            time.sleep(min(.025, max(0, deadline - time.monotonic())))

    def validate_action(self, action):
        kind = action['type']
        if kind in ('move', 'click', 'scroll', 'drag'):
            self.point(action['frameId'], action['x'], action['y'])
            if kind == 'drag':
                self.point(action['frameId'], action['toX'], action['toY'])
        if kind == 'key':
            for key in action['keys']:
                keysym(key)

    def action(self, action):
        self.check()
        kind = action['type']
        try:
            if kind in ('move', 'click', 'scroll', 'drag'):
                x, y = self.point(action['frameId'], action['x'], action['y'])
                self.backend.move(x, y)
            if kind == 'click':
                button = BUTTONS[action.get('button', 'left')]
                for _ in range(action.get('count', 1)):
                    self.button(button, True)
                    self.pause(.035)
                    self.button(button, False)
                    self.pause(.07)
            elif kind == 'drag':
                tx, ty = self.point(action['frameId'], action['toX'], action['toY'])
                self.button(BUTTONS['left'], True)
                steps = 30
                for i in range(1, steps + 1):
                    self.check()
                    self.backend.move(x + (tx - x) * i / steps, y + (ty - y) * i / steps)
                    self.pause(action.get('durationMs', 500) / 1000 / steps)
                self.button(BUTTONS['left'], False)
            elif kind == 'scroll':
                self.backend.scroll(action.get('dx', 0), action.get('dy', 0))
            elif kind == 'key':
                syms = [keysym(k) for k in action['keys']]
                for sym in syms:
                    self.key(sym, True)
                self.pause(.04)
                for sym in reversed(syms):
                    self.key(sym, False)
            elif kind == 'type':
                for char in action['text']:
                    self.check()
                    sym = keysym({'\n': 'Return', '\t': 'Tab'}.get(char, char))
                    self.key(sym, True)
                    self.key(sym, False)
                    self.pause(.002)
            elif kind == 'wait':
                self.pause(action.get('durationMs', 250) / 1000)
            elif kind != 'move':
                raise ValueError(f'Unsupported action: {kind}')
        finally:
            self.release()

    def batch(self, actions):
        self.check()
        for action in actions:
            self.validate_action(action)
        completed = 0
        for action in actions:
            try:
                self.action(action)
                completed += 1
            except Exception as exc:
                return {'completed': completed, 'failedIndex': completed, 'error': str(exc)}
        return {'completed': completed}
