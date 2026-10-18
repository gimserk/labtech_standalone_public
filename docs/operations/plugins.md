# Licensed connector operations

The native installer provisions a separate `labtech-plugin` service identity, root-owned release storage under `/var/lib/labtech/plugins`, credentials under `/etc/labtech/plugins`, a local socket directory under `/run/labtech/plugins`, and `labtech-plugin-install.timer`. It preserves installed releases and tokens on reruns. Plugin code runs through `labtech-plugin@<id>.service`, not the Django web process. The installer copies the restricted socket runner and a root-owned snapshot of the helper's Python code and dependencies into `/usr/local/lib/labtech/`; the root timer never executes code from the service-user-writable checkout.

## Configure the Marketplace

The signed license must include `plugins_marketplace_enabled: true`, match this machine, and be current. The official licensing administrator enables the entitlement on this machine record and sets a unique random client secret. Enter that 32–512 character secret at the native installer's `PLUGIN_MARKETPLACE_CLIENT_SECRET` prompt and renew the license. The standalone sends it only in its HTTPS license renewal request; the server stores a hash. A missing or wrong secret produces a normal core license without plugin access. Supply the official Ed25519 publisher **public** key file at the installer prompt; this is distinct from `LICENSE_SERVER_PUBLIC_KEY`. `PLUGIN_MARKETPLACE_URL` is an HTTPS origin, defaulting to `https://www.wyocyberrange.com`. The helper refuses new installations when the publisher key is absent. Removing a key from the installer configuration disables new installations; do not remove it during an in-progress job. Rotate the public key after the Marketplace service has published a compatible signed release and the current jobs finish; stage any old and new trust transition with the service operator.

The official Marketplace catalog and download API is a separate service. Until it exposes the documented endpoints in `docs/integrations/plugin-marketplace-api.md`, the admin page will show an unavailable message. A local fixture can exercise the client and verifier but does not prove the remote service exists.

## Inspect and recover

```bash
PLUGIN_ID=demo
KNOWN_GOOD_VERSION=1.0.0
sudo systemctl status labtech-plugin-install.timer labtech-plugin-install.service
sudo journalctl -u labtech-plugin-install.service -n 100 --no-pager
sudo systemctl list-units 'labtech-plugin@*.service' --all
sudo ls -l "/var/lib/labtech/plugins/$PLUGIN_ID/current"
```

Each install is a durable `PluginInstallJob` visible in the administrator's Plugin Marketplace. The helper retries only queued jobs, takes a per-plugin lock, verifies signed metadata and exact archive bytes, stages wheels in a separate virtual environment, swaps the symlink, restarts the restricted service, and waits briefly for health. A failed health check restores the previous symlink and service. The timer marks a job interrupted for more than 21 minutes as failed and restores its recorded prior target where possible; inspect any recovery warning before retrying from the admin page. A failed job remains failed so a new administrator POST can create a new request. Do not delete the release directory or token to retry. Disabled connectors have a separate Re-enable action, which verifies the entitlement, release, and health before restoring availability.

The timer polls at most ten queued numeric database job IDs per run. This replaces the planned service-user-writable spool handoff; it keeps the request data in the database and avoids an extra file path in the privileged interface.

To inspect job records from the installed checkout:

```bash
cd /opt/labtech
sudo -u labtech env DJANGO_SETTINGS_MODULE=deployment_settings PYTHONPATH=/etc/labtech:/opt/labtech /opt/labtech/venv/bin/python manage.py shell -c 'from app.plugin_models import PluginInstallJob; print(list(PluginInstallJob.objects.order_by("-id").values("id", "plugin_id", "release_id", "status", "error")[:20]))'
```

To start the queued-job check after fixing the cause:

```bash
sudo systemctl start labtech-plugin-install.service
```

For an explicit rollback to a known healthy version, first stop the connector instance, then change its root-owned symlink and restart it. Keep all other services running:

```bash
PLUGIN_ID=demo
KNOWN_GOOD_VERSION=1.0.0
sudo systemctl stop "labtech-plugin@$PLUGIN_ID.service"
sudo ln -s "releases/$KNOWN_GOOD_VERSION" "/var/lib/labtech/plugins/$PLUGIN_ID/.rollback-current"
sudo mv -Tf "/var/lib/labtech/plugins/$PLUGIN_ID/.rollback-current" "/var/lib/labtech/plugins/$PLUGIN_ID/current"
sudo systemctl start "labtech-plugin@$PLUGIN_ID.service"
```

The database's `InstalledConnector` version also needs reconciliation after a manual rollback; use a new signed Marketplace install request for that version. The symlink command alone is for immediate service recovery.

The signed entitlement allows an installed connector to run during the first 30 days after expiry. Catalog and new installations require an active entitlement. After grace, the timer stops connector services and the core refuses connector calls; the web, courses, and gradebook remain available. Revocation blocks connector calls immediately and the next timer run stops services. An administrator can disable a connector or remove its services and files after it is no longer in use.

## Limits

This foundation offers a reference health/configuration connector. External Assignment, grade ingestion, GNS3 launch, and official Marketplace server deployment are separate milestones. The socket protocol reserves operation names for those future integrations, but this runner rejects them until the corresponding core workflow is designed. All installed connectors currently share the restricted `labtech-plugin` identity; the deployment isolates them from the web and root but does not isolate one connector's credentials from another connector. The later connector isolation milestone should introduce distinct service identities before installing mutually untrusted providers.
