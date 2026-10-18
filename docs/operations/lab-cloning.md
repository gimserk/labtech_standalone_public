# Linked and full lab clones

In **Add Lab** or **Edit Lab**, use **Clone type** directly below **Lab type**.
Both **Linked Clone** and **Full Clone** are available for timed and persistent
(permanent) labs. The selection applies to all machines in that lab and stays
independent of the lab's lifetime.

- **Linked Clone:** faster provisioning and lower initial storage use. It depends
  on the source template and requires storage that supports linked clones.
- **Full Clone:** copies all disk data, takes longer to provision, and uses more
  storage. Its independence from the template can make it a better fit for
  persistent labs used over a long period. Cloning time depends on disk sizes,
  storage speed, and concurrent builds; the form does not promise a fixed time.

New labs default to Linked Clone. Migration `0021_lab_clone_type` preserves the
previous behavior for existing labs: persistent labs become Full Clone and timed
labs become Linked Clone. Existing virtual machines are not converted or rebuilt.
The chosen value is read when each machine's provisioning worker loads its lab;
finish changing lab configuration before starting a batch of builds.

Both provisioning helpers send an explicit Proxmox `full` value (`0` for linked,
`1` for full). Storage and placement requirements still apply. LabTech does not
silently switch an instructor's selected mode if a clone fails.

Course exports and copies include the choice. Imports of older packages without
`clone_type` keep the previous lifetime-based behavior; invalid values are rejected.

## Updating a server

Follow the [normal update procedure](../installation.md). This change includes a
database migration, so apply migrations before restarting the web and Celery
worker services with the updated code. Allow active provisioning work to finish
before updating. No new dependencies or environment variables are required.

## Verification

```bash
python manage.py test app.test_lab_clone_type app.test_lab_clone_migration --settings=app.test_settings
python manage.py test app --top-level-directory . --settings=app.test_settings
python manage.py makemigrations --check --dry-run --settings=app.test_settings
```

Tests cover form choices, saving/editing both lab types, permissions, explicit
Proxmox request parameters in both build helpers, package round trips and legacy
imports, and the database upgrade. Provider calls are mocked; a live Proxmox
smoke test should use a small template on the deployment's actual storage.

Proxmox describes the template dependency and storage differences in
[VM Templates and Clones](https://pve.proxmox.com/wiki/VM_Templates_and_Clones).
