"""
Auto mode: runs whichever scheduled mode is active, each in its own
subprocess (`python main.py <mode> --no-guard`), so a slot boundary can
kill the whole process tree cleanly (browser, mpv/vlc, everything).
The guard is active only while a slot is active.
"""
import signal
import subprocess
import sys
import time
from pathlib import Path

import psutil

from core.guard import ProcessGuard
from core.schedule import current_slot, seconds_until_next_slot

BROWSER_MODES = {"coursera", "wqu", "revision", "dsa"}
VALID_MODES = BROWSER_MODES | {"shows"}
TICK_SECONDS = 5


def _kill_tree(proc: subprocess.Popen):
    try:
        p = psutil.Process(proc.pid)
        victims = p.children(recursive=True) + [p]
    except psutil.NoSuchProcess:
        return
    for v in victims:
        try:
            v.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    try:
        proc.wait(timeout=5)
    except Exception:
        pass


class AutoMode:
    name = "auto"

    def __init__(self, config: dict, guard=None):
        # `guard` accepted for compatibility; auto manages its own.
        self.config = config
        self.schedule = config.get("schedule", [])
        if not self.schedule:
            raise SystemExit("[auto] config.json has no 'schedule' block.")
        self.main_py = Path(__file__).resolve().parents[1] / "main.py"
        self.guard = None
        self.child = None
        self.child_started = 0.0
        self.slot_key = None

    def _make_guard(self):
        return ProcessGuard(
            allowed=set(self.config["allowed_processes"]),
            kill_list=set(self.config["kill_processes"]),
            poll_seconds=self.config.get("poll_seconds", 2),
        )

    def _spawn(self, slot):
        mode = slot["mode"]
        cmd = [sys.executable, str(self.main_py), mode, "--no-guard"]
        if mode in BROWSER_MODES:
            wait = seconds_until_next_slot(self.schedule)
            cmd += ["--session-minutes", str(max(1, wait // 60))]
        print(f"[auto] Starting {mode} ({slot['start']}-{slot['end']})", flush=True)
        self.child_started = time.monotonic()
        return subprocess.Popen(cmd)

    def _teardown(self):
        if self.child is not None:
            print("[auto] Killing active mode.", flush=True)
            _kill_tree(self.child)
            self.child = None
        if self.guard is not None:
            self.guard.stop()
            self.guard = None

    def run(self):
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        try:
            self._loop()
        except (KeyboardInterrupt, SystemExit):
            print("[auto] Stopped.", flush=True)
        finally:
            self._teardown()

    def _loop(self):
        while True:
            slot = current_slot(self.schedule)
            key = (slot["mode"], slot["start"], slot["end"]) if slot else None

            if key != self.slot_key:  # boundary: start, end, or switch
                self._teardown()
                if slot is not None:
                    self.guard = self._make_guard()
                    self.guard.start()
                self.slot_key = key

            if slot is None:
                time.sleep(min(30, max(1, seconds_until_next_slot(self.schedule))))
                continue

            if slot["mode"] not in VALID_MODES:
                print(f"[auto] Unknown mode in schedule: {slot['mode']}", flush=True)
                time.sleep(60)
                continue

            if self.child is None or self.child.poll() is not None:
                if self.child is not None:
                    ran = time.monotonic() - self.child_started
                    print(f"[auto] {slot['mode']} exited (code {self.child.returncode}).", flush=True)
                    time.sleep(5 if ran > 10 else 30)  # back off on crash loops
                self.child = self._spawn(slot)

            time.sleep(TICK_SECONDS)
