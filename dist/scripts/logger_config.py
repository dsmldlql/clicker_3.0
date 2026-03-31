"""
Simplified logger config - no logging, just stubs.
"""

import sys


def setup_logging(name: str):
    """Simple logger setup for bot scripts"""
    class DummyLogger:
        def info(self, msg):
            pass

        def debug(self, msg):
            pass

        def warning(self, msg):
            pass

        def error(self, msg):
            pass

        def critical(self, msg):
            pass

    return DummyLogger()
