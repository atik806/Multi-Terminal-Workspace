#!/usr/bin/env python3
import sys

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ui.window import MultiTerminalWindow


class MultiTerminalApp(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id="com.multi-terminal.launcher",
            flags=0,
        )

    def do_activate(self):
        win = MultiTerminalWindow(self)
        win.present()


def main():
    app = MultiTerminalApp()
    exit_code = app.run(sys.argv)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
