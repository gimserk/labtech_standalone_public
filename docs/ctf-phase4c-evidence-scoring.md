# CTF Phase 4C — Verified Evidence Scoring

CTF authors can choose one of two scoring methods for each challenge:

1. **Submit a flag** (default; unchanged).
2. **Verify live evidence (no flag)**. The learner chooses **Verify & Claim Points** from the challenge board. LabTech verifies all configured real QEMU Guest Agent step checks and/or the assigned SOC incident with qualifying real Wazuh/Checkmk evidence, then awards points through the existing CTF submission ledger. No instructor-issued flag is required.

## Instructor setup

- Create or edit a CTF challenge and select *Verify live evidence (no flag)*.
- Configure **at least one** of: a linked LabTech lab with a valid verification step containing active VM checks; or an assigned real SOC incident ticket plus Wazuh/Checkmk evidence type.
- If both are configured, *both* must pass. Missing or misconfigured verification requirements fail closed.
- Readiness checks distinguish evidence-scored challenges from flag challenges; no flag is required for evidence scoring.
- Publish the challenge when ready. You can mix scoring modes within a single competition.
- **Automatic awards also occur after attributable student actions:** after their own active VM step check completes with a passing result, or when they personally move an assigned real SOC incident ticket into resolved/closed status. If evidence is collected or associated later, the student may use **Verify & Claim Points** to recheck. Background ingestion without an attributable student action never silently scores another analyst's work.

## Scoring protections

- The existing CTFSubmission unique constraints and challenge row lock prevent duplicate solo or team awards.
- The existing participant/course eligibility, team requirement, release visibility, event time window, and submission pause restrictions apply unchanged.
- Each student must independently satisfy their configured verification prerequisites; SOC team membership is separate from CTF team membership.
- Hint costs are deducted exactly as for manual flag solves, with a minimum zero award.
- `CTFSubmission.scoring_source` records `flag` or `evidence`. Historical submissions default to `flag`; no existing score is rewritten.
- Automatic evidence claim requests never accept a flag and never call Wazuh/Checkmk directly, invoke Proxmox/QEMU, or run new shell commands. They only inspect validated evidence already present in LabTech.
- The traditional flag endpoint explicitly rejects evidence-scored challenges to prevent scoring bypasses.

## Database and rollout

Additive migration `0077_ctf_evidence_scoring` depends on `0076_ctf_soc_ticket_evidence`. Development testing must verify mixed modes, both source types, team claims, paused competitions and replay attempts before production deployment.

## Future work

Background ingestion-only scoring (such as an alert arriving without a student action) remains intentionally excluded: its participant attribution is ambiguous. The existing student-triggered VM-check and SOC-ticket transition hooks are supported with the exact same unique ledger writer as manual claims.
