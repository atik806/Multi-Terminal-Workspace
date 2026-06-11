import os
import signal
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class TerminalInfo:
    pid: int
    emulator: str
    mode: str
    session_name: str | None = None
    pane_id: str | None = None
    index: int = 0
    status: str = "running"
    launched_at: float = field(default_factory=time.time)

    @property
    def display_name(self) -> str:
        if self.mode == "tmux" and self.pane_id:
            return f"tmux pane {self.pane_id}"
        if self.mode == "tmux":
            return f"{self.emulator} (tmux)"
        return f"{self.emulator} #{self.index + 1}"


class TerminalManager:
    def __init__(self):
        self.terminals: list[TerminalInfo] = []
        self._listeners: list[Callable] = []

    def add(self, info: TerminalInfo):
        self.terminals.append(info)
        self._notify()

    def add_all(self, infos: list[TerminalInfo]):
        self.terminals.extend(infos)
        self._notify()

    def close_terminal(self, info: TerminalInfo, force: bool = False) -> bool:
        if info.mode == "tmux" and info.session_name:
            if info.pane_id:
                subprocess.run(
                    ["tmux", "kill-pane", "-t", info.pane_id],
                    capture_output=True,
                )
                info.status = "stopped"
                self._check_tmux_session_dead(info.session_name)
            else:
                self._kill_tmux_session(info.session_name)
                self._kill_pid(info.pid, force)
                info.status = "stopped"
        else:
            self._kill_pid(info.pid, force)
            info.status = "stopped"

        self._cleanup_stopped()
        self._notify()
        return True

    def close_all(self, force: bool = False):
        sessions = set()
        for info in self.terminals:
            if info.mode == "tmux" and info.session_name:
                sessions.add(info.session_name)
            else:
                self._kill_pid(info.pid, force)

        for session in sessions:
            self._kill_tmux_session(session)

        for info in self.terminals:
            if info.mode == "tmux" and not info.pane_id:
                self._kill_pid(info.pid, force)

        self.terminals.clear()
        self._notify()

    def focus_terminal(self, info: TerminalInfo) -> bool:
        pid = info.pid
        if shutil.which("wmctrl"):
            result = subprocess.run(
                ["wmctrl", "-l", "-p"],
                capture_output=True, text=True,
            )
            for line in result.stdout.splitlines():
                parts = line.split(None, 3)
                if len(parts) >= 3:
                    try:
                        if int(parts[2]) == pid:
                            subprocess.Popen(["wmctrl", "-i", "-a", parts[0]])
                            return True
                    except ValueError:
                        pass
        if shutil.which("xdotool"):
            result = subprocess.run(
                ["xdotool", "search", "--pid", str(pid)],
                capture_output=True, text=True,
            )
            for wid in result.stdout.strip().splitlines():
                subprocess.Popen(["xdotool", "windowactivate", wid])
                return True
        return False

    def update_statuses(self):
        changed = False
        for info in list(self.terminals):
            if info.status != "running":
                continue
            alive = False
            if info.mode == "tmux":
                if info.session_name:
                    result = subprocess.run(
                        ["tmux", "has-session", "-t", info.session_name],
                        capture_output=True,
                    )
                    if result.returncode == 0:
                        if info.pane_id:
                            pr = subprocess.run(
                                ["tmux", "list-panes", "-t", info.session_name,
                                 "-F", "#{pane_id}"],
                                capture_output=True, text=True,
                            )
                            alive = info.pane_id in pr.stdout
                        else:
                            pr = subprocess.run(
                                ["tmux", "list-panes", "-t", info.session_name],
                                capture_output=True, text=True,
                            )
                            alive = pr.returncode == 0 and pr.stdout.strip()
                    if not alive and result.returncode != 0:
                        for t in self.terminals:
                            if t.session_name == info.session_name and t.status == "running":
                                t.status = "stopped"
                                changed = True
            else:
                alive = self._pid_exists(info.pid)

            if not alive and info.status == "running":
                info.status = "stopped"
                changed = True

        if changed:
            self._cleanup_stopped()
            self._notify()

    def get_running_count(self) -> int:
        return sum(1 for t in self.terminals if t.status == "running")

    def on_change(self, callback: Callable):
        self._listeners.append(callback)

    def _notify(self):
        for cb in self._listeners:
            cb(list(self.terminals))

    def _cleanup_stopped(self):
        self.terminals = [t for t in self.terminals if t.status == "running"]

    def _check_tmux_session_dead(self, session_name: str):
        result = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True,
        )
        if result.returncode != 0:
            for t in self.terminals:
                if t.session_name == session_name and t.status == "running":
                    t.status = "stopped"

    def _kill_tmux_session(self, session_name: str):
        subprocess.run(
            ["tmux", "kill-session", "-t", session_name],
            capture_output=True,
        )

    def _kill_pid(self, pid: int, force: bool = False):
        try:
            sig = signal.SIGKILL if force else signal.SIGTERM
            os.kill(pid, sig)
        except ProcessLookupError:
            pass

    def _pid_exists(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False
