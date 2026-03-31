"""
Simplified bot logger - no logging, just stubs.
"""


class BotLogger:
    def __init__(self, bot_id: int, project: str = "unknown", site: str = "unknown",
                 scenario: str = "unknown", log_dir: str = "logs"):
        self.bot_id = bot_id

    def info(self, event: str, data=None):
        pass

    def success(self, event: str, data=None):
        pass

    def action(self, action_name: str, details=None):
        pass

    def action_failed(self, action_name: str, error: str, details=None):
        pass

    def error(self, event: str, error: str, data=None):
        pass

    def warning(self, event: str, message: str, data=None):
        pass

    def debug(self, event: str, data=None):
        pass

    def state_enter(self, state_name: str, details=None):
        pass

    def state_exit(self, state_name: str, success: bool, details=None):
        pass

    def log_operation(self, operation: str, success: bool, duration_ms=None, details=None):
        pass

    def log_click(self, coords: tuple, success: bool, element: str = "unknown"):
        pass

    def log_json_saved(self, filepath: str, uid: str, global_idx: int):
        pass

    def log_json_failed(self, reason: str, uid=None):
        pass

    def log_question_advance(self, old_idx: int, new_idx: int, uid: str):
        pass

    def log_clipboard(self, operation: str, success: bool, content_preview=None):
        pass

    def log_browser_action(self, action: str, success: bool, details=None):
        pass

    def log_verification(self, verification_type: str, success: bool, details=None):
        pass

    def log_timeout(self, state: str, elapsed: float, timeout: float):
        pass

    def log_reset(self, reason: str):
        pass

    def get_stats(self):
        return {}

    def log_stats(self):
        pass

    def log_shutdown(self):
        pass

    def log_csv_operation(self, event_type: str, global_index=None, question_uid=None):
        pass


class LogManager:
    _instance = None
    _loggers = {}
    _shared_csv_loggers = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_logger(self, bot_id: int, project: str = "unknown", site: str = "unknown",
                   scenario: str = "unknown") -> BotLogger:
        if bot_id not in self._loggers:
            self._loggers[bot_id] = BotLogger(bot_id, project, site, scenario)
        return self._loggers[bot_id]

    def get_shared_csv_logger(self, site: str, scenario: str):
        key = f"{site}__{scenario}"
        if key not in self._shared_csv_loggers:
            self._shared_csv_loggers[key] = SharedCSVLogger(site, scenario)
        return self._shared_csv_loggers[key]


class SharedCSVLogger:
    def __init__(self, site: str, scenario: str, log_dir: str = "logs"):
        pass

    def log(self, bot_id: int, event_type: str, attempt_number=None,
            global_index=None, question_uid=None):
        pass


def get_bot_logger(bot_id: int, project: str = "unknown", site: str = "unknown",
                   scenario: str = "unknown") -> BotLogger:
    manager = LogManager()
    return manager.get_logger(bot_id, project, site, scenario)


def get_shared_csv_logger(site: str, scenario: str) -> SharedCSVLogger:
    manager = LogManager()
    return manager.get_shared_csv_logger(site, scenario)


def log_global_stats():
    pass
