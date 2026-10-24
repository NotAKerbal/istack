"""GNOME/KDE Wayland via public XDG portals. No shell or privileged input."""
import os
import fcntl
import io
import threading
import time
import uuid

import dbus
from dbus.mainloop.glib import DBusGMainLoop
import gi
gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst
from PIL import Image

DEST = 'org.freedesktop.portal.Desktop'
PATH = '/org/freedesktop/portal/desktop'
RD = 'org.freedesktop.portal.RemoteDesktop'
SC = 'org.freedesktop.portal.ScreenCast'
CB = 'org.freedesktop.portal.Clipboard'


class Portal:
    name = 'wayland-portal'

    def __init__(self):
        DBusGMainLoop(set_as_default=True)
        Gst.init(None)
        self.bus = dbus.SessionBus()
        self.obj = self.bus.get_object(DEST, PATH)
        self.rd = dbus.Interface(self.obj, RD)
        self.sc = dbus.Interface(self.obj, SC)
        self.session = None
        self.pipeline = None
        self.fd = None
        self.matches = []
        self.clipboard_enabled = False
        self.clipboard_text = ''
        self.active = False
        self.lock_fd = None

    def request(self, iface, method, *args, options=None, timeout=90):
        token = 'linuxcua_' + uuid.uuid4().hex
        sender = self.bus.get_unique_name()[1:].replace('.', '_')
        path = f'/org/freedesktop/portal/desktop/request/{sender}/{token}'
        loop = GLib.MainLoop()
        result = []
        def response(code, values):
            result.append((int(code), values))
            loop.quit()
        match = self.bus.add_signal_receiver(response, signal_name='Response',
            dbus_interface='org.freedesktop.portal.Request', path=path, bus_name=DEST)
        opts = dict(options or {}, handle_token=dbus.String(token))
        timed_out = False
        def expire():
            nonlocal timed_out
            timed_out = True
            loop.quit()
            return False
        timer = GLib.timeout_add_seconds(timeout, expire)
        handle = None
        try:
            handle = getattr(iface, method)(*args, dbus.Dictionary(opts, signature='sv'))
            if str(handle) != path:
                raise RuntimeError('Portal returned an unexpected request path')
            if not result:
                loop.run()
            if not result:
                raise RuntimeError('Portal permission request timed out; retry Start and approve the desktop dialog')
            code, values = result[0]
            if code == 1:
                raise RuntimeError('Desktop permission was cancelled or denied (portal response %s)' % code)
            if code:
                raise RuntimeError(f'Portal {method} failed (response {code}). Check that the desktop is unlocked and remote access is allowed.')
            return values
        finally:
            if not result and handle:
                try:
                    dbus.Interface(self.bus.get_object(DEST, handle), 'org.freedesktop.portal.Request').Close()
                except Exception:
                    pass
            if not timed_out:
                GLib.source_remove(timer)
            match.remove()

    def start(self, clipboard=False):
        self.close()
        try:
            self.acquire_lock()
            result = self.request(self.rd, 'CreateSession', options={
                'session_handle_token': dbus.String('linuxcua_' + uuid.uuid4().hex)})
            self.session = dbus.ObjectPath(result['session_handle'])
            self.matches.append(self.bus.add_signal_receiver(self._closed,
                signal_name='Closed', dbus_interface='org.freedesktop.portal.Session',
                path=str(self.session), bus_name=DEST))
            self.request(self.rd, 'SelectDevices', self.session,
                         options={'types': dbus.UInt32(3)})
            props = dbus.Interface(self.obj, 'org.freedesktop.DBus.Properties')
            cursors = int(props.Get(SC, 'AvailableCursorModes'))
            self.request(self.sc, 'SelectSources', self.session, options={
                'types': dbus.UInt32(1), 'multiple': dbus.Boolean(False),
                'cursor_mode': dbus.UInt32(2 if cursors & 2 else 1)})
            if clipboard:
                self.cb = dbus.Interface(self.obj, CB)
                self.cb.RequestClipboard(self.session, dbus.Dictionary({}, signature='sv'))
                self.matches.append(self.bus.add_signal_receiver(self._transfer,
                    signal_name='SelectionTransfer', dbus_interface=CB, path=PATH, bus_name=DEST))
            result = self.request(self.rd, 'Start', self.session, '', timeout=180)
            if int(result.get('devices', 0)) & 3 != 3:
                raise RuntimeError('Pointer and keyboard permission were not both granted '
                    f'(devices={int(result.get("devices", 0))}). Enable Allow Remote Interaction in the sharing dialog and start again.')
            streams = result.get('streams', [])
            if len(streams) != 1:
                raise RuntimeError('Select exactly one monitor in the desktop sharing dialog')
            self.stream, info = streams[0]
            self.stream = int(self.stream)
            self.logical_size = tuple(map(int, info.get('size', (0, 0))))
            if not all(self.logical_size):
                raise RuntimeError('Portal did not provide stream logical size; refusing ambiguous input coordinates')
            self.clipboard_enabled = bool(result.get('clipboard_enabled', False))
            self.fd = self.sc.OpenPipeWireRemote(self.session, dbus.Dictionary({}, signature='sv')).take()
            return self.start_capture()
        except Exception:
            self.close()
            raise

    def acquire_lock(self):
        lock_dir = os.environ.get('XDG_RUNTIME_DIR', f'/tmp/linux-cua-{os.getuid()}')
        os.makedirs(lock_dir, mode=0o700, exist_ok=True)
        self.lock_fd = os.open(os.path.join(lock_dir, 'linux-computer-use.lock'),
                               os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another Linux computer-use session owns this desktop. Stop it first.')

    def start_capture(self):
        fd_option = f'fd={self.fd} ' if self.fd is not None else ''
        self.pipeline = Gst.parse_launch(
            f'pipewiresrc {fd_option}path={self.stream} do-timestamp=true keepalive-time=100 '
            '! videoconvert ! videoflip video-direction=auto '
            '! videorate max-rate=5 drop-only=true ! video/x-raw,format=RGB,framerate=5/1 '
            '! pngenc compression-level=1 '
            '! appsink name=screen emit-signals=false max-buffers=1 drop=true sync=false')
        self.sink = self.pipeline.get_by_name('screen')
        if self.pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError('Unable to start PipeWire screenshot stream')
        self.active = True
        image = self.capture()
        self.info = {'backend': self.name, 'logicalSize': self.logical_size,
                     'pixelSize': image.size, 'clipboard': self.clipboard_enabled,
                     'scope': 'selected monitor; keyboard goes to focused application'}
        return self.info

    def _closed(self, *args):
        self.active = False
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)

    def capture(self):
        if not self.active:
            raise RuntimeError('Desktop session is closed. Call computer_start again.')
        try:
            return self._capture_frame()
        except Exception:
            # A stalled, errored or undecodable stream does not heal itself. Close the whole
            # session so the next start (or native auto-start) builds a fresh one.
            self.close()
            raise

    def _capture_frame(self):
        # Discard an old queued frame. keepalive-time supplies frames on static desktops.
        self.sink.emit('try-pull-sample', 0)
        sample = self.sink.emit('try-pull-sample', 5 * Gst.SECOND)
        if sample is None:
            message = self.pipeline.get_bus().pop_filtered(Gst.MessageType.ERROR)
            detail = str(message.parse_error()) if message else 'No PipeWire frame within five seconds'
            raise RuntimeError(detail)
        buf = sample.get_buffer()
        ok, mapped = buf.map(Gst.MapFlags.READ)
        if not ok:
            raise RuntimeError('Unable to map screenshot buffer')
        try:
            # GStreamer handles raw stride/crop/orientation; PNG has no ambiguous row layout.
            return Image.open(io.BytesIO(bytes(mapped.data))).convert('RGB')
        finally:
            buf.unmap(mapped)

    def move(self, x, y):
        self.rd.NotifyPointerMotionAbsolute(self.session, {}, dbus.UInt32(self.stream), float(x), float(y))

    def pump(self):
        # Input batches run on GLib's thread. Service revocation and clipboard
        # transfers between events instead of starving them until a batch ends.
        context = GLib.MainContext.default()
        for _ in range(32):
            if not context.pending():
                break
            context.iteration(False)

    def button(self, button, down):
        self.rd.NotifyPointerButton(self.session, {}, dbus.Int32(button), dbus.UInt32(bool(down)))

    def key(self, sym, down):
        self.rd.NotifyKeyboardKeysym(self.session, {}, dbus.Int32(sym), dbus.UInt32(bool(down)))

    def scroll(self, dx, dy):
        self.rd.NotifyPointerAxis(self.session, {}, float(dx), float(dy))
        self.rd.NotifyPointerAxis(self.session, {'finish': dbus.Boolean(True)}, 0.0, 0.0)

    def clipboard_set(self, text):
        if not self.clipboard_enabled:
            raise RuntimeError('Clipboard not granted. Restart with clipboard=true.')
        self.clipboard_text = text
        self.cb.SetSelection(self.session, {'mime_types': dbus.Array(
            ['text/plain;charset=utf-8', 'text/plain'], signature='s')})

    def _transfer(self, session, mime, serial):
        if session != self.session:
            return
        fd = self.cb.SelectionWrite(self.session, serial).take()
        payload = self.clipboard_text.encode('utf-8')
        current_session = self.session
        def write():
            success = False
            try:
                # Never block the GLib/D-Bus event loop on a clipboard consumer.
                os.set_blocking(fd, False)
                import select
                offset = 0
                deadline = time.monotonic() + 5
                while offset < len(payload):
                    if time.monotonic() > deadline:
                        raise TimeoutError('Clipboard consumer timed out')
                    if select.select([], [fd], [], .1)[1]:
                        try:
                            offset += os.write(fd, payload[offset:])
                        except BlockingIOError:
                            pass
                success = True
            finally:
                os.close(fd)
                def done():
                    if self.active and self.session == current_session:
                        self.cb.SelectionWriteDone(current_session, serial, success)
                    return False
                GLib.idle_add(done)
        threading.Thread(target=write, daemon=True).start()

    def close(self):
        self.active = False
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None
        if self.session:
            try:
                dbus.Interface(self.bus.get_object(DEST, self.session),
                               'org.freedesktop.portal.Session').Close()
            except Exception:
                pass
            self.session = None
        for match in self.matches:
            match.remove()
        self.matches = []
        self.clipboard_enabled = False
        self.clipboard_text = ''
        if self.lock_fd is not None:
            os.close(self.lock_fd)
            self.lock_fd = None
