import sys
from pathlib import Path
import tempfile
import unittest
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'native'))
from controller import Controller, keysym


class Backend:
    active = True
    logical_size = (1000, 500)
    stream = 7
    def __init__(self):
        self.events = []
        self.size = (2000, 1000)
    def capture(self): return Image.new('RGB', self.size)
    def move(self, x, y): self.events.append(('move', x, y))
    def key(self, key, down): self.events.append(('key', key, down))
    def button(self, button, down): self.events.append(('button', button, down))
    def scroll(self, dx, dy): self.events.append(('scroll', dx, dy))
    def close(self): self.active = False


class ControllerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.backend = Backend()
        self.control = Controller(self.backend, Path(self.tmp.name) / 'STOP')
    def tearDown(self): self.tmp.cleanup()
    def frame(self, **kwargs): return self.control.screenshot(**kwargs)['metadata']['frameId']

    def test_scaled_image_coordinates(self):
        frame = self.frame(max_width=1000)
        self.assertEqual(self.control.point(frame, 500, 250), (500, 250))

    def test_crop_then_scale_then_logical_coordinates(self):
        frame = self.frame(max_width=400, crop={'x': 400, 'y': 200, 'width': 800, 'height': 400})
        self.assertEqual(self.control.point(frame, 200, 100), (400, 200))
        with self.assertRaises(ValueError): self.control.point(frame, 400, 0)
        with self.assertRaises(ValueError): self.control.point(frame, float('nan'), 0)

    def test_frames_expire_on_reset_and_time(self):
        frame = self.frame()
        self.control.frames[frame]['timestamp'] -= 121
        with self.assertRaisesRegex(ValueError, '120 seconds'): self.control.point(frame, 1, 1)
        self.control.reset()
        with self.assertRaisesRegex(ValueError, 'expired'): self.control.point(frame, 1, 1)

    def test_geometry_change_closes_session(self):
        self.frame()
        self.backend.size = (1000, 1000)
        with self.assertRaisesRegex(RuntimeError, 'geometry changed'): self.frame()
        self.assertFalse(self.backend.active)
        self.assertFalse(self.control.frames)

    def test_invalid_later_action_prevents_all_input(self):
        frame = self.frame()
        with self.assertRaises(ValueError):
            self.control.batch([{'type': 'click', 'frameId': frame, 'x': 1, 'y': 1},
                                {'type': 'key', 'keys': ['NotARealKeyName']}])
        self.assertEqual(self.backend.events, [])

    def test_drag_failure_releases_button_and_reports_partial_progress(self):
        frame = self.frame()
        original = self.backend.move
        def fail_on_drag(x, y):
            if self.control.held_buttons: raise RuntimeError('injected motion failure')
            original(x, y)
        self.backend.move = fail_on_drag
        result = self.control.batch([{'type': 'wait', 'durationMs': 0},
            {'type': 'drag', 'frameId': frame, 'x': 1, 'y': 1, 'toX': 20, 'toY': 20}])
        self.assertEqual(result['completed'], 1)
        self.assertEqual(result['failedIndex'], 1)
        self.assertEqual(self.backend.events[-1], ('button', 272, False))
        self.assertFalse(self.control.held_buttons)

    def test_key_failure_releases_pressed_modifier(self):
        original = self.backend.key
        def fail(key, down):
            if key == keysym('a') and down: raise RuntimeError('injected key failure')
            original(key, down)
        self.backend.key = fail
        with self.assertRaises(RuntimeError): self.control.action({'type': 'key', 'keys': ['CTRL', 'a']})
        self.assertIn(('key', keysym('CTRL'), False), self.backend.events)
        self.assertFalse(self.control.held_keys)

    def test_emergency_stop_closes_and_rejects(self):
        frame = self.frame()
        self.control.stop_file.touch()
        with self.assertRaisesRegex(RuntimeError, 'Emergency stop'):
            self.control.point(frame, 0, 0)
        self.assertFalse(self.backend.active)

    def test_pending_portal_revocation_prevents_next_keyboard_event(self):
        def revoke():
            self.backend.active = False
        self.backend.pump = revoke
        with self.assertRaisesRegex(RuntimeError, 'No active desktop session'):
            self.control.action({'type': 'key', 'keys': ['a']})
        self.assertEqual(self.backend.events, [])

    def test_unicode_and_hotkey_aliases(self):
        self.assertEqual(keysym('CTRL'), keysym('Control_L'))
        self.assertEqual(keysym('é'), 233)
        self.assertEqual(keysym('😊'), 0x0101f60a)


if __name__ == '__main__': unittest.main()
