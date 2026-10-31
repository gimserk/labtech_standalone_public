# Supervised real Cyber City QEMU → MQTT exercise

This is **real infrastructure communication**, not a mock or simulation. It polls an actual Cyber City VM through Proxmox QEMU Guest Agent, evaluates stored monitor conditions, queues configured trigger commands and attempts real MQTT delivery for the same city. A physical ESP32 may actuate when conditions change.

## Safety and setup

Use an authorized disposable VM and one nonhazardous ESP32 building. Check its monitor trigger mapping and pin actions first. Disable/clear unrelated pending commands in the city; this command deliberately also processes existing pending commands in the **same** city, not only newly triggered ones. Production city configuration and MQTT permissions must already work.

Existing `CYBERCITY_QGA_MONITORING_ENABLED` setting must be enabled, VM must be running and `monitor_enabled=True`. The first QEMU observation establishes baseline and intentionally will not trigger physical outputs. Change the monitored VM **after** baseline and run another cycle.

Before execution, inspect pending commands and relevant device state in the live SOC dashboard. Run from the existing LabTech Python environment (no reinstall):

```bash
python manage.py run_cybercity_live_cycle --machine-id YOUR_VM_ID --execute --dispatch-limit 10
```

**No automatic changes to production or service installation occur with this PR.** The command requires an explicit `--execute` flag and city-scopes both MQTT queue selection and stale-command recovery. It does not itself verify MQTT broker acceptance, ESP32 acknowledgment, or hardware motion; inspect persisted command status `published` versus `executed` and physical state in the live SOC. The separate report-listener service must be running with valid versioned firmware and per-device broker ACLs for command acknowledgments.

If the firmware generator has not yet been validated, do not enable versioned commands on production ESP32 devices. This PR deliberately does not replace any firmware.
