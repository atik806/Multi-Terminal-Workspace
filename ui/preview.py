import math

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gtk, Gdk, GLib, Pango, PangoCairo


class GridPreview(Gtk.DrawingArea):
    def __init__(self):
        super().__init__()
        self._count = 4
        self._auto_tile = True
        self._use_tmux = True
        self.set_vexpand(True)
        self.set_size_request(-1, 200)
        self.set_draw_func(self._on_draw, None)

    def set_count(self, count):
        count = max(count, 1)
        if self._count != count:
            self._count = count
            self.queue_draw()

    def set_auto_tile(self, enabled):
        enabled = bool(enabled)
        if self._auto_tile != enabled:
            self._auto_tile = enabled
            self.queue_draw()

    def set_use_tmux(self, enabled):
        enabled = bool(enabled)
        if self._use_tmux != enabled:
            self._use_tmux = enabled
            self.queue_draw()

    def _on_draw(self, area, cr, width, height):
        if width < 1 or height < 1:
            return

        style_mgr = None
        try:
            gi.require_version("Adw", "1")
            from gi.repository import Adw
            style_mgr = Adw.StyleManager.get_default()
        except (ImportError, ValueError):
            pass

        is_dark = style_mgr.get_dark() if style_mgr else True

        bg = (0.12, 0.12, 0.16) if is_dark else (0.94, 0.94, 0.96)
        cr.set_source_rgb(*bg)
        cr.paint()

        if self._use_tmux and self._count > 1:
            self._draw_tmux(cr, width, height, is_dark)
        elif self._auto_tile:
            self._draw_grid(cr, width, height, is_dark)
        else:
            self._draw_untiled(cr, width, height, is_dark)

    def _rounded_rect(self, cr, x, y, w, h, r):
        r = min(r, w / 2, h / 2)
        cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
        cr.arc(x + w - r, y + r, r, 3 * math.pi / 2, 2 * math.pi)
        cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        cr.close_path()

    def _draw_tmux(self, cr, w, h, is_dark):
        padding = 24
        cx, cy = padding, padding
        cw, ch = w - 2 * padding, h - 2 * padding

        r, g, b = (0.30, 0.55, 0.85)
        cr.set_source_rgb(r, g, b)
        self._rounded_rect(cr, cx, cy, cw, ch, 10)
        cr.fill()

        panes = self._count
        pane_w = (cw - (panes - 1) * 3) / panes
        for i in range(panes):
            px = cx + i * (pane_w + 3) + 6
            py = cy + 30
            pw = pane_w - 12
            ph = ch - 50
            cr.set_source_rgba(0, 0, 0, 0.15)
            self._rounded_rect(cr, px, py, pw, ph, 4)
            cr.fill()

            cr.set_source_rgba(0, 0, 0, 0.3)
            cr.set_line_width(1)
            self._rounded_rect(cr, px, py, pw, ph, 4)
            cr.stroke()

        layout = PangoCairo.create_layout(cr)
        font_desc = Pango.FontDescription.from_string("Sans Bold 16")
        layout.set_font_description(font_desc)
        layout.set_text("tmux")
        extents = layout.get_pixel_extents()
        lw, lh = extents[1].width, extents[1].height
        cr.set_source_rgb(1, 1, 1)
        cr.move_to(cx + (cw - lw) / 2, cy + 4)
        PangoCairo.show_layout(cr, layout)

        sub = f"{self._count} panes"
        layout2 = PangoCairo.create_layout(cr)
        font_desc2 = Pango.FontDescription.from_string("Sans 11")
        layout2.set_font_description(font_desc2)
        layout2.set_text(sub)
        ext2 = layout2.get_pixel_extents()
        sw, sh = ext2[1].width, ext2[1].height
        cr.set_source_rgb(1, 1, 1)
        cr.move_to(cx + (cw - sw) / 2, cy + ch - sh - 6)
        PangoCairo.show_layout(cr, layout2)

    def _draw_grid(self, cr, w, h, is_dark):
        cols = max(math.ceil(math.sqrt(self._count)), 1)
        rows = max(math.ceil(self._count / cols), 1)
        padding = 20
        gap = 5

        avail_w = w - 2 * padding
        avail_h = h - 2 * padding
        cell_w = (avail_w - (cols - 1) * gap) / cols
        cell_h = (avail_h - (rows - 1) * gap) / rows

        cell_w = max(cell_w, 10)
        cell_h = max(cell_h, 10)

        for i in range(self._count):
            col = i % cols
            row_i = i // cols
            cx = padding + col * (cell_w + gap)
            cy = padding + row_i * (cell_h + gap)

            if is_dark:
                t = i / max(self._count - 1, 1)
                r = 0.21 + 0.30 * (1 - t)
                g = 0.52 + 0.20 * t
                b = 0.89 - 0.10 * t
            else:
                t = i / max(self._count - 1, 1)
                r = 0.21 + 0.30 * t
                g = 0.52 + 0.10 * (1 - t)
                b = 0.89

            cr.set_source_rgb(r, g, b)
            radius = min(6, cell_w / 3, cell_h / 3)
            self._rounded_rect(cr, cx, cy, cell_w, cell_h, radius)
            cr.fill()

            text = str(i + 1)
            layout = PangoCairo.create_layout(cr)
            font_desc = Pango.FontDescription.from_string(
                f"Sans Bold {max(9, min(int(cell_w * 0.4), int(cell_h * 0.4)))}"
            )
            layout.set_font_description(font_desc)
            layout.set_text(text)
            ink, log = layout.get_pixel_extents()
            tx = cx + (cell_w - log.width) / 2
            ty = cy + (cell_h + log.height) / 2
            cr.set_source_rgb(1, 1, 1)
            cr.move_to(tx, ty)
            PangoCairo.show_layout(cr, layout)

        label = f"{self._count} terminals — {cols}×{rows} grid"
        layout = PangoCairo.create_layout(cr)
        font_desc = Pango.FontDescription.from_string("Sans 11")
        layout.set_font_description(font_desc)
        layout.set_text(label)
        ink, log = layout.get_pixel_extents()
        lx = (w - log.width) / 2
        ly = h - 6
        gray = (0.55, 0.55, 0.60) if is_dark else (0.40, 0.40, 0.45)
        cr.set_source_rgb(*gray)
        cr.move_to(lx, ly)
        PangoCairo.show_layout(cr, layout)

    def _draw_untiled(self, cr, w, h, is_dark):
        padding = 20
        gap = 10
        count = min(self._count, 12)
        cols = min(count, 4)
        rows_vis = math.ceil(count / cols) if cols > 0 else 1

        diag = 30
        spacing_x = (w - 2 * padding - diag) / max(cols - 1, 1) if cols > 1 else 0
        spacing_y = (h - 2 * padding - diag) / max(rows_vis - 1, 1) if rows_vis > 1 else 0

        for i in range(count):
            col = i % cols
            row_i = i // cols
            ox = col * spacing_x + (row_i * 3)
            oy = row_i * spacing_y + (col * 2)
            cx = padding + ox
            cy = padding + oy

            t = i / max(count - 1, 1)
            r = 0.40 + 0.30 * t
            g = 0.50 + 0.30 * (1 - t)
            b = 0.85
            cr.set_source_rgb(r, g, b)
            self._rounded_rect(cr, cx, cy, diag, diag * 0.7, 4)
            cr.fill()

        label = f"{self._count} terminals (no tiling)"
        layout = PangoCairo.create_layout(cr)
        font_desc = Pango.FontDescription.from_string("Sans 11")
        layout.set_font_description(font_desc)
        layout.set_text(label)
        ink, log = layout.get_pixel_extents()
        gray = (0.55, 0.55, 0.60) if is_dark else (0.40, 0.40, 0.45)
        cr.set_source_rgb(*gray)
        cr.move_to((w - log.width) / 2, h - 6)
        PangoCairo.show_layout(cr, layout)
