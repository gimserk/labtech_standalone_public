# CTF Phase 4A: Live VM-Check-Gated Challenges

This increment connects CTF scoring with existing *real* LabTech QEMU Guest Agent validations. There is no artificial simulated evidence and no second command executor.

## Instructor workflow

1. Create a LabTech lab in the competition's course, configure its VM(s), and add a step with **active VM checks**.
2. Open CTF Mission Control, edit a challenge, and select the **Linked Lab**.
3. Save, then reopen the challenge and select the **Verification Step** from the selected lab. Save and release only once the readiness check is clear.
4. The student starts their own lab, performs the remediation/investigation, and runs the normal **Check** action in the lab step.
5. On passing every active check of that step, the student can submit the correct CTF flag. The existing flag verification and scoring system remains authoritative.

For team competitions, each submitting student must personally have a current pass from their own active lab session. Teammate verification does not count for the student submitting the flag.

## Rules and safeguards

- Existing challenges without a verification step work exactly as before.
- A verification step must belong to the linked lab, and the linked lab must belong to the competition's course when one is set.
- At least one active check is required, all currently active checks on the chosen step must pass, and the evidence must belong to an unexpired active lab session owned by the submitting student.
- Result evaluation uses LabTech's existing `current_check_state` selector: it ignores instructor previews, failed/abandoned runs, removed checks, and out-of-date check revisions.
- No flag, VM credentials, or check secrets are exposed by this integration.
- This is **prerequisite gating**, not automatic CTF solving. The student still provides a flag. Automatically awarding points upon VM proof is future work requiring explicit event/team rules and idempotency review.
- This does not yet link Wazuh or Checkmk SOC alerts to the CTF. Phase 4B will address safely scoped, real SOC event proof.

## Deployment

Apply migration `0075_ctf_verified_lab_step` after `0074_ctf_challenge_bank`. Run the dedicated Phase 4A regression tests and verify a live lab with real QEMU Guest Agent checks in development before production.
