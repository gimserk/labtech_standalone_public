# ESP32 staged application activation gate

This phase adds an **approval record only**. It intentionally does NOT
install, execute, import, reboot into, or automatically roll back downloaded
firmware.

A trusted operator can invoke:

```python
import ota_activation
ota_activation.prepare_activation(manifest, "staging-v3", approve=True)
```

The manifest must be the verified response corresponding to the previously
staged `staging-v3` folder. Before writing a pending record, the helper
validates the firmware paths and SHA-256 digests again. It rejects
overlapping pending activations. `cancel_activation()` removes the pending
record without modifying active code.

This is deliberately a preparation milestone, **not** a complete OTA
activation feature. The permanent bootstrap, credentials, and current
application remain unchanged. No boot supervisor is installed.

## Requirements before actual activation and rollback

1. Validate LabTech HTTPS certificate chains and hostname checking on the
   target ESP32 firmware and the MQTT TLS transport with real boards.
2. Use protected A/B application slots or a tested filesystem rollback
   approach. Avoid overwriting `boot.py` or provisioning credentials.
3. Have a boot supervisor capable of checking pending activation, retry
   limits, boot confirmation and last-known-good recovery on power loss.
4. Test interrupted writes, file corruption, low-storage, reboot loops,
   and physical device recovery before enabling unattended updates.
5. Run `python -m unittest discover -s firmware/cybercity/tools -p 'test_*.py'`
   and the Django suite, then manually test on actual ESP32 hardware.

The downloaded basic firmware ZIP includes `ota_activation.py`, but
nothing invokes it automatically.
