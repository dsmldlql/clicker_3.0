"""
Simplified verification stub - no verification, just basic JSON check.
"""

import json


def check_valid_json(text, bot_id=None):
    """Basic JSON validation without full verification."""
    if not text:
        return False, None
    try:
        start = text.find('{')
        end = text.rfind('}') + 1
        if start != -1 and end != 0:
            data = json.loads(text[start:end])
            return True, data
        return False, None
    except:
        return False, None


def verify_saved_json(json_data, bot_id=None):
    """Stub - always returns True."""
    return True, json_data


def load_messy_json(text):
    """Try to load JSON, return None if failed."""
    try:
        start = text.find('{')
        end = text.rfind('}') + 1
        if start != -1 and end != 0:
            return json.loads(text[start:end])
        return None
    except:
        return None
