# Phase 5C — Private Evidence Uploads and Instructor-Reviewed Verification Planning

## Evidence workflow

From **CTF Mission Control → Challenge Bank → Edit Template**, the instructor can upload **one private binary evidence file** of type PNG, JPEG, PDF, PCAP, or PCAPNG (maximum 10 MiB). The application rejects mismatched magic headers and disallowed extensions. Stored evidence uses the existing `CTFPrivateStorage` outside public media.

The original template's evidence is never publicly linked. On **Add to Competition**, LabTech creates an independent private copy, releases it only through the existing authenticated CTF evidence download view, and keeps the new competition challenge **hidden** for instructor review. If there is no binary file, the existing `artifact_text` field is materialized as a separate private `.txt` attachment. **One** student attachment per challenge is supported; when both are configured, binary evidence takes precedence. Changes to the bank do not mutate previously copied competition evidence. Binary files do not appear in CSV/JSON exports and are not sent to EagleAI.

Notes: File headers are an initial safety filter, not a malware scanner. Use trusted classroom evidence, keep the server's private-storage directory protected, and consider additional malware scanning before enabling arbitrary submissions beyond trusted instructors.

## AI-assisted verification plan workflow

On a saved challenge template, select **Generate AI Verification Plan**. Choose either:

- A **real LabTech lab step** from one of your instructor-assigned courses which has active guest-agent checks, or
- An existing **Cyber City SOC incident ticket**, with its current assigned city/team.

EagleAI receives the challenge title, a bounded scenario excerpt, resource **display name**, and optional short instructor notes. It does **not** receive uploaded evidence bytes, stored solution, flags, credentials, private logs, VM configurations, or SOC alert payloads.

The AI returns an advisory checklist: objective, prerequisites, validation steps, success criteria, student instructions, and instructor notes. LabTech validates structured JSON and displays a private review page. Nothing is saved until the instructor explicitly approves. Approved plans are stored on the instructor's **Challenge Bank template only**; they are excluded from portable exports and never copied into student-visible challenges.

**Critical:** Selecting a source for an advisory plan does *not* automatically bind it as a live scoring requirement. Instructors must separately configure the verified lab step or SOC evidence gate in an authorized competition challenge and test it with a real student lab/SOC session. Neither AI generation nor approval executes infrastructure commands, reconfigures QEMU, changes Wazuh/Checkmk, modifies ticket states, or releases a CTF challenge.

## Deployment

Phase 5C adds migration `0079_ctf_private_artifact_verification_plan`, after Phase 5A `0078`. Run Phase 5C tests and the pre-existing CTF suite, validate private storage permission/download behavior and review the ongoing earlier CI failures before production deployment.
