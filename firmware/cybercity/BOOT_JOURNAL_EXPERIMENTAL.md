# Cyber City redundant boot journal — experimental

This is a **manual/opt-in journal prototype** and does not alter device boot.py, production startup, MQTT, LabTech APIs, firmware installer or building machines.

The two separately written journal slots contain monotonically increasing generation numbers, firmware version, attempt count, explicit confirmation state and SHA-256 checksum. Any damaged on-disk slot now forces a manual-recovery decision, even when an older valid generation survives. Gaps between two valid generation numbers also fail closed. This improves resilience but **does not guarantee power-loss atomicity, flash durability or rollback**.

Caution: falling back to an older valid generation after an interrupted attempt write may undercount real candidate starts. Therefore, never use this prototype as an automatic boot gate or as a guarantee of the 3-attempt limit on real hardware. Confirmation currently depends on explicit external health verification. Recovery of corrupt application files and metadata reconciliation are not implemented.

Next: use a hardware-tested protected boot supervisor with fail-safe monotonic attempt storage, validated app identity, watchdog health handshake, and verified rollback. Test power cuts at every write boundary and before/after boot, full flash, filesystem variants and USB recovery before enabling unattended OTA.

Host tests: `python -m unittest discover -s firmware/cybercity/tools -p 'test_boot_journal.py'`. These tests do not simulate physical flash/power behavior.
