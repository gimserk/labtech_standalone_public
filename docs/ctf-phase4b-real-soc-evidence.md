# CTF Phase 4B — Real Cyber City SOC Ticket Evidence

## Instructor setup

1. Within Cyber City SOC, configure a real Wazuh agent mapping or Checkmk host mapping for an existing city machine.
2. Capture actual Wazuh detections or collect Checkmk monitoring results through the normal SOC workflows.
3. Create an incident ticket assigned to a Cyber City SOC team and link real evidence to the ticket using existing SOC triage.
4. In CTF Mission Control, create/edit a challenge and select **SOC Ticket** and **SOC Evidence Type** (Wazuh or Checkmk).
5. Confirm the challenge's readiness checks and release it. Students must be CTF participants and explicit members of the ticket's SOC team.

## Student behavior

Students investigate the assigned incident through Cyber City SOC, link real Wazuh/Checkmk evidence and resolve/close the incident ticket. The student submitting the CTF flag must have active membership in the SOC ticket's assigned team. The existing CTF flag verifier and ledger award points only after those checks pass.

This integration is read-only. It does not call Wazuh/Checkmk APIs itself, execute attacks, mutate Cyber City equipment, or change SOC ticket states. Evidence must exist in LabTech's already-ingested SOC tables and belong to the same city and mapped machine as the selected ticket. Only records observed after the CTF start time qualify.

## Scope

- No auto-solving or auto-award; correct flag remains mandatory.
- Solo and team CTF modes supported; CTF team membership alone does not grant SOC membership.
- Existing ungated challenges remain unaffected; existing scoring ledger unchanged.
- SOC teams are assigned within Cyber City SOC, independent of CTF teams.
- Wazuh gate requires a persisted `CyberCitySOCWazuhEvidence` association with the incident ticket.
- Checkmk gate requires a persisted `CyberCitySOCCheckmkTriage` linked ticket and real alert.
- Ticket must have status resolved/closed and be an incident ticket with a city-matched SOC team.
- Both lab-step and SOC requirements apply if both are configured on the same CTF challenge.

## Deployment and testing

Apply migration `0076_ctf_soc_ticket_evidence`, following `0075_ctf_verified_lab_step`. Run the Phase 4B regression suite and a manual SOC ingest/triage/CTF smoke test on development before production.
