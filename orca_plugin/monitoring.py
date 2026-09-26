"""Conservative monitoring helpers; no inferred successful print from 100% alone."""
import math


def number(value, scale=1):
    if isinstance(value, bool):
        return None
    try:
        result = float(value) * scale
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def phase(state):
    state = str(state).lower()
    if state in {"running", "printing"}:
        return "printing"
    if state in {"pause", "paused", "pausing"}:
        return "paused"
    if state in {"finish", "finished", "complete", "completed"}:
        return "completed"
    if state in {"failed", "error", "shutdown"}:
        return "error"
    if state in {"cancel", "cancelled", "canceled", "stopped"}:
        return "cancelled"
    if state in {"idle", "ready", "standby", "operational"}:
        return "idle"
    return "unknown"


def percent(value, scale=1):
    result = number(value, scale)
    return result if result is not None and 0 <= result <= 100 else None


def merge_delta(target, update):
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            merge_delta(target[key], value)
        else:
            target[key] = value
