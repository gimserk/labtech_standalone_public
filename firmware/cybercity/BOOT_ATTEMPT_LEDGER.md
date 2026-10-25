# Persistent boot attempt ledger — controlled staging

This module is **not an automatic boot supervisor**. No existing boot.py,
main.py, LabTech endpoint, MQTT path, OTA setting, or VM is changed.

An operator can initialize a candidate version with
`begin_candidate(version, approve=True)`, explicitly record attempts using
`record_attempt(version, approve=True)`, and confirm actual health via
`confirm_healthy(version, healthy=True, approve=True)`. Three unconfirmed
attempts result in **manual_recovery_required**, not autonomous execution or
rollback. The existing protected recovery preflight remains separate.

**Known gaps before unattended OTA**: MicroPython filesystem rename-overwrite
semantics differ from CPython; the ledger replacement is not power-loss atomic,
and a rename failure can prevent recording subsequent attempts. A protected
boot entry point, independent health confirmation, version reconciliation and
robust two-record/power-cut-tolerant journal still need design and on-device
tests. Do not attach this ledger to boot.py until those gates are met.

Run host-side tests:
`python -m unittest discover -s firmware/cybercity/tools -p 'test_boot_attempts.py'`

Acceptance test on a sacrificial ESP32: repeat resets mid-ledger write, verify
that corrupt states fail closed, measure flash usage, verify existing startup
still functions, and validate USB/REPL rescue procedure.
