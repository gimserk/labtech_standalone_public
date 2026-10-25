# Cyber City ESP32 recovery preflight (PR #90)

This phase adds **manual, opt-in recovery primitives**. It does not install a
boot.py hook, reset the device, implement automatic rollback or enable
unattended OTA. Existing LabTech Cyber City VMs, MQTT controls and firmware
polling configuration are unchanged.

## Why cautious staging is necessary

The existing single-file OTA installer saves the previous application as
`main.py.ota-backup` before promoting the replacement. A power interruption
can occur between those renames or before version metadata is updated.
The presence of `main.py` does not prove that its code booted successfully.
A failed application can keep restarting; an automatically enabled supervisor
must have a separate known-good boot path, retry bounds and verified health
conditions that are tested on the specific MicroPython firmware build.

## Controlled test sequence (isolated development board only)

1. Verify USB/REPL rescue access and copy `main.py`, its OTA backup, and
   `ota-installed-version.json` off the device. Do not expose device keys.
2. Import `boot_recovery` via REPL and call `inspect_boot_files()`.
3. Only when main.py is missing **and** the backup exists, call
   `restore_missing_app(approve=True)`. A restart is still required.
4. Validate GPIO safe startup, MQTT reconnect, and LabTech device reporting.
5. When a new firmware has been independently verified and is stable, an
   operator may call `confirm_boot_and_release_backup(approve=True,
   healthy=True)`. This irreversibly releases the old backup; do not invoke
   merely because the app file exists.
6. Reconcile `ota-installed-version.json` with the actual running app before
   the next OTA attempt; restoring the backup alone does not update metadata.

## Future automatic supervisor acceptance gates

- Boot from a protected immutable entry point, not the candidate application.
- Persist bounded attempts and candidate identity across resets.
- Confirm health from the running candidate within a timeout; do not treat
  imports, file existence or a single MQTT connect as sufficient.
- Restore a known-good version without overwriting provisioning/credentials.
- Verify behavior across crashes, power cuts, low flash capacity and corrupt
  metadata on physical hardware.
- Keep automatic installation disabled until all these gates pass.

Run host-side pure-Python tests with:
`python -m unittest discover -s firmware/cybercity/tools -p 'test_boot_recovery.py'`
