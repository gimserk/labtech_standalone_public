# TEKCON NFC pilot reliability checks

The first pre-deployment review identified a risk with generated usernames: if a LabTech account already had `tekcon_<participant_id>`, the connector might attempt account provisioning with that existing name. The login path now fails closed in that case rather than reusing or modifying the existing account. Staff must resolve the collision deliberately.

The NFC login regression test now supplies the anonymous request user expected by Django middleware, and adds a username-collision test.

Recommended smoke test on the deployed app:

```bash
python manage.py check
python manage.py test app.test_tekcon_nfc_auth app.test_tekcon_nfc_session app.test_tekcon_nfc_diagnostics app.test_tekcon_nfc_scoped_ctf app.test_tekcon_nfc_scoped_workshop
```

These tests are not a substitute for a real USB HID reader and actual TEKCON HTTPS endpoint. Keep NFC disabled until DNS/TLS/shared-secret checks, real badge scanning, repeated-user signout, and workshop/CTF authorization are tested.
