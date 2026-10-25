# ESP32 startup health gate (advisory prototype)

This module is a pure decision helper. It is **not wired into boot.py or the running controller**, and it does not perform checks independently. Its booleans are supplied by a caller, so it is not an independent proof of firmware health.

The check set covers Wi-Fi, validated LabTech device configuration, MQTT connection, GPIO initialization, and the running firmware version. Each must be explicitly true, and the pending firmware journal must match the requested version with at least one attempt and no confirmation.

Before a real protected boot supervisor may use this logic, hardware testing must supply authenticated or trusted signals from the actual running application, bound to boot identity and observed across a stability window. Avoid treating a single MQTT connection as successful boot validation. Confirm safe pin defaults, watchdog reset behavior and sustained runtime. Do not automatically call journal.confirm from this preview.

No existing Cyber City machine, MQTT behavior, OTA policy or device boot path is modified.

Host test: python -m unittest discover -s firmware/cybercity/tools -p 'test_firmware_health_gates.py'
