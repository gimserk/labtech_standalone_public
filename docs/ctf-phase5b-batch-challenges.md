# Phase 5B — Resumable AI Challenge Batches

From **CTF Mission Control → Challenge Bank → Generate AI Batch** an instructor prepares **2–5 specific technical challenge topics** and shared assessment settings (category, collection, difficulty, points, and environment).

Generation is deliberately **one topic per button press**, using the already configured LabTech AIClient/EagleAI streaming transport and Phase 5A challenge schema. This reduces 504 gateway risks for batches and keeps successful drafts intact when a later request fails.

The UI shows each independent draft's student story, separate text evidence, technical solution, tags and hints. The instructor must independently verify accuracy, enter a final flag, and approve each item. Approval hashes the flag and creates **one private Challenge Bank template**, not a published challenge. Unapproved drafts remain in the instructor session for 30 minutes; instructors can discard individual drafts or close the batch without deleting already saved templates.

No Proxmox, Cyber City, Wazuh or Checkmk resources are provisioned or modified; the generator is purely an authoring workflow. Current Phase 5B supports a textual evidence artifact like logs/configuration/packet metadata, not binary media; multimedia artifact creation and verified lab/SOC check plans are follow-ups.

Deployment: **no new database migration** beyond Phase 5A migration `0078`. Run Phase 5B regression tests plus Phase 5A tests, and confirm the AI gateway and challenge copying work in development before production. Existing broader regression failures from prior phases still require triage.
