"""
Simplified state logger - no logging, just stubs.
"""

import time
from typing import Optional, Dict, Any


class StateTimer:
    def __init__(self):
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.condition_start: Optional[float] = None
        self.condition_end: Optional[float] = None

    def start(self):
        self.start_time = time.time()
        self.end_time = None

    def mark_condition_start(self):
        self.condition_start = time.time()

    def mark_condition_end(self):
        self.condition_end = time.time()

    def stop(self):
        self.end_time = time.time()

    def get_elapsed(self) -> float:
        if self.start_time is None:
            return 0.0
        end = self.end_time if self.end_time else time.time()
        return end - self.start_time

    def get_condition_time(self) -> float:
        if self.condition_start is None:
            return 0.0
        end = self.condition_end if self.condition_end else time.time()
        return end - self.condition_start

    def reset(self):
        self.__init__()


class StateLogger:
    def __init__(self, bot_id: int, site: str, scenario: str, log_dir: str):
        self.bot_id = bot_id
        self.site = site
        self.scenario = scenario
        self.log_dir = log_dir
        self.current_state: Optional[str] = None
        self.previous_state: Optional[str] = None
        self.state_timer = StateTimer()
        self.transition_time: Optional[float] = None
        self.state_stats: Dict[str, Dict[str, Any]] = {}

    def enter_state(self, state: str, from_state: Optional[str] = None):
        self.state_timer.start()
        self.previous_state = self.current_state
        self.current_state = state

    def mark_trigger_found(self):
        pass

    def mark_condition_start(self):
        self.state_timer.mark_condition_start()

    def mark_condition_result(self, success: bool, condition_type: str = "unknown"):
        self.state_timer.mark_condition_end()

    def exit_state(self, success: bool, next_state: str, reason: str = "normal"):
        self.state_timer.stop()
        self.transition_time = time.time()

    def log_timeout(self, timeout_sec: float, state: Optional[str] = None):
        pass

    def log_error(self, error: str, details: Optional[Dict] = None):
        pass

    def get_stats_summary(self) -> Dict[str, Any]:
        return {
            "bot_id": self.bot_id,
            "site": self.site,
            "scenario": self.scenario,
            "current_state": self.current_state,
            "states": {}
        }

    def print_stats(self):
        pass
