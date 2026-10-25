# Cyber City Milestone 1 — validation and staging release gate

This package fixes a QEMU Guest Agent collector parsing issue and adds negative-response tests. It does not enable physical building actions automatically.

## Developer verification

Run in a dedicated Django development environment with its own test database:

```bash
python -m compileall -q app/cybercity_qga_collector.py app/test_cybercity_qga_parser_hardening.py
python manage.py check
python manage.py test app.test_cybercity_qga_collector app.test_cybercity_qga_parser_hardening app.test_cybercity_m1_db_dispatch app.test_cybercity_m1_chain app.test_cybercity_qga_poll app.test_cybercity_qga_enrollment
```

Record test command, exit code, environment, and any failures. **A merged test is not evidence of passing tests.**

## Staging live chain — one building

1. In staging, use the existing building CyberCityMachine, not a separate student lab VM. Verify it is running and has QEMU Guest Agent enabled on the Proxmox template and clone.
2. In LabTech, configure one service-status monitor and matching single-building ESP32 pin action.
3. Run `python manage.py poll_cybercity_qga --machine-id <LABTECH_MACHINE_ID> --os-family linux` in read-only/dry-run mode.
4. With `CYBERCITY_QGA_MONITORING_ENABLED=True` in isolated staging, use `--apply` and verify the database records exactly one pending CyberCityCommand after a service transition.
5. Run the already implemented `python manage.py dispatch_cybercity_commands` against the disposable localhost broker and simulator. Observe command topic, JSON envelope, published state and device ACK.
6. Verify duplicate suppression on repeated polls, and monitor rearm on a nonmatching state. Test QGA timeout and MQTT broker outage.
7. Connect one physical ESP32 to a staged ACL-restricted Control VM MQTT broker and repeat. Confirm actual GPIO change, correlated ACK, device status, and LabTech building UI.

The staging team must separately record all gates: Django tests, QGA collection, real broker dispatch, physical output and UI. Do not claim production ready or milestone complete until each gate is observed.

## Safety cautions

- QGA `guest-exec` runs software inside the guest and is privileged. Restrict Proxmox credentials and monitor targets to trusted instructors.
- On Windows, the current collector parses English `sc.exe query` output; non-English guests require a locale-independent collector.
- QGA guest-exec timeouts may leave a guest command executing briefly. Only bounded, read-only checks are allowed.
- Do not schedule a new timer until systemd paths, Redis-backed lock, MQTT TLS and dispatcher scheduler are verified.
