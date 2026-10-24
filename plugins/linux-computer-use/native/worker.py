#!/usr/bin/python3
"""Private JSON-lines bridge; MCP lives in Node. stdout is protocol only."""
import json
import os
import signal
import sys
import threading
import traceback
from pathlib import Path

from controller import Controller, STOP_FILE


def desktop_environment():
    # MCP clients commonly sanitize environment variables. Recover only this UID's
    # standard local session socket, without borrowing another user's credentials.
    runtime = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
    if runtime.is_dir() and runtime.stat().st_uid == os.getuid():
        os.environ.setdefault('XDG_RUNTIME_DIR', str(runtime))
        if (runtime / 'bus').is_socket():
            os.environ.setdefault('DBUS_SESSION_BUS_ADDRESS', 'unix:path=' + str(runtime / 'bus'))
        sockets = sorted(p for p in runtime.glob('wayland-*') if p.is_socket())
        if len(sockets) == 1:
            os.environ.setdefault('WAYLAND_DISPLAY', sockets[0].name)
            os.environ.setdefault('XDG_SESSION_TYPE', 'wayland')


def doctor():
    import importlib.util
    import ctypes.util
    result = {'platform': sys.platform, 'sessionType': os.environ.get('XDG_SESSION_TYPE'),
              'desktop': os.environ.get('XDG_CURRENT_DESKTOP'),
              'waylandDisplay': os.environ.get('WAYLAND_DISPLAY'),
              'xDisplay': os.environ.get('DISPLAY'), 'stopFile': str(STOP_FILE),
              'emergencyStopped': STOP_FILE.exists(), 'python': sys.executable}
    result['dependencies'] = {name: importlib.util.find_spec(name) is not None for name in ['dbus', 'gi', 'PIL']}
    try:
        import gi
        for name, version in [('Gst', '1.0'), ('Atspi', '2.0')]:
            gi.require_version(name, version)
            result['dependencies'][name] = True
        from gi.repository import Gst
        Gst.init(None)
        for element in ['pipewiresrc', 'videoconvert', 'videoflip', 'videorate', 'pngenc', 'appsink']:
            result['dependencies'][element] = bool(Gst.ElementFactory.find(element))
        result['dependencies']['xkbcommon'] = bool(ctypes.util.find_library('xkbcommon'))
        import dbus
        bus = dbus.SessionBus()
        try:
            screensaver = dbus.Interface(bus.get_object('org.gnome.ScreenSaver', '/org/gnome/ScreenSaver'),
                                         'org.gnome.ScreenSaver')
            result['desktopLocked'] = bool(screensaver.GetActive(timeout=2))
        except dbus.DBusException:
            pass  # Optional on non-GNOME desktops.
        props = dbus.Interface(bus.get_object('org.freedesktop.portal.Desktop', '/org/freedesktop/portal/desktop'),
                               'org.freedesktop.DBus.Properties')
        result['portal'] = {name: int(props.Get('org.freedesktop.portal.' + name, 'version'))
                            for name in ['RemoteDesktop', 'ScreenCast']}
        result['ready'] = all(result['dependencies'].values()) and bool(result.get('waylandDisplay') or result.get('xDisplay'))
    except Exception as exc:
        result['ready'] = False
        result['error'] = str(exc)
    return result


def main():
    desktop_environment()
    if '--doctor' in sys.argv:
        print(json.dumps(doctor(), indent=2))
        return
    from portal import Portal
    from accessibility import Accessibility
    from gi.repository import GLib
    native_gnome = os.environ.get('LINUX_CUA_BACKEND') == 'mutter'
    if native_gnome:
        from mutter import Mutter
        backend = Mutter()
    else:
        backend = Portal()
    control = Controller(backend)
    a11y = Accessibility()
    loop = GLib.MainLoop()

    def dispatch(request):
        try:
            method, args = request['method'], request.get('params', {})
            if native_gnome and method not in ('status', 'start', 'stop') and not backend.active:
                if STOP_FILE.exists():
                    raise RuntimeError('Emergency stop active. Run npm run resume before using desktop control.')
                control.reset()
                a11y.refs.clear()
                backend.start(clipboard=True)
            if method == 'status':
                result = {**doctor(), 'active': backend.active, 'backend': backend.name,
                          'workerPid': os.getpid(), 'generation': control.generation}
            elif method == 'start':
                if STOP_FILE.exists():
                    raise RuntimeError('Emergency stop active. Run npm run resume before starting.')
                if native_gnome:
                    args.setdefault('clipboard', True)
                if backend.active and (not args.get('clipboard') or backend.clipboard_enabled):
                    result = {**backend.info, 'reused': True}
                else:
                    control.reset()
                    a11y.refs.clear()
                    result = backend.start(**args)
            elif method == 'screenshot':
                result = control.screenshot(**args)
            elif method == 'batch':
                result = control.batch(args['actions'])
                if args.get('screenshot', True) and not result.get('error'):
                    result.update(control.screenshot())
            elif method == 'accessibility':
                control.check()
                result = a11y.snapshot(**args)
            elif method == 'element_action':
                control.check()
                result = a11y.action(**args)
            elif method == 'clipboard_set':
                control.check()
                backend.clipboard_set(args['text'])
                result = {'written': True}
            elif method == 'stop':
                control.reset()
                a11y.refs.clear()
                backend.close()
                result = {'active': False}
            else:
                raise ValueError('Unknown native method')
            reply = {'id': request['id'], 'result': result}
        except Exception as exc:
            print(traceback.format_exc(), file=sys.stderr)
            reply = {'id': request['id'], 'error': str(exc)}
        print(json.dumps(reply, ensure_ascii=True), flush=True)
        return False

    def shutdown():
        control.release()
        backend.close()
        loop.quit()
        return False

    def reader():
        for line in sys.stdin:
            try:
                request = json.loads(line)
                GLib.idle_add(dispatch, request)
            except Exception as exc:
                print(str(exc), file=sys.stderr)
        GLib.idle_add(shutdown)
    threading.Thread(target=reader, daemon=True).start()
    def stop_watch():
        if STOP_FILE.exists() and backend.active:
            control.reset()
            a11y.refs.clear()
            backend.close()
        return True
    GLib.timeout_add(250, stop_watch)
    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGTERM, shutdown)
    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGINT, shutdown)
    try:
        loop.run()
    finally:
        control.release()
        backend.close()


if __name__ == '__main__':
    main()
