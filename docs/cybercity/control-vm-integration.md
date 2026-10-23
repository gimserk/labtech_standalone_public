# Control VM: integration plan against existing Cyber City

## Confirmed implementation points (main branch)

- `CyberCity` in `app/models.py`: pfSense and Management have
  `*_vm_template`, `*_vmid`, `*_vnc_port`, `*_status` fields.
- `CyberCityForm` in `app/forms.py` includes both templates, and
  restricts non-superusers from changing templates.
- `cybercity_utility_machine_action_view` in `app/views.py`
  handles creation, startup, stop, VM deletion and VNC allocation.
- `cybercity_guacamole_sso_redirect_view` handles city-wide utility consoles.
- `cybercity_detail.html` displays city utility controls and broker status.
- `CyberCity.mqtt_broker_address` / port / username / password already
  configure the broker connection for MQTT attacks and pin status reads.
- Attack commands use `<building base>/<pin subtopic>/command`;
  status reads use `<building base>/<pin subtopic>/status`.

## Planned minimal Control extension

1. Add nullable `control_vm_template`, `control_vmid`,
   `control_vnc_port`, and `control_status` to `CyberCity`, with an
   additive migration. Keep existing Firewall and Management data intact.
2. Include Control template in `CyberCityForm` with matching queryset and
   administrator restrictions.
3. Add a `control` branch to the *existing* utility-machine action view,
   reusing cloning, VNC allocation, start, stop and cleanup.
4. Add `control` to the *existing* city utility Guacamole redirect,
   reusing its Proxmox host and Guacamole configuration lookup.
5. Add a Control card in the existing `cybercity_detail.html` City
   Services section; add no separate dashboard.
6. The Control VM image/template will contain Mosquitto (or the selected
   broker) and must be configured to expose its reachable broker hostname/IP.
   LabTech's existing broker address field remains the source of truth.
   Starting the VM does not by itself prove the broker is ready.
7. Add tests: city form field visibility; Control lifecycle; console
   authorization; startup failure cleanup; reachable MQTT broker status.

## Identified existing behaviors needing separate investigation

- Guacamole utility JWTs are constructed from VM VNC ports. Verify the
  Guacamole connection to the correct Proxmox server before changing JWT flow.
- Building-machine console permissions are currently staff-only.
- Firmware check and configuration endpoints accept MAC alone. Do not
  deploy unauthenticated executable OTA or expose MQTT passwords through
  these endpoints to untrusted clients.
- Building status endpoint temporarily subscribes to MQTT every request;
  a persistent service on the Control VM could later improve telemetry.

## Scope boundary

No automatic MQTT installation or Proxmox provisioning changes have been
attempted in this plan alone. The Control VM template, schema migration,
runtime tests, and connectivity checks remain required before merge.
