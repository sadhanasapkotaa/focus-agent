"""
Process guard.
Kills anything in the kill-list, plus any Chrome/browser that is NOT a
descendant of this Python process (the agent).
"""
import os
import psutil
from threading import Thread, Event
from typing import Set


BROWSER_NAMES = ("chrome", "google-chrome", "google-chrome-stable",
                 "chromium", "chromium-browser", "brave", "brave-browser")


class ProcessGuard:
    def __init__(self, allowed: Set[str], kill_list: Set[str],
                 poll_seconds: int = 3):
        self.allowed = {a.lower() for a in allowed}
        self.kill_list = {k.lower() for k in kill_list}
        self.poll_seconds = poll_seconds
        self._stop = Event()
        self._thread: Thread | None = None
        self.own_pid = os.getpid()
        self.own_children: Set[int] = set()

    def register_child(self, pid: int):
        self.own_children.add(pid)

    def _is_descendant_of_agent(self, proc: psutil.Process) -> bool:
        """True if this process or one of its ancestors is the agent
        or an explicitly-registered child (e.g. the Playwright browser)."""
        try:
            current = proc
            seen = set()
            while current and current.pid not in seen:
                seen.add(current.pid)
                if current.pid == self.own_pid:
                    return True
                if current.pid in self.own_children:
                    return True
                try:
                    current = current.parent()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    return False
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
        return False

    def _should_kill(self, proc: psutil.Process) -> bool:
        try:
            name = proc.name().lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

        # Never kill ourselves or our parent shell.
        try:
            if proc.pid == self.own_pid:
                return False
            if proc.pid == os.getppid():
                return False
        except Exception:
            pass

        if self._is_descendant_of_agent(proc):
            return False

        # Crashpad handlers are per-profile helpers spawned by any Chrome
        # instance. Killing them is harmless but very noisy at startup.
        if name.startswith("chrome_crashpad_handler"):
            return False

        # Browsers: kill unless they descend from the agent.
        if any(name.startswith(b) for b in BROWSER_NAMES):
            return True

        # Explicit kill-list.
        stems = {k.removesuffix(".exe") for k in self.kill_list}
        if name in self.kill_list or any(name.startswith(k) for k in stems):
            return True

        return False

    def _loop(self):
        while not self._stop.is_set():
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    if self._should_kill(proc):
                        print(f"[guard] Killing {proc.info['name']} "
                              f"(pid={proc.info['pid']})")
                        proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied,
                        psutil.ZombieProcess):
                    pass
            self._stop.wait(self.poll_seconds)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("[guard] Started.")

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        print("[guard] Stopped.")