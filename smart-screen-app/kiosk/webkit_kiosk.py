#!/usr/bin/env python3
"""Smart Screen kiosk: WebKitGTK fullscreen window for the local web app."""
import urllib.request

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import GLib, Gtk, WebKit2

APP_URL = "http://127.0.0.1:8080"
STATUS_URL = APP_URL + "/api/status"


def backend_up():
    try:
        with urllib.request.urlopen(STATUS_URL, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


class Kiosk:
    def __init__(self):
        self.loaded = False

        self.win = Gtk.Window()
        self.win.set_title("Smart Screen")
        self.win.set_default_size(480, 800)
        self.win.fullscreen()
        self.win.connect("delete-event", Gtk.main_quit)

        settings = WebKit2.Settings()
        settings.set_enable_developer_extras(False)

        self.view = WebKit2.WebView()
        self.view.set_settings(settings)
        self.view.connect("context-menu", lambda *_a: True)

        self.win.add(self.view)
        self.win.show_all()
        self.win.get_window().set_cursor(None)

        GLib.timeout_add_seconds(2, self._pump)
        GLib.timeout_add_seconds(10, self._keepalive)

    def _pump(self):
        if backend_up() and not self.loaded:
            self.loaded = True
            self.view.load_uri(APP_URL)
        return True

    def _keepalive(self):
        if self.loaded and not backend_up():
            self.loaded = False
        return True


if __name__ == "__main__":
    Kiosk()
    Gtk.main()