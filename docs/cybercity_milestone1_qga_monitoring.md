# Milestone 1 — QEMU Guest Agent is the Cyber City monitoring transport

**Architecture decision:** Every building machine is the existing `CyberCityMachine` already listed under its building. LabTech polls it using Proxmox QEMU Guest Agent. No independent Python/PowerShell monitoring daemon or separate student lab VM is required.

```text
Existing building CyberCityMachine (linked clone)
  -> Proxmox QEMU Guest Agent API (trusted server-side credentials)
  -> LabTech scheduled monitor evaluation
  -> edge-triggered durable CyberCityCommand outbox
  -> city's Control VM MQTT broker
  -> same building's ESP32 GPIO
  -> MQTT status/ACK consumer and Cyber City instructor UI
```

This PR defines the **fail-closed machine target and observation contract** for the future QGA poller; it does not yet connect to Proxmox or schedule polls. Only running QEMU clones whose VMIDs differ from the source template may be read. Only configured active monitor IDs on that same building machine may contribute observations. Agent failures are errors/missing observations, not forced `False` values that rearm a monitor.

For service checks and file hashes, implement a bounded allowlisted QGA `guest-exec` collector with explicit Windows/Linux argument vectors, strict output limits, command timeout, Proxmox task status checks, and no user-supplied shell interpolation. Do not directly execute arbitrary SQL from `MachineStateMonitor.target` under privileged guest-agent credentials: database query monitors need a constrained dedicated read-only protocol or additional security design.

The existing `api_report_machine_state` supports authenticated agent-pushed observations; the QGA poller should share its **edge detection + outbox** service rather than calling its HTTP endpoint with a VM credential or duplicating logic. Move the state transition logic into a common service in the next PR, then bind the QGA poller to it.

## Verification

Run `python manage.py test app.test_cybercity_qga_monitoring` in a configured development environment. Follow with a real QGA inspection on a **staging** building VM, then continue the MQTT simulated-ESP32 suite from PR #108. This contract test is not proof that any physical ESP32 or live Proxmox path passed.
