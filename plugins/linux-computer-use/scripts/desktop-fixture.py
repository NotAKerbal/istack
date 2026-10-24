#!/usr/bin/python3
"""Disposable native GTK fixture for an end-to-end portal input test."""
import json
import sys
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

GLib.set_prgname('linux-cua-test')
GLib.set_application_name('Linux Computer Use Test Fixture')

state = {'clicked': 0, 'text': ''}
window = Gtk.Window(title='Linux Computer Use Test')
window.set_default_size(520, 300)
window.set_position(Gtk.WindowPosition.CENTER)
window.connect('destroy', Gtk.main_quit)
box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
box.set_border_width(30)
window.add(box)
label = Gtk.Label(label='Linux Computer Use · desktop integration test')
box.pack_start(label, False, False, 0)
button = Gtk.Button(label='Click to test pointer input')
button.set_name('linux-cua-marker')
button.set_size_request(320, 76)
style = Gtk.CssProvider()
style.load_from_data(b'#linux-cua-marker { background-image: none; background-color: #e934bc; border: 0; border-radius: 0; color: white; box-shadow: none; }')
Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), style, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
box.pack_start(button, False, False, 0)
entry = Gtk.Entry()
entry.set_placeholder_text('The plugin will type here')
box.pack_start(entry, False, False, 0)
def emit(*args):
    state['text'] = entry.get_text()
    print(json.dumps(state), flush=True)
def click(*args):
    state['clicked'] += 1
    entry.grab_focus()
    emit()
button.connect('clicked', click)
entry.connect('changed', emit)
window.show_all()
emit()
Gtk.main()
