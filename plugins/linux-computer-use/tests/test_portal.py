"""Portal request lifecycle tests without opening a real desktop dialog."""
import fcntl
import io
import os
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'native'))
from portal import Portal, GLib, Gst


class Match:
    removed = False
    def remove(self): self.removed = True


class Bus:
    def __init__(self):
        self.match = Match()
        self.closed = False
    def get_unique_name(self): return ':1.123'
    def add_signal_receiver(self, callback, **kwargs):
        self.callback = callback
        self.path = kwargs['path']
        return self.match
    def get_object(self, dest, path): return self
    def Close(self): self.closed = True


class PortalRequestTest(unittest.TestCase):
    def setUp(self):
        self.portal = object.__new__(Portal)
        self.portal.bus = Bus()

    def iface(self, response=0, immediate=False, mismatch=False, no_response=False):
        bus = self.portal.bus
        class Interface:
            def CreateSession(self, options):
                # Registration must already exist when the method is invoked.
                assert callable(bus.callback)
                def emit():
                    bus.callback(response, {'session_handle': '/session/test'})
                    return False
                if not no_response:
                    if immediate: emit()
                    else: GLib.idle_add(emit)
                return '/wrong/path' if mismatch else bus.path
        return Interface()

    def test_subscribe_before_call_and_wait_for_asynchronous_response(self):
        result = self.portal.request(self.iface(), 'CreateSession', timeout=1)
        self.assertEqual(result['session_handle'], '/session/test')
        self.assertTrue(self.portal.bus.match.removed)

    def test_immediate_response_is_not_lost(self):
        result = self.portal.request(self.iface(immediate=True), 'CreateSession', timeout=1)
        self.assertIn('session_handle', result)

    def test_denied_request_fails_and_removes_subscription(self):
        with self.assertRaisesRegex(RuntimeError, 'cancelled or denied'):
            self.portal.request(self.iface(response=1), 'CreateSession', timeout=1)
        self.assertTrue(self.portal.bus.match.removed)

    def test_timeout_closes_request_instead_of_leaving_permission_dialog(self):
        with patch('portal.dbus.Interface', lambda obj, name: obj):
            with self.assertRaisesRegex(RuntimeError, 'timed out'):
                self.portal.request(self.iface(no_response=True), 'CreateSession', timeout=0)
        self.assertTrue(self.portal.bus.closed)
        self.assertTrue(self.portal.bus.match.removed)

    def test_portal_failure_is_not_misreported_as_user_denial(self):
        with self.assertRaisesRegex(RuntimeError, 'Portal CreateSession failed'):
            self.portal.request(self.iface(response=2), 'CreateSession', timeout=1)

    def test_unexpected_handle_is_cancelled(self):
        with patch('portal.dbus.Interface', lambda obj, name: obj):
            with self.assertRaisesRegex(RuntimeError, 'unexpected request path'):
                self.portal.request(self.iface(mismatch=True, no_response=True), 'CreateSession', timeout=1)
        self.assertTrue(self.portal.bus.closed)


def png_bytes():
    out = io.BytesIO()
    Image.new('RGB', (4, 3), (10, 20, 30)).save(out, 'PNG')
    return out.getvalue()


class Mapped:
    def __init__(self, data): self.data = data


class Buffer:
    def __init__(self, data, mappable=True):
        self.data, self.mappable, self.unmapped = data, mappable, False
    def map(self, flags): return (True, Mapped(self.data)) if self.mappable else (False, None)
    def unmap(self, mapped): self.unmapped = True


class Sample:
    def __init__(self, buffer): self.buffer = buffer
    def get_buffer(self): return self.buffer


class Sink:
    def __init__(self, sample): self.sample = sample
    def emit(self, signal, timeout): return self.sample if timeout else None


class ErrorMessage:
    def parse_error(self): return ('gst-resource-error', 'pipewiresrc: stream lost')


class Pipeline:
    def __init__(self, error=None):
        self.states, self.error = [], error
    def set_state(self, state): self.states.append(state)
    def get_bus(self): return self
    def pop_filtered(self, kind): return self.error


def open_session(backend, sample, error=None, lock_dir=None):
    """Put a backend in the state start_capture leaves it in, holding the real desktop lock."""
    backend.pipeline = Pipeline(error)
    backend.sink = Sink(sample)
    backend.fd = None
    backend.session = None
    backend.matches = []
    backend.clipboard_enabled = False
    backend.clipboard_text = ''
    backend.lock_fd = None
    with patch.dict(os.environ, {'XDG_RUNTIME_DIR': lock_dir}):
        backend.acquire_lock()
    backend.active = True
    return backend.pipeline


def lock_is_free(lock_dir):
    fd = os.open(os.path.join(lock_dir, 'linux-computer-use.lock'), os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except BlockingIOError:
        return False
    finally:
        os.close(fd)


class PortalCaptureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.portal = object.__new__(Portal)
    def tearDown(self):
        self.portal.close()
        self.tmp.cleanup()

    def assert_invalidated(self, pipeline):
        self.assertFalse(self.portal.active)
        self.assertIsNone(self.portal.pipeline)
        self.assertEqual(pipeline.states, [Gst.State.NULL])
        self.assertTrue(lock_is_free(self.tmp.name), 'broken session must release the desktop lock')
        with self.assertRaisesRegex(RuntimeError, 'session is closed'):
            self.portal.capture()

    def test_normal_capture_keeps_session_active(self):
        buffer = Buffer(png_bytes())
        pipeline = open_session(self.portal, Sample(buffer), lock_dir=self.tmp.name)
        image = self.portal.capture()
        self.assertEqual((image.size, image.mode), ((4, 3), 'RGB'))
        self.assertTrue(buffer.unmapped)
        self.assertTrue(self.portal.active)
        self.assertEqual(pipeline.states, [])
        self.assertFalse(lock_is_free(self.tmp.name))

    def test_missing_sample_invalidates_session(self):
        pipeline = open_session(self.portal, None, lock_dir=self.tmp.name)
        with self.assertRaisesRegex(RuntimeError, 'No PipeWire frame'):
            self.portal.capture()
        self.assert_invalidated(pipeline)

    def test_gstreamer_error_invalidates_session(self):
        pipeline = open_session(self.portal, None, ErrorMessage(), lock_dir=self.tmp.name)
        with self.assertRaisesRegex(RuntimeError, 'stream lost'):
            self.portal.capture()
        self.assert_invalidated(pipeline)

    def test_unmappable_buffer_invalidates_session(self):
        pipeline = open_session(self.portal, Sample(Buffer(b'', mappable=False)), lock_dir=self.tmp.name)
        with self.assertRaisesRegex(RuntimeError, 'map screenshot'):
            self.portal.capture()
        self.assert_invalidated(pipeline)

    def test_undecodable_frame_invalidates_session_and_unmaps(self):
        buffer = Buffer(b'not a png')
        pipeline = open_session(self.portal, Sample(buffer), lock_dir=self.tmp.name)
        with self.assertRaises(OSError):
            self.portal.capture()
        self.assertTrue(buffer.unmapped)
        self.assert_invalidated(pipeline)


if __name__ == '__main__': unittest.main()
