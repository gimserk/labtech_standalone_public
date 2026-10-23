# TEKCON NFC shared-workstation account switching

An already-authenticated LabTech browser visiting the TEKCON NFC badge login
is redirected to an explicit **Workshop session in use** screen, rather than
silently replacing the logged-in student's account.

Use the **Sign out and scan next badge** POST/CSRF button to end the previous
session before accepting a new participant. The page includes no-cache
response headers; ordinary LabTech login is still available when the TEKCON
integration is disabled. The original 20-minute session expiration remains.

This prevents *accidental* account switching, not all kiosk risks. Staff must
still close sensitive tabs and verify browser profiles/cookies after events.
Physical HID-reader testing and full integration tests remain outstanding.

Test: `python manage.py test app.test_tekcon_nfc_session`.
