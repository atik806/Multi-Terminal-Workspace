import math
import shutil
import subprocess

import gi

gi.require_version("Gdk", "4.0")
from gi.repository import Gdk

TERMINAL_EMULATORS = [
    ("gnome-terminal", ["gnome-terminal"]),
    ("xterm", ["xterm"]),
    ("konsole", ["konsole"]),
    ("kitty", ["kitty"]),
    ("alacritty", ["alacritty"]),
    ("tilix", ["tilix"]),
    ("terminator", ["terminator"]),
    ("xfce4-terminal", ["xfce4-terminal"]),
    ("lxterminal", ["lxterminal"]),
    ("urxvt", ["urxvt"]),
]


def resolve_emulator(name: str) -> list[str] | None:
    for label, cmd in TERMINAL_EMULATORS:
        if label == name:
            if shutil.which(cmd[0]):
                return cmd
            return None
    return None


def get_available_emulators() -> list[tuple[str, str]]:
    available = []
    for label, cmd in TERMINAL_EMULATORS:
        if shutil.which(cmd[0]):
            available.append((label, cmd[0]))
    return available


def compute_grid(count: int):
    if count <= 0:
        return []
    cols = math.ceil(math.sqrt(count))
    rows = math.ceil(count / cols)
    positions = []
    for i in range(count):
        row = i // cols
        col = i % cols
        positions.append((col, row, cols, rows))
    return positions


def get_geometry_flags(cmd_base: str, x: int, y: int, w: int, h: int) -> list[str]:
    if cmd_base in ("gnome-terminal", "terminator", "lxterminal"):
        return [f"--geometry={w}x{h}+{x}+{y}"]
    elif cmd_base in ("xterm", "urxvt"):
        return ["-geometry", f"{w}x{h}+{x}+{y}"]
    elif cmd_base == "konsole":
        return ["--geometry", f"{w}x{h}+{x}+{y}"]
    elif cmd_base in ("kitty", "alacritty"):
        return ["--geometry", f"{w}x{h}+{x}+{y}"]
    return []


def launch_terminals(
    count: int,
    emulator_name: str,
    auto_tile: bool = True,
    on_status=None,
) -> int:
    cmd_base = resolve_emulator(emulator_name)
    if cmd_base is None:
        if on_status:
            on_status(f"Terminal '{emulator_name}' not found")
        return 0

    launched = 0
    display = Gdk.Display.get_default()

    if auto_tile and display:
        monitor = display.get_primary_monitor()
        if monitor is None:
            monitor = display.get_monitor(0)
        if monitor:
            geo = monitor.get_geometry()
            screen_w = geo.width
            screen_h = geo.height
        else:
            screen_w, screen_h = 1920, 1080
    else:
        screen_w, screen_h = 1920, 1080

    positions = compute_grid(count) if auto_tile else [(0, 0, 1, 1)] * count

    for idx in range(count):
        pos = positions[idx]
        col, row, cols, rows = pos

        cell_w = screen_w // cols
        cell_h = screen_h // rows
        x = col * cell_w
        y = row * cell_h

        win_w = cell_w
        win_h = cell_h

        cmd = list(cmd_base)
        flags = get_geometry_flags(cmd_base[0], x, y, win_w, win_h)
        cmd.extend(flags)

        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            launched += 1
        except FileNotFoundError:
            if on_status:
                on_status(f"Command not found: {cmd_base[0]}")
            break
        except OSError as e:
            if on_status:
                on_status(f"Error: {e}")
            break

    return launched
