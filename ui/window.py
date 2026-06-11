import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk, GLib

from config import load_config, save_config
from launcher import get_available_emulators, launch_terminals

UI_FILE = None


class MultiTerminalWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("Multi-Terminal Launcher")
        self.set_default_size(420, 280)
        self.set_resizable(False)

        self.config = load_config()

        css = Gtk.CssProvider()
        css.load_from_data(b"""
            .card { background: #1e1e2e; border-radius: 12px; padding: 24px; }
            .title-label { font-size: 20px; font-weight: bold;
                           margin-bottom: 16px; }
            .row { margin-bottom: 12px; }
            .launch-btn { background: #89b4fa; color: #1e1e2e;
                          font-weight: bold; border-radius: 8px;
                          padding: 10px 32px; }
            .launch-btn:hover { background: #b4d0fb; }
            .status-label { margin-top: 8px; font-size: 13px;
                            color: #a6adc8; }
        """)

        style = self.get_style_context()
        style.add_provider_for_display(
            Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        vbox.set_margin_start(24)
        vbox.set_margin_end(24)
        vbox.set_margin_top(24)
        vbox.set_margin_bottom(24)
        self.set_child(vbox)

        title = Gtk.Label(label="Multi-Terminal Launcher")
        title.get_style_context().add_class("title-label")
        vbox.append(title)

        desc = Gtk.Label(
            label="Select how many terminals to open and click Launch.",
            wrap=True,
        )
        vbox.append(desc)

        count_box = Gtk.Box(spacing=12)
        count_box.get_style_context().add_class("row")
        count_label = Gtk.Label(label="Terminal count:")
        self.spin = Gtk.SpinButton()
        self.spin.set_adjustment(
            Gtk.Adjustment(value=self.config["terminal_count"],
                           lower=1, upper=20, step_increment=1)
        )
        self.spin.set_numeric(True)
        count_box.append(count_label)
        count_box.append(self.spin)
        vbox.append(count_box)

        emu_box = Gtk.Box(spacing=12)
        emu_box.get_style_context().add_class("row")
        emu_label = Gtk.Label(label="Terminal:")
        self.emulator_combo = Gtk.ComboBoxText()
        self.available = get_available_emulators()
        selected_idx = 0
        for i, (label, _binary) in enumerate(self.available):
            self.emulator_combo.append_text(label)
            if label == self.config["terminal_emulator"]:
                selected_idx = i
        if self.available:
            self.emulator_combo.set_active(selected_idx)
        else:
            self.emulator_combo.append_text("(none available)")
            self.emulator_combo.set_active(0)
        emu_box.append(emu_label)
        emu_box.append(self.emulator_combo)
        vbox.append(emu_box)

        self.launch_btn = Gtk.Button(label="Launch")
        self.launch_btn.get_style_context().add_class("launch-btn")
        self.launch_btn.connect("clicked", self.on_launch)
        vbox.append(self.launch_btn)

        self.status_label = Gtk.Label(label="")
        self.status_label.get_style_context().add_class("status-label")
        vbox.append(self.status_label)

        shortcut = Gtk.ShortcutController()
        trigger = Gtk.ShortcutTrigger.parse_string("<Control>l")
        action = Gtk.CallbackAction.new(self.on_ctrl_l)
        shortcut.add_shortcut(Gtk.Shortcut(trigger=trigger, action=action))
        self.add_controller(shortcut)

    def on_launch(self, _widget=None):
        count = int(self.spin.get_value())
        if not self.available:
            self.status_label.set_label("No terminal emulator found!")
            return
        idx = self.emulator_combo.get_active()
        if idx < 0:
            return
        emulator_name = self.available[idx][0]

        self.config["terminal_count"] = count
        self.config["terminal_emulator"] = emulator_name
        save_config(self.config)

        self.launch_btn.set_sensitive(False)
        self.status_label.set_label("Launching...")

        launched = launch_terminals(
            count, emulator_name,
            auto_tile=self.config.get("auto_tile", True),
            on_status=lambda msg: GLib.idle_add(self.status_label.set_label, msg),
        )

        if launched:
            self.status_label.set_label(f"Launched {launched} terminal{'s' if launched != 1 else ''}")
        self.launch_btn.set_sensitive(True)

    def on_ctrl_l(self, _widget, _param=None):
        self.on_launch()
        return True
