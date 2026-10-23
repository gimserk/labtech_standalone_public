# TEKCON NFC administrator diagnostics

In LabTech Django Admin > Tekcon NFC configurations > open the configuration,
select **Test TEKCON connection / badge**. Scan a test badge on a USB
keyboard-emulation reader or enter its UID. The form calls TEKCON's existing
server-authenticated badge identity endpoint using the configured HTTPS origin
and protected shared secret. It does NOT create accounts, sessions, CTF
participants, enrollments, or XP awards.

This test confirms HTTPS connectivity and recognition for one badge.
It does not independently measure DNS/TLS or validate production readiness;
certificate errors, timeouts and authentication failures display a generic
failure message. Keep the reader and test session in a staff-only area.
The test requires NFC login to be enabled; disable it again after testing
if attendee access is not yet authorized.

Run `python manage.py test app.test_tekcon_nfc_diagnostics` after deployment.
