# Dedicated LabTech VNC TCP port range (6000–6999)

LabTech's Proxmox server connections default to **TCP 6000–6999** for
direct QEMU VNC access through Guacamole, providing 1,000 port allocations
per configured ProxmoxServer record. The allocator remains cluster-wide, not
per-node. This change does not increase the number of VMIDs available.

## Applying the update

Deploy the application and run `python manage.py migrate` before new
provisioning begins. Migration `0033_proxmox_vnc_port_range` updates only
existing ProxmoxServer connections whose VNC range is **exactly**
5900–5999. Custom port ranges remain unchanged.

Existing `AllocatedVNCPort` reservations and running VM configurations are
**not deleted or reassigned**. Older sessions continue to use their original
ports until their usual cleanup completes. For a custom-configured server,
edit the range through **Manage Proxmox Servers → Edit** (both VNC start
and VNC end are now visible).

Check the applied range with:

```bash
python manage.py shell -c "from app.models import ProxmoxServer; print(list(ProxmoxServer.objects.values_list('name', 'vnc_port_start', 'vnc_port_end')))"
```

Run focused tests before deployment:

```bash
python manage.py test app.test_vnc_port_range --settings=app.test_settings
python manage.py makemigrations --check --dry-run --settings=app.test_settings
```

## Network requirements and cautions

* Permit TCP 6000–6999 **only from the Guacamole server** to each
  Proxmox node that may run LabTech machines. Do not expose these raw VNC
  endpoints to the public internet.
* Validate that these ports are free of other services on every eligible node.
  They are TCP listener ports, not automatically opened or reserved by Proxmox.
* LabTech uses QEMU `-vnc 0.0.0.0:<display>`, with `display = port - 5900`.
  Port 6000 maps to VNC display 100, and 6999 maps to display 1099.
* Changing the port range does **not** repair failed cleanup jobs or solve
  Proxmox cross-node cloning failures involving local storage. Retry affected
  cleanup jobs after fixing their underlying resource issue.

The migration's reverse step intentionally does not revert existing server
configuration, as that could make active allocations inaccessible.
