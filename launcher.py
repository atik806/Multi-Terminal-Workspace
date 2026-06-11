import math
import os
import shutil
import subprocess
import tempfile

import gi

gi.require_version("Gdk", "4.0")
from gi.repository import Gdk

TERMINAL_EMULATORS = [
    ("ptyxis", ["ptyxis"]),
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

KNOWN_TERMINAL_NAMES = {name for name, _ in TERMINAL_EMULATORS}


def resolve_symlinks(path: str) -> str:
    return os.path.realpath(path)


def detect_default_terminal() -> str | None:
    candidate = shutil.which("x-terminal-emulator")
    if candidate:
        return resolve_symlinks(candidate)
    env = os.environ.get("TERMINAL")
    if env and shutil.which(env):
        return resolve_symlinks(shutil.which(env))
    return None


def resolve_emulator(name: str) -> list[str] | None:
    if name == "System Default":
        path = detect_default_terminal()
        if path:
            return [path]
        return None
    for label, cmd in TERMINAL_EMULATORS:
        if label == name:
            if shutil.which(cmd[0]):
                return cmd
            return None
    return None


def get_terminal_real_name(cmd_base: str) -> str:
    return os.path.basename(resolve_symlinks(cmd_base))


def get_available_emulators() -> list[tuple[str, str]]:
    available = []
    for label, cmd in TERMINAL_EMULATORS:
        if shutil.which(cmd[0]):
            available.append((label, cmd[0]))
    default = detect_default_terminal()
    if default and os.path.basename(default) not in KNOWN_TERMINAL_NAMES:
        available.insert(0, ("System Default", default))
    return available


def tmux_available() -> bool:
    return shutil.which("tmux") is not None


def build_tmux_script(session_name: str, count: int) -> str:
    lines = [
        "#!/bin/bash",
        f"tmux new-session -d -s {session_name}",
    ]
    for _ in range(count - 1):
        lines.append(f"tmux split-window -t {session_name}")
    lines.append(f"tmux select-layout -t {session_name} tiled 2>/dev/null")
    lines.append(f"tmux set-option -t {session_name} remain-on-exit off 2>/dev/null")
    lines.append(f"tmux attach -t {session_name}")
    lines.append(
        f"tmux kill-session -t {session_name} 2>/dev/null"
    )
    return "\n".join(lines) + "\n"


def get_exec_flags(term_bin: str, command: str) -> list[str]:
    name = os.path.basename(resolve_symlinks(term_bin))
    if name == "ptyxis":
        return ["-x", command]
    elif name in ("gnome-terminal",):
        return ["--", "bash", "-c", command]
    elif name in ("xterm", "urxvt"):
        return ["-e", command]
    elif name == "konsole":
        return ["-e", command]
    elif name in ("kitty", "alacritty"):
        return ["-e", command]
    elif name in ("terminator",):
        return ["-e", command]
    return ["-e", command]


def launch_terminals(
    count: int,
    emulator_name: str,
    auto_tile: bool = True,
    use_tmux: bool = True,
    on_status=None,
) -> int:
    cmd_base = resolve_emulator(emulator_name)
    if cmd_base is None:
        if on_status:
            on_status(f"Terminal '{emulator_name}' not found")
        return 0

    if use_tmux and tmux_available():
        session_name = f"multi-terminal-{os.getpid()}"
        script = build_tmux_script(session_name, count)

        fd, script_path = tempfile.mkstemp(
            suffix=".sh", prefix="multi-terminal-", dir="/tmp"
        )
        with os.fdopen(fd, "w") as f:
            f.write(script)
        os.chmod(script_path, 0o755)

        term_bin = cmd_base[0]
        cmd = [term_bin] + get_exec_flags(term_bin, script_path)

        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return count
        except (FileNotFoundError, OSError) as e:
            os.unlink(script_path)
            if on_status:
                on_status(f"Error: {e}")
            return 0

    launched = 0
    display = Gdk.Display.get_default()

    if auto_tile and display:
        try:
            monitors = list(display.get_monitors())
            monitor = monitors[0] if monitors else None
        except AttributeError:
            monitor = None
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


def compute_grid(count: int):
    if count <= 0:
        return []
    cols = math.ceil(math.sqrt(count))
    rows = math.ceil(count / cols)
    positions = []
    for i in range(count):
        col = i % cols
        row = i // cols
        positions.append((col, row, cols, rows))
    return positions


def get_geometry_flags(cmd_base: str, x: int, y: int, w: int, h: int) -> list[str]:
    name = get_terminal_real_name(cmd_base)
    if name in ("ptyxis", "gnome-terminal", "terminator", "lxterminal"):
        return [f"--geometry={w}x{h}+{x}+{y}"]
    elif name in ("xterm", "urxvt"):
        return ["-geometry", f"{w}x{h}+{x}+{y}"]
    elif name == "konsole":
        return ["--geometry", f"{w}x{h}+{x}+{y}"]
    elif name in ("kitty", "alacritty"):
        return ["--geometry", f"{w}x{h}+{x}+{y}"]
    return []
