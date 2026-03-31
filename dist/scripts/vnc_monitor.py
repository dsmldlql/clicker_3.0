import subprocess
import time
import threading
import os
from typing import Optional, Dict
from datetime import datetime


class VNCHealthMonitor:
    def __init__(self, bot_count: int, check_interval: float = 30.0, bot_offset: int = 0):
        self.bot_count = bot_count
        self.check_interval = check_interval
        self.bot_offset = bot_offset
        self.stop_event = threading.Event()
        self.monitor_thread: Optional[threading.Thread] = None
        self.xvfb_failed_bots: set = set()
        self.vnc_processes: Dict[int, subprocess.Popen] = {}
        self._lock = threading.Lock()

    def check_xvfb(self, bot_id: int) -> bool:
        display = f":{100 + bot_id}"
        try:
            result = subprocess.run(
                ["pgrep", "-f", f"Xvfb.*{display}"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0 and result.stdout.strip():
                result = subprocess.run(
                    ["xdpyinfo", "-display", display],
                    capture_output=True, timeout=2
                )
                return result.returncode == 0
            return False
        except:
            return False

    def check_vnc_port(self, bot_id: int) -> bool:
        vnc_port = 5900 + bot_id
        try:
            result = subprocess.run(
                ["ss", "-tlnp"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                return str(vnc_port) in result.stdout
            return False
        except:
            return False

    def check_vnc_process(self, bot_id: int) -> bool:
        display = f":{100 + bot_id}"
        try:
            result = subprocess.run(
                ["pgrep", "-f", f"x11vnc.*{display}"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    if not pid.strip():
                        continue
                    try:
                        ps_result = subprocess.run(
                            ["ps", "-o", "stat=", "-p", pid.strip()],
                            capture_output=True, text=True, timeout=1
                        )
                        if ps_result.returncode == 0:
                            state = ps_result.stdout.strip()
                            if 'Z' not in state:
                                return True
                    except:
                        pass
                return False
            return False
        except:
            return False

    def is_xvfb_failed(self, bot_id: int) -> bool:
        with self._lock:
            return bot_id in self.xvfb_failed_bots

    def clear_xvfb_failed(self, bot_id: int):
        with self._lock:
            self.xvfb_failed_bots.discard(bot_id)

    def restore_vnc(self, bot_id: int):
        display = f":{100 + bot_id}"
        vnc_port = 5900 + bot_id

        try:
            result = subprocess.run(
                ["pgrep", "-f", f"Xvfb.*{display}"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode != 0 or not result.stdout.strip():
                size = "960x800x24"
                subprocess.Popen(
                    ["Xvfb", display, "-screen", "0", size, "-ac"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                time.sleep(1)

            result = subprocess.run(
                ["xdpyinfo", "-display", display],
                capture_output=True, timeout=2
            )
            if result.returncode != 0:
                return

            result = subprocess.run(
                ["pgrep", "-f", f"x11vnc.*{display}"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode != 0 or not result.stdout.strip():
                subprocess.Popen([
                    "x11vnc",
                    "-display", display,
                    "-rfbport", str(vnc_port),
                    "-nopw",
                    "-forever",
                    "-shared",
                    "-nowf",
                    "-noxdamage"
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(2)
        except:
            pass

    def check_all_bots(self):
        start_bot = self.bot_offset
        end_bot = self.bot_offset + self.bot_count if self.bot_count > 1 else self.bot_offset + 1

        for bot_id in range(start_bot, end_bot):
            if not self.check_xvfb(bot_id):
                with self._lock:
                    self.xvfb_failed_bots.add(bot_id)
                self.restore_vnc(bot_id)

    def run(self):
        while not self.stop_event.is_set():
            self.check_all_bots()
            time.sleep(self.check_interval)

    def start(self):
        self.monitor_thread = threading.Thread(target=self.run, daemon=True)
        self.monitor_thread.start()

    def stop(self):
        self.stop_event.set()
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
