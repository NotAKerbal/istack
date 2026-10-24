"""Mutter backend teardown when its capture stream breaks, without a real GNOME session."""
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'native'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mutter import Mutter
from portal import Gst
from test_portal import ErrorMessage, Sample, Buffer, open_session, lock_is_free, png_bytes


class Remote:
    def __init__(self): self.calls = []
    def Stop(self): self.calls.append('Stop')


class Bus:
    def __init__(self, cast): self.cast, self.requests = cast, []
    def get_object(self, dest, path):
        self.requests.append((dest, str(path)))
        return self.cast


class MutterCaptureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mutter = object.__new__(Mutter)
        self.remote, self.cast = Remote(), Remote()
        self.mutter.bus = Bus(self.cast)
        interface = patch('mutter.dbus.Interface', lambda obj, name: obj)
        interface.start()
        self.addCleanup(interface.stop)
    def tearDown(self):
        self.mutter.close()
        self.tmp.cleanup()

    def open(self, sample, error=None):
        pipeline = open_session(self.mutter, sample, error, lock_dir=self.tmp.name)
        self.mutter.session = '/org/gnome/Mutter/RemoteDesktop/Session/u1'
        self.mutter.session_iface = self.remote
        self.mutter.cast_session = '/org/gnome/Mutter/ScreenCast/Session/u2'
        return pipeline

    def test_broken_stream_stops_native_sessions_so_auto_start_can_recreate(self):
        pipeline = self.open(None, ErrorMessage())
        with self.assertRaisesRegex(RuntimeError, 'stream lost'):
            self.mutter.capture()
        # The worker's native auto-start and explicit start both key off active.
        self.assertFalse(self.mutter.active)
        self.assertEqual(self.remote.calls, ['Stop'])
        self.assertEqual(self.cast.calls, ['Stop'])
        self.assertEqual(self.mutter.bus.requests, [('org.gnome.Mutter.ScreenCast', '/org/gnome/Mutter/ScreenCast/Session/u2')])
        self.assertIsNone(self.mutter.session_iface)
        self.assertIsNone(self.mutter.cast_session)
        self.assertIsNone(self.mutter.session)
        self.assertIsNone(self.mutter.pipeline)
        self.assertEqual(pipeline.states, [Gst.State.NULL])
        self.assertTrue(lock_is_free(self.tmp.name))

    def test_normal_capture_leaves_native_session_running(self):
        self.open(Sample(Buffer(png_bytes())))
        self.assertEqual(self.mutter.capture().size, (4, 3))
        self.assertTrue(self.mutter.active)
        self.assertEqual(self.remote.calls, [])
        self.assertFalse(lock_is_free(self.tmp.name))


if __name__ == '__main__': unittest.main()
