import os
import requests

secret = os.environ.get("LABTECH_TEKCON_SHARED_SECRET", "")
uid = input("Enter registered badge UID: ").strip()

if len(secret) < 32:
    print("Secret not available in this shell.")
    print("The Gunicorn service may still have it configured.")
else:
    r = requests.post(
        "https://lccctekcon.com/api/integrations/labtech/badge-identity/",
        json={"card_uid": uid},
        headers={"X-LabTech-Bridge-Key": secret},
        timeout=8,
    )
    print("HTTP status:", r.status_code)
    print("Response:", r.text[:500])
