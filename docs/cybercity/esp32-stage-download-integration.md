# ESP32 OTA stage integration — no automatic activation

This change connects `secure_stage.py` to the existing v2 manifest and
`ota_staging.py` validation. The city ZIP now includes both modules.

`secure_stage.stage_files()`:
1. Uses the registered ESP32 Wi-Fi MAC and configured bearer key.
2. Retrieves the currently active firmware manifest from LabTech HTTPS.
3. Validates path names, duplicate entries, SHA-256 digests and download URLs.
4. Requires download URLs to stay under the same LabTech API origin.
5. Downloads in 4 KiB chunks; limits each file to 256 KiB and total to 1 MiB.
6. Stages `main.py` and allowed `lib/*.py` under a fresh
   `staging-v<version>` directory.
7. Verifies the SHA-256 digest before renaming a temporary part file into its
   staging location.

This does **not** write to the live `main.py`, change `boot.py`, install
libraries into the active `lib/`, or execute downloaded code.

## Verification before use

- Confirm the exact ESP32 MicroPython HTTPS client validates the LabTech
  certificate chain and hostname, including invalid certificate rejection.
- Confirm that the device's `urequests` supports `stream=True` and
  `response.raw.read(n)`. Its behavior varies by firmware and package.
- Validate ESP32 flash capacity and test interrupted downloads. A failed
  stage can leave a partially populated versioned directory, which must be
  removed manually before retrying the same version.
- Do not install over an existing application or enable unattended OTA until
  activation, durable metadata, boot confirmation and rollback have tests.
- Firmware manifest size limits are currently enforced by the ESP32 client,
  not at the upload endpoint; server-side constraints are still needed.
