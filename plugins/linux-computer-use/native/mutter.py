"""Trusted per-user GNOME backend. Private Mutter API, tested on GNOME 46.

Runs with the signed-in user's existing session-bus privileges. It does not
unlock the screen, elevate privileges, or open a remote desktop listener.
"""
import dbus
from gi.repository import GLib
from portal import Portal

RD = 'org.gnome.Mutter.RemoteDesktop'
SC = 'org.gnome.Mutter.ScreenCast'
RDS = RD + '.Session'
SCS = SC + '.Session'
STREAM = SC + '.Stream'


class ClipboardAdapter:
    """Translate the existing clipboard transfer implementation to Mutter."""
    def __init__(self, iface): self.iface = iface
    def SetSelection(self, session, options):
        return self.iface.SetSelection({'mime-types': options['mime_types']})
    def SelectionWrite(self, session, serial): return self.iface.SelectionWrite(serial)
    def SelectionWriteDone(self, session, serial, success):
        return self.iface.SelectionWriteDone(serial, success)


class Mutter(Portal):
    name = 'gnome-native'

    def __init__(self):
        self.cast_session = None
        self.session_iface = None
        super().__init__()

    def start(self, clipboard=False):
        self.close()
        try:
            self.acquire_lock()
            root = self.bus.get_object(RD, '/org/gnome/Mutter/RemoteDesktop')
            self.session = dbus.ObjectPath(dbus.Interface(root, RD).CreateSession())
            obj = self.bus.get_object(RD, self.session)
            self.session_iface = dbus.Interface(obj, RDS)
            session_id = dbus.Interface(obj, 'org.freedesktop.DBus.Properties').Get(RDS, 'SessionId')
            self.matches.append(self.bus.add_signal_receiver(self._closed,
                signal_name='Closed', dbus_interface=RDS, path=str(self.session), bus_name=RD))
            cast_root = self.bus.get_object(SC, '/org/gnome/Mutter/ScreenCast')
            self.cast_session = dbus.ObjectPath(dbus.Interface(cast_root, SC).CreateSession({
                'remote-desktop-session-id': dbus.String(session_id)}))
            cast = dbus.Interface(self.bus.get_object(SC, self.cast_session), SCS)
            # An empty connector selects GNOME's primary monitor.
            self.stream_path = str(cast.RecordMonitor('', {'cursor-mode': dbus.UInt32(1)}))
            stream_obj = self.bus.get_object(SC, self.stream_path)
            parameters = dbus.Interface(stream_obj, 'org.freedesktop.DBus.Properties').Get(STREAM, 'Parameters')
            self.logical_size = tuple(map(int, parameters.get('size', (0, 0))))
            if not all(self.logical_size):
                raise RuntimeError('GNOME did not provide the monitor logical size')
            nodes = []
            loop = GLib.MainLoop()
            def added(node):
                nodes.append(int(node))
                loop.quit()
            self.matches.append(self.bus.add_signal_receiver(added,
                signal_name='PipeWireStreamAdded', dbus_interface=STREAM,
                path=self.stream_path, bus_name=SC))
            expired = False
            def expire():
                nonlocal expired
                expired = True
                loop.quit()
                return False
            timer = GLib.timeout_add_seconds(5, expire)
            try:
                self.session_iface.Start()
                if not nodes:
                    loop.run()
                if not nodes:
                    raise RuntimeError('GNOME did not create a PipeWire monitor stream')
            finally:
                if not expired:
                    GLib.source_remove(timer)
            self.stream = nodes[0]
            if clipboard:
                self.cb = ClipboardAdapter(self.session_iface)
                self.matches.append(self.bus.add_signal_receiver(
                    lambda mime, serial: self._transfer(self.session, mime, serial),
                    signal_name='SelectionTransfer', dbus_interface=RDS,
                    path=str(self.session), bus_name=RD))
                self.session_iface.EnableClipboard(dbus.Dictionary({}, signature='sv'))
                self.clipboard_enabled = True
            result = self.start_capture()
            result['scope'] = 'primary monitor; native GNOME keyboard and pointer; signed-in user'
            result['permissionDialog'] = False
            return result
        except dbus.DBusException as exc:
            self.close()
            if 'inhibited' in str(exc).lower():
                raise RuntimeError('GNOME desktop control is inhibited. Unlock the signed-in desktop and try again.') from None
            raise
        except Exception:
            self.close()
            raise

    def move(self, x, y):
        self.session_iface.NotifyPointerMotionAbsolute(self.stream_path, float(x), float(y))

    def button(self, button, down):
        self.session_iface.NotifyPointerButton(dbus.Int32(button), dbus.Boolean(down))

    def key(self, sym, down):
        self.session_iface.NotifyKeyboardKeysym(dbus.UInt32(sym), dbus.Boolean(down))

    def scroll(self, dx, dy):
        self.session_iface.NotifyPointerAxis(float(dx), float(dy), dbus.UInt32(0))
        self.session_iface.NotifyPointerAxis(0.0, 0.0, dbus.UInt32(1))

    def close(self):
        self.active = False
        if self.session_iface:
            try:
                self.session_iface.Stop()
            except dbus.DBusException:
                pass
            self.session_iface = None
        if self.cast_session:
            try:
                dbus.Interface(self.bus.get_object(SC, self.cast_session), SCS).Stop()
            except dbus.DBusException:
                pass
            self.cast_session = None
        # Stop() owns the linked cast session. Do not call portal Session.Close.
        self.session = None
        super().close()
