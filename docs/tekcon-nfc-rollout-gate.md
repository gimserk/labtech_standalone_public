# TEKCON NFC rollout gate

Both repository branches must deploy as a coordinated pair.

## TEKCON deployment
- Backup database.
- Set protected TEKCON_LABTECH_SHARED_SECRET (32+ random characters).
- Configure correct proxy SSL headers so Django's request.is_secure() reports HTTPS.
- Apply migrations, including 0022 canonical NFC index. Historical ambiguous UIDs remain unindexed and cannot log in; registration staff must correct them.
- Run: python manage.py check
- Run: python manage.py test competitions.test_labtech_bridge competitions.test_labtech_badge_index
- Verify badge reassignment workflow updates canonical_card_uid; bulk queryset updates are not supported by the model save hook.

## LabTech deployment
- Backup database. Apply migrations through 0026.
- Set matching LABTECH_TEKCON_SHARED_SECRET in the app service environment, not the browser.
- Set TEKCON NFC to DISABLED until tests pass.
- Run: python manage.py check
- Run: python manage.py test app.test_tekcon_nfc_auth app.test_tekcon_nfc_session app.test_tekcon_nfc_diagnostics app.test_tekcon_nfc_scoped_ctf app.test_tekcon_nfc_scoped_workshop app.test_tekcon_nfc_integration
- Set a properly verified HTTPS TEKCON origin. No HTTP or skip-verify.
- Enable only for supervised low-risk workshop/CTF accounts. Select ONE target course or public CTF; if both configured, CTF takes priority.
- In Django Admin, use the read-only badge diagnostic; then test browser sign-in, repeat tap, logout, and unauthorized badge.
- Confirm assigned participant cannot access unrelated private/sensitive LabTech resources. This must be manually verified since these end-to-end tests only verify membership creation, not every course/lab authorization middleware.
- Enable on a trial workstation before broader rollout; disable immediately if anomalous sessions are observed.

## Limitations
UID-only NFC tags are clonable and insufficient for privileged authentication.
No physical reader test or live Django database test was executed by the assistant.
