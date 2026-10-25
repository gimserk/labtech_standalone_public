"""Persistent candidate-attempt ledger for a future protected ESP32 boot supervisor.

Never imports boot.py, executes firmware, resets hardware or performs rollback.
The operator must explicitly record starts and verified healthy boots.
This file is deliberately separate from existing production startup.
"""
import os
try:
    import ujson as json
except ImportError:
    import json

LEDGER = "ota-boot-attempts.json"
MAX_ATTEMPTS = 3


def _read():
    try:
        with open(LEDGER, "r") as stream:
            data = json.loads(stream.read())
    except OSError:
        return None
    except (ValueError, TypeError):
        raise ValueError("Boot ledger is corrupt; manual recovery required")
    if (not isinstance(data, dict) or type(data.get("version")) is not int or
            data["version"] < 1 or type(data.get("attempts")) is not int or
            data["attempts"] < 0 or data["attempts"] > MAX_ATTEMPTS or
            type(data.get("confirmed")) is not bool):
        raise ValueError("Boot ledger is invalid; manual recovery required")
    return data


def status():
    data = _read()
    if data is None:
        return {"state": "not_initialized", "attempts": 0}
    state = ("confirmed" if data["confirmed"] else
             "retry_limit_reached" if data["attempts"] >= MAX_ATTEMPTS else
             "candidate_unconfirmed")
    return {"state": state, "version": data["version"], "attempts": data["attempts"]}


def _write(data):
    temp = LEDGER + ".tmp"
    # Failure to replace ledger must be surfaced; do not start a candidate
    # based on an unrecorded attempt. Rename semantics vary by filesystem.
    with open(temp, "w") as stream:
        stream.write(json.dumps(data))
    os.rename(temp, LEDGER)


def begin_candidate(version, approve=False):
    """Explicitly start tracking one candidate; not a boot or OTA operation."""
    if approve is not True or type(version) is not int or version < 1:
        raise ValueError("Explicit approval and positive version required")
    if _read() is not None:
        raise ValueError("Ledger already exists; do not replace pending history")
    _write({"version": version, "attempts": 0, "confirmed": False})
    return status()


def record_attempt(version, approve=False):
    """Return a decision; never run firmware or restore files."""
    if approve is not True:
        raise ValueError("Explicit approve=True required")
    data = _read()
    if data is None or data["version"] != version or data["confirmed"]:
        raise ValueError("Candidate is not pending in boot ledger")
    if data["attempts"] >= MAX_ATTEMPTS:
        return {"action": "manual_recovery_required", "attempts": data["attempts"]}
    data["attempts"] += 1
    _write(data)
    return {"action": "candidate_test_permitted", "attempts": data["attempts"]}


def confirm_healthy(version, healthy=False, approve=False):
    """Only an independent application health check may call this explicitly."""
    if approve is not True or healthy is not True:
        raise ValueError("External health confirmation and approval required")
    data = _read()
    if data is None or data["version"] != version or data["attempts"] < 1:
        raise ValueError("No matching attempted firmware candidate")
    data["confirmed"] = True
    _write(data)
    return status()
