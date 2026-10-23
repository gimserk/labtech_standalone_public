# ESP32 firmware staging guardrails (pre-activation)

This increment adds `ota_staging.py` and offline regression tests.
It does **not** replace the existing `secure_stage.py` download code,
change Django firmware records, or enable automatic installation.

The helper validates an authenticated manifest's filenames, hashes and
HTTPS URLs before creating a staging area. It supports `main.py` and
simple `lib/*.py` paths, forbids traversal, duplicates and hidden paths,
and checks the SHA-256 of a temporary file before renaming it into a
**new** staging destination.

Run host tests:
```bash
python -m unittest discover -s firmware/cybercity/tools -p 'test_*.py'
```

## Important outstanding work

- Wire staged verification into the actual MicroPython download flow.
- Validate the server's HTTPS certificate on the actual ESP32.
- Bound file size and total space, stream files rather than buffer in RAM.
- Build an activation manifest and last-known-good recovery that survives
  reset or power failure. No bootloader or boot-time logic is changed here.
- Reconcile existing active firmware versions with device application
  versions and ensure installation cannot overwrite bootstrap credentials.
- Test failure injection and recovery on an actual board.

Do not use this module alone as evidence of a safe OTA updater.
