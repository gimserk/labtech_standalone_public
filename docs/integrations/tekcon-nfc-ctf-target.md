# TEKCON NFC scoped CTF check-in

The existing optional TEKCON USB NFC authentication settings now include
`target_ctf`, a nullable foreign key to a LabTech CTF campaign.

If a LabTech administrator selects a **public** CTF, a successful badge
login enrolls that participant in only the selected CTF and redirects to
its detail page. A repeated badge login is idempotent via
`CTFParticipant.objects.get_or_create()`.

When no target is configured, or the selected campaign is not public,
login uses the ordinary LabTech home page. A URL query or browser input
cannot select the enrollment target; it is server-side configuration.

CTF enrollment does not confer elevated user roles or course access.
Do not use UID-only badge auth for sensitive/privileged labs. The existing
20-minute shared-workstation session expiry remains in effect.

Deploy with `python manage.py migrate`. Staff can select the target
from Django Admin > Tekcon NFC configurations.

Host-side and USB hardware end-to-end tests are still needed.
