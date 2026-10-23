# Read-only ESP32 OTA supervisor preview

This preview consumes the existing explicit approval record from
`ota_activation.prepare_activation(..., approve=True)`, validates its
versioned staging directory, checks that all firmware paths are safe and
verifies SHA-256 digests again. It returns a **decision for inspection only**:

- `current`: no candidate, malformed record or verification failure.
- `candidate-verified`: validated staged candidate, but **not executed**.

Run manually from the device REPL:
```python
import ota_supervisor_preview
print(ota_supervisor_preview.inspect_pending())
```

No `boot.py` or active `main.py` is changed and no candidate is imported.
This is not an A/B boot loader, rollback engine, or automatic update system.

Before enabling candidate execution, design and hardware-test protected
application slots, persistent boot attempts, confirmation after health
checks, transaction-safe promotion and recovery following power loss.
Validate the actual MicroPython HTTPS and MQTT TLS trust behavior too.

Host test command:
```bash
python -m unittest discover -s firmware/cybercity/tools -p 'test_*.py'
```
