# QEMU guest-agent checks

LabTech can validate work inside individual student Linux and Windows VMs. Students run checks with **Check Work** and can review their progress. **Finish Lab** starts cleanup for timed labs even if checks are incomplete, so students can end a session and restart after cleanup. Persistent labs can only be ended by an instructor. Checks do not award grades.

## Prepare each VM template

1. Enable the **QEMU Guest Agent** option on the Proxmox VM template and install/start the `qemu-guest-agent` service inside Linux. For Windows, install the QEMU Guest Agent from the VirtIO guest tools and ensure its service runs. Boot a clone and confirm the Proxmox guest-agent `ping`/`info` command works before enabling checks.
2. In LabTech, open **Manage Machines** for the lab and explicitly classify each checked machine as **Linux** or **Windows**. Existing rows are left unclassified by the migration; a check cannot be saved until the machine is classified.
3. Ensure the guest account and platform tools needed by the selected check exist. Linux probes use `test`, `head`, `systemctl`, `id`, `getent`, `dpkg-query`, `rpm`, `apk`, `pgrep`, and `ss` where appropriate. Windows probes use built-in PowerShell cmdlets. Grant the guest agent sufficient guest-side permissions for these probes.
4. Start the instructor's own lab instance before **Test on My Lab**. Preview never executes on a shared Proxmox template or another user's instance.

## Configure deployment

Set `LAB_CHECK_SECRET_KEY` to a dedicated Fernet key before saving file-content checks. Generate one with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Back it up securely and keep it stable: changing it makes encrypted expected text unreadable. Never commit the key or use the Django signing key in its place.

| Environment variable | Default | Purpose |
| --- | ---: | --- |
| `LAB_CHECK_STEP_COOLDOWN` | 10 seconds | Minimum time between a student's attempts on one step. |
| `LAB_CHECK_COMMAND_TIMEOUT` | 5 seconds | Guest-agent command deadline. |
| `LAB_CHECK_RUN_DEADLINE` | 45 seconds | Whole validation deadline. |
| `LAB_CHECK_MAX_OUTPUT_BYTES` | 65,536 | Maximum returned stdout or stderr per command. |
| `LAB_CHECK_MAX_FILE_BYTES` | 65,536 | Largest text file content inspected. |
| `LAB_CHECK_LEASE_SECONDS` | 60 seconds | Recovery interval for a lost validation worker. |

The web server and proxy must allow validation requests to remain open for at least the run deadline. Lower limits are supported. The application caps raised limits to finite bounds. Run `python manage.py migrate` and `python manage.py check --deploy` during rollout. A missing or unusable key for stored secret checks is `labchecks.E001`; a removed registered type is `labchecks.E003`. Repair the key or catalog before enabling the affected checks.

## Instructor workflow

Go to **Manage Steps → VM Checks**, select the machine and type, configure the typed fields, add a student-facing label and hint, then save. Reorder, activate, deactivate, or soft-remove checks from the step list. Secrets are write-only; leave the expected text blank on edit to keep its value. A change to execution settings or private expected text invalidates previous passes. Test on My Lab uses the current instructor instance. Attempt history is filtered by student, step, outcome, and context and contains only sanitized result codes.

## Failure meanings

| Outcome | Operator action |
| --- | --- |
| `fail` | The VM answered and its state differs from the requirement; review the public hint. |
| `infrastructure_error` | Confirm VM is running, QEMU agent is installed/enabled, Proxmox API access, guest command availability, timeout and output caps; retry. This never counts as student failure. |
| `configuration_error` | Inspect OS classification and the saved check, then re-save valid fields or restore the encryption key. |
| `abandoned` | A worker stopped or lease expired; retry after the lease deadline. |

Commands and scripts are selected by application code. Instructors cannot supply arbitrary shell commands, PowerShell source, executable paths, or command templates. Raw output, credentials, and decrypted expected values are excluded from normal responses and attempt history. Automatic scoring and archival are not part of this release.
