import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gdk, GLib, Gio, Adw

from config import load_config, save_config
from launcher import get_available_emulators, launch_terminals
from ui.preview import GridPreview
from ui.terminal_manager import TerminalManager, TerminalInfo


class MultiTerminalWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("Multi-Terminal Launcher")
        self.set_default_size(560, 640)

        self.config = load_config()
        self.available = get_available_emulators()
        if not self.available:
            self.available = [("System Default", "")]

        self.manager = TerminalManager()
        self.manager.on_change(self._on_terminals_changed)

        self._apply_theme()
        self._build_ui()

        GLib.timeout_add(2000, self._poll_statuses)

    def _apply_theme(self):
        scheme = self.config.get("theme", "system")
        style_mgr = Adw.StyleManager.get_default()
        mapping = {
            "system": Adw.ColorScheme.DEFAULT,
            "light": Adw.ColorScheme.FORCE_LIGHT,
            "dark": Adw.ColorScheme.FORCE_DARK,
        }
        style_mgr.set_color_scheme(mapping.get(scheme, Adw.ColorScheme.DEFAULT))

    def _build_ui(self):
        toast_overlay = Adw.ToastOverlay()
        self.set_content(toast_overlay)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        toast_overlay.set_child(main_box)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.set_vexpand(True)
        main_box.append(toolbar_view)

        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        theme_btn = Gtk.ToggleButton()
        scheme = self.config.get("theme", "system")
        theme_btn.set_active(scheme == "dark")
        theme_btn.set_tooltip_text("Toggle dark mode")
        self._update_theme_icon(theme_btn)
        theme_btn.connect("toggled", self._on_theme_toggled)
        header.pack_end(theme_btn)

        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("open-menu-symbolic")
        menu_btn.set_tooltip_text("Menu")

        menu_model = Gio.Menu()
        menu_model.append("About", "app.about")
        menu_btn.set_menu_model(menu_model)
        header.pack_end(menu_btn)

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.get_application().add_action(about_action)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        toolbar_view.set_content(content_box)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        content_box.append(scroll)

        page = Adw.PreferencesPage()
        scroll.set_child(page)

        config_group = Adw.PreferencesGroup()
        config_group.set_title("Configuration")
        config_group.set_description("Choose terminal count and emulator")
        page.add(config_group)

        self.count_row = Adw.SpinRow(
            title="Terminal count",
            subtitle="Number of terminals to open",
            adjustment=Gtk.Adjustment(
                value=self.config.get("terminal_count", 4),
                lower=1,
                upper=20,
                step_increment=1,
            ),
        )
        self.count_row.connect("notify::value", self._on_config_changed)
        config_group.add(self.count_row)

        model = Gtk.StringList.new([label for label, _ in self.available])
        self.emulator_row = Adw.ComboRow(
            title="Terminal emulator",
            subtitle="Select which terminal application to use",
            model=model,
        )
        target = self.config.get("terminal_emulator", "gnome-terminal")
        for i, (label, _) in enumerate(self.available):
            if label == target:
                self.emulator_row.set_selected(i)
                break
        self.emulator_row.connect("notify::selected", self._on_config_changed)
        config_group.add(self.emulator_row)

        preview_group = Adw.PreferencesGroup()
        preview_group.set_title("Grid Preview")
        preview_group.set_description("Shows how terminals will be arranged")
        page.add(preview_group)

        self.preview = GridPreview()
        preview_group.add(self.preview)

        advanced_group = Adw.PreferencesGroup()
        advanced_group.set_title("Advanced")
        page.add(advanced_group)

        self.tile_switch = Adw.SwitchRow(
            title="Auto-tile",
            subtitle="Automatically arrange terminals in a grid across the screen",
            active=self.config.get("auto_tile", True),
        )
        self.tile_switch.connect("notify::active", self._on_config_changed)
        advanced_group.add(self.tile_switch)

        self.tmux_switch = Adw.SwitchRow(
            title="Use tmux",
            subtitle="Launch terminals in a tmux session instead of separate windows (recommended)",
            active=self.config.get("use_tmux", True),
        )
        self.tmux_switch.connect("notify::active", self._on_config_changed)
        advanced_group.add(self.tmux_switch)

        self._build_terminal_section(content_box)

        action_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        action_bar.set_margin_top(12)
        action_bar.set_margin_bottom(12)
        action_bar.set_margin_start(12)
        action_bar.set_margin_end(12)

        self.status_label = Gtk.Label(label="")
        self.status_label.set_hexpand(True)
        self.status_label.set_halign(Gtk.Align.START)
        self.status_label.add_css_class("dim-label")
        action_bar.append(self.status_label)

        launch_btn = Gtk.Button(label="Launch")
        launch_btn.add_css_class("suggested-action")
        launch_btn.connect("clicked", self._on_launch)
        launch_btn.set_valign(Gtk.Align.CENTER)
        action_bar.append(launch_btn)

        main_box.append(action_bar)

        self._update_preview()
        self._toast_overlay = toast_overlay

    def _build_terminal_section(self, parent):
        self.terminal_revealer = Gtk.Revealer()
        self.terminal_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        parent.append(self.terminal_revealer)

        term_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        term_box.set_margin_start(12)
        term_box.set_margin_end(12)
        term_box.set_margin_bottom(4)
        self.terminal_revealer.set_child(term_box)

        header_box = Gtk.Box(spacing=8)
        header_box.set_margin_top(4)
        header_box.set_margin_bottom(4)

        self.list_count_label = Gtk.Label(label="Running (0)")
        self.list_count_label.add_css_class("heading")
        header_box.append(self.list_count_label)

        spacer = Gtk.Label()
        spacer.set_hexpand(True)
        header_box.append(spacer)

        self.close_all_btn = Gtk.Button(label="Close All")
        self.close_all_btn.add_css_class("destructive-action")
        self.close_all_btn.add_css_class("circular")
        self.close_all_btn.connect("clicked", lambda _: self.manager.close_all())
        self.close_all_btn.set_sensitive(False)
        header_box.append(self.close_all_btn)
        term_box.append(header_box)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_max_content_height(180)
        scrolled.set_propagate_natural_height(True)

        self.terminal_list = Gtk.ListBox()
        self.terminal_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.terminal_list.add_css_class("boxed-list")
        self.terminal_list.connect("row-activated", self._on_row_activated)
        scrolled.set_child(self.terminal_list)
        term_box.append(scrolled)

        self._css_dot = Gtk.CssProvider()
        self._css_dot.load_from_data(b"""
            .status-dot { font-size: 10px; margin-right: 6px; }
            .status-running { color: #a6e3a1; }
            .status-stopped { color: #f38ba8; }
            .term-pid { font-size: 12px; color: #6c7086;
                         font-family: monospace; }
            .row-close-btn { background: transparent; color: #f38ba8;
                             border: none; border-radius: 4px;
                             padding: 4px 10px; font-weight: bold;
                             font-size: 14px; }
            .row-close-btn:hover { background: alpha(currentColor, 0.1); }
            .popover-menu button { padding: 8px 20px; border: none;
                                   background: transparent;
                                    font-size: 14px;
                                   border-radius: 0; }
            .popover-menu button:hover { background: alpha(currentColor, 0.1); }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            self._css_dot,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _update_theme_icon(self, btn):
        style_mgr = Adw.StyleManager.get_default()
        btn.set_icon_name(
            "weather-clear-night-symbolic"
            if style_mgr.get_dark()
            else "weather-clear-symbolic"
        )

    def _on_theme_toggled(self, btn):
        style_mgr = Adw.StyleManager.get_default()
        if btn.get_active():
            style_mgr.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
            self.config["theme"] = "dark"
        else:
            style_mgr.set_color_scheme(Adw.ColorScheme.DEFAULT)
            self.config["theme"] = "system"
        self._update_theme_icon(btn)
        self.preview.queue_draw()
        save_config(self.config)

    def _on_about(self, *_unused):
        about = Adw.AboutWindow(transient_for=self)
        about.set_application_name("Multi-Terminal Launcher")
        about.set_version("1.0.0")
        about.set_developer_name("Multi-Terminal Contributors")
        about.set_license_type(Gtk.License.GPL_3_0)
        about.set_website("https://github.com/multi-terminal")
        about.set_issue_url("https://github.com/multi-terminal/issues")
        about.present()

    def _on_config_changed(self, *_unused):
        self._update_preview()

    def _update_preview(self):
        count = int(self.count_row.get_value())
        auto_tile = self.tile_switch.get_active()
        use_tmux = self.tmux_switch.get_active()
        self.preview.set_count(count)
        self.preview.set_auto_tile(auto_tile)
        self.preview.set_use_tmux(use_tmux)

    def _on_launch(self, _btn=None):
        count = int(self.count_row.get_value())
        idx = self.emulator_row.get_selected()
        if idx < 0:
            idx = 0
        emulator_name = self.available[idx][0]
        auto_tile = self.tile_switch.get_active()
        use_tmux = self.tmux_switch.get_active()

        self.config["terminal_count"] = count
        self.config["terminal_emulator"] = emulator_name
        self.config["auto_tile"] = auto_tile
        self.config["use_tmux"] = use_tmux
        save_config(self.config)

        resolved_tmux = use_tmux and count > 1

        self.status_label.set_label("Launching...")
        result = launch_terminals(
            count,
            emulator_name,
            auto_tile=auto_tile,
            use_tmux=resolved_tmux,
            on_status=lambda msg: GLib.idle_add(self._show_status, msg),
        )

        if result.success:
            self._register_terminals(result)
            if resolved_tmux and result.count > 1:
                msg = f"Opened {result.count} terminals in tmux grid"
            else:
                msg = f"Launched {result.count} terminal{'s' if result.count != 1 else ''}"
            self._show_toast(msg)
        else:
            self._show_toast(result.error or "No terminals launched — check your terminal emulator")

        self.status_label.set_label("")

    def _register_terminals(self, result):
        if result.mode == "tmux":
            if result.panes:
                infos = []
                for pane in result.panes:
                    info = TerminalInfo(
                        pid=pane["pid"],
                        emulator=result.emulator,
                        mode="tmux",
                        session_name=result.session_name,
                        pane_id=pane["pane_id"],
                        index=pane["index"],
                    )
                    infos.append(info)
                if result.pids:
                    main_info = TerminalInfo(
                        pid=result.pids[0],
                        emulator=result.emulator,
                        mode="tmux",
                        session_name=result.session_name,
                    )
                    infos.append(main_info)
                self.manager.add_all(infos)
            else:
                for pid in result.pids:
                    info = TerminalInfo(
                        pid=pid,
                        emulator=result.emulator,
                        mode="tmux",
                        session_name=result.session_name,
                    )
                    self.manager.add(info)
        else:
            for i, pid in enumerate(result.pids):
                info = TerminalInfo(
                    pid=pid,
                    emulator=result.emulator,
                    mode="standalone",
                    index=i,
                )
                self.manager.add(info)

    def _on_terminals_changed(self, terminals):
        child = self.terminal_list.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.terminal_list.remove(child)
            child = next_child

        for info in terminals:
            row = self._build_terminal_row(info)
            self.terminal_list.append(row)

        count = len(terminals)
        self.list_count_label.set_label(f"Running ({count})")
        self.close_all_btn.set_sensitive(count > 0)
        self.terminal_revealer.set_reveal_child(count > 0)

    def _build_terminal_row(self, info):
        row = Gtk.ListBoxRow()
        row._terminal_info = info
        row.set_activatable(True)

        box = Gtk.Box(spacing=8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_hexpand(True)

        dot = Gtk.Label(label="●")
        dot.add_css_class("status-dot")
        dot.add_css_class("status-running" if info.status == "running"
                          else "status-stopped")
        box.append(dot)

        name = Gtk.Label(label=info.display_name)
        name.set_halign(Gtk.Align.START)
        name.set_hexpand(True)
        name.set_xalign(0.0)
        box.append(name)

        pid_label = Gtk.Label(label=str(info.pid))
        pid_label.add_css_class("term-pid")
        box.append(pid_label)

        close_btn = Gtk.Button(label="✕")
        close_btn.add_css_class("row-close-btn")
        close_btn.set_valign(Gtk.Align.CENTER)
        info_ref = info
        close_btn.connect("clicked",
                          lambda _, i=info_ref: self.manager.close_terminal(i))
        box.append(close_btn)

        row.set_child(box)

        gesture = Gtk.GestureClick(button=3)
        info_ref2 = info
        gesture.connect("pressed", self._on_row_right_click, row, info_ref2)
        row.add_controller(gesture)

        return row

    def _on_row_right_click(self, gesture, n_press, x, y, row, info):
        self.terminal_list.select_row(row)
        self._show_context_menu(row, info, int(x), int(y))

    def _show_context_menu(self, row, info, x, y):
        popover = Gtk.Popover()
        popover.set_parent(row)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        vbox.add_css_class("popover-menu")

        items = [
            ("Close", lambda: self.manager.close_terminal(info)),
            ("Force Kill", lambda: self.manager.close_terminal(info, force=True)),
            ("Focus Window", lambda: self.manager.focus_terminal(info)),
            ("Copy PID", lambda: self._copy_pid(info.pid)),
        ]

        for label, action in items:
            btn = Gtk.Button(label=label)
            btn.connect("clicked",
                        lambda _, a=action: (a(), popover.popdown()))
            vbox.append(btn)

        popover.set_child(vbox)
        rect = Gdk.Rectangle()
        rect.x = x
        rect.y = y
        rect.width = 1
        rect.height = 1
        popover.set_pointing_to(rect)
        popover.popup()

    def _on_row_activated(self, _listbox, row):
        info = getattr(row, "_terminal_info", None)
        if info and info.status == "running":
            self.manager.focus_terminal(info)

    def _copy_pid(self, pid):
        display = Gdk.Display.get_default()
        if display:
            display.get_clipboard().set_text(str(pid))
            self._show_toast(f"PID {pid} copied to clipboard")

    def _poll_statuses(self):
        self.manager.update_statuses()
        return True

    def _show_toast(self, msg):
        toast = Adw.Toast.new(msg)
        toast.set_timeout(3)
        self._toast_overlay.add_toast(toast)

    def _show_status(self, msg):
        self.status_label.set_label(msg)
