# Optional TEKCON USB NFC login in LabTech

## Architecture

A USB NFC reader attached to the workstation must support **HID keyboard
emulation**. The reader types its badge UID and Enter into the dedicated
LabTech badge login form. There is no TEKCON reader daemon, Pi, or WebUSB
dependency. Browser HTTPS/CSRF still apply.

1. In LabTech Django Admin, create the single **Tekcon NFC configuration**
   row, enter the TEKCON HTTPS server origin (DNS or HTTPS IP address),
   set `enabled=True`, and optionally `auto_create_users=True`.
2. Generate a random integration key of at least 32 characters.
   Set `LABTECH_TEKCON_SHARED_SECRET` on the LabTech server, and the
   **same value** as `TEKCON_LABTECH_SHARED_SECRET` on the TEKCON server.
   Protect these as server-side environment secrets, never in JavaScript.
3. Make sure LabTech trusts the TEKCON server certificate and hostname.
   IP addresses require a matching TLS certificate Subject Alternative Name.
   Do not disable certificate checking.
4. Deploy migrations: `python manage.py migrate`. Restart Django workers
   after installing the secret.
5. When enabled, the existing LabTech account login page shows
   **Sign in with TEKCON NFC Badge**. Or visit
   `/accounts/tekcon-nfc/` directly.
6. On first recognized badge tap, LabTech creates an unprivileged user
   `tekcon_<participant_id>` and a stable `TekconIdentityLink`
   unless auto creation is disabled. It never merges by name or email.
   Existing users with linked TEKCON identities can be reused.
7. LabTech creates an ordinary Django session that expires after twenty
   minutes; the workstation operator must sign out between attendees.
   Workshop/CTF enrollment is **not automatic** in this phase.

## Security boundaries

TEKCON is the source of badge identity. LabTech controls what the resulting
limited account can access. TEKCON does not send passwords, badge identifiers
or email to LabTech in the response; only a stable participant ID and name.
The reader UID is sent over a server-to-server TLS request with a secret
configured on both servers. A server-to-server secret protects the API but
**does not prevent a cloned UID from impersonating its badge holder**.
Do not enable this for staff, privileged/sensitive accounts, or unsupervised
shared computers without a second factor and stronger NFC tags.

Configure trusted proxy HTTPS headers correctly, rate-limit the service
at your reverse proxy, restrict TEKCON integration endpoint access, and
monitor failures. LabTech's normal login remains available when disabled,
and TEKCON badge login fails closed on network errors.

## Tests

```bash
python manage.py migrate
python manage.py test app.test_tekcon_nfc_auth
```

TEKCON tests: `python manage.py test competitions.test_labtech_bridge`.
No physical USB scanner or integrated-server tests have been run yet.
