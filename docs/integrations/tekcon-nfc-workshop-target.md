# TEKCON NFC workshop check-in

The TEKCON NFC settings include a Target course dropdown in Django Admin. Following successful badge login, LabTech enrolls that participant only in the selected active, non-archived course and opens its course detail page. Enrollment is idempotent.

If a target CTF is selected, it takes priority and workshop enrollment does not occur. With no eligible target, normal login redirects home. The browser cannot select a course. Reserve this feature for supervised low-risk workshops because NFC UIDs are clonable.

Deploy with `python manage.py migrate`. Run `python manage.py test app.test_tekcon_nfc_scoped_workshop`. End-to-end tests with a USB reader and LabTech permissions remain outstanding.
