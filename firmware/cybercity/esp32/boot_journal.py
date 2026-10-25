"""Opt-in two-slot boot journal prototype for MicroPython device testing.

Never invoked automatically by boot.py. An interrupted write may leave a
partial inactive slot; a validated older slot remains readable. File rename
atomicity and flash durability must be checked on target hardware.
"""
import os
try:
    import ujson as json
except ImportError:
    import json
try:
    import uhashlib as hashlib
except ImportError:
    import hashlib

SLOTS = ("ota-boot-a.json", "ota-boot-b.json")
MAX_ATTEMPTS = 3


def _checksum(sequence, version, attempts, confirmed):
    raw = "%d:%d:%d:%d" % (sequence, version, attempts, 1 if confirmed else 0)
    return hashlib.sha256(raw.encode()).digest()


def _read_slot(path):
    try:
        with open(path, "r") as handle:
            value = json.loads(handle.read())
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(value, dict):
        return None
    seq, ver, tries, confirmed, digest = (value.get("sequence"),
                                          value.get("version"),
                                          value.get("attempts"),
                                          value.get("confirmed"),
                                          value.get("checksum"))
    if (type(seq) is not int or seq < 1 or type(ver) is not int or ver < 1 or
            type(tries) is not int or not 0 <= tries <= MAX_ATTEMPTS or
            type(confirmed) is not bool or not isinstance(digest, str)):
        return None
    expected = "".join("%02x" % byte for byte in _checksum(seq, ver, tries, confirmed))
    return value if expected == digest else None


def snapshot():
    """Only return trustworthy state; reject any damaged on-disk generation.

    A partially written newer record may hide a recorded attempt. Until a
    hardware-tested monotonic journal exists, require operator inspection.
    """
    a, b = _read_slot(SLOTS[0]), _read_slot(SLOTS[1])
    if a is None and b is None:
        for path in SLOTS:
            try:
                os.stat(path)
            except OSError:
                continue
            raise ValueError("No valid boot journal slot; manual recovery required")
        return None
    for path, record in ((SLOTS[0], a), (SLOTS[1], b)):
        if record is None:
            try:
                os.stat(path)
            except OSError:
                continue
            raise ValueError("Damaged boot journal slot; manual recovery required")
    if a is None:
        return b
    if b is None:
        return a
    if a["sequence"] == b["sequence"] and a != b:
        raise ValueError("Conflicting boot journal generations")
    if abs(a["sequence"] - b["sequence"]) != 1:
        raise ValueError("Boot journal sequence gap; manual recovery required")
    return a if a["sequence"] >= b["sequence"] else b


def _write(version, attempts, confirmed):
    current = snapshot()
    seq = current["sequence"] + 1 if current else 1
    target = SLOTS[seq % 2]
    digest = "".join("%02x" % n for n in _checksum(seq, version, attempts, confirmed))
    data = {"sequence": seq, "version": version, "attempts": attempts,
            "confirmed": confirmed, "checksum": digest}
    # Write to inactive generation. Never remove the previous valid slot.
    # On power interruption the old slot remains a fallback (subject to
    # actual filesystem guarantees, which must be hardware-tested).
    with open(target, "w") as out:
        out.write(json.dumps(data))
        out.flush()
        if hasattr(os, "sync"):
            os.sync()
    if _read_slot(target) != data:
        raise OSError("Journal write verification failed")
    return data


def initialize(version, approve=False):
    if approve is not True or type(version) is not int or version < 1:
        raise ValueError("Explicit approval and positive firmware version required")
    if snapshot() is not None:
        raise ValueError("Boot journal already initialized")
    return _write(version, 0, False)


def record_attempt(version, approve=False):
    if approve is not True:
        raise ValueError("Explicit approval required")
    old = snapshot()
    if old is None or old["version"] != version or old["confirmed"]:
        raise ValueError("No matching pending candidate")
    if old["attempts"] >= MAX_ATTEMPTS:
        return {"action": "manual_recovery_required", "attempts": old["attempts"]}
    fresh = _write(version, old["attempts"] + 1, False)
    return {"action": "candidate_test_permitted", "attempts": fresh["attempts"]}


def confirm(version, healthy=False, approve=False):
    if approve is not True or healthy is not True:
        raise ValueError("Approval and externally verified health required")
    old = snapshot()
    if old is None or old["version"] != version or old["attempts"] < 1:
        raise ValueError("No matching attempted candidate")
    return _write(version, old["attempts"], True)
