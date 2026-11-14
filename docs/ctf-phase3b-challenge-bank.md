# CTF Phase 3B: Persistent Challenge Bank

Access **CTF Mission Control → Challenge Bank**. Instructors can create templates, organize them into collections, filter by category/difficulty/terms/tags, and deploy snapshots to their competitions.

* Save any existing challenge from its competition's Mission Control with **Save to Bank**.
* New templates need a nonempty flag; it is stored using Django's one-way password hash.
* **Add** creates a new hidden event challenge with independent hints. Instructor must review and release it.
* Collection access is limited to the owning instructor. The shared institution library and instructor-to-instructor approvals are future work; do not interpret this as campus-wide sharing.
* JSON and CSV exports contain prompt text, category, points, difficulty, tags, collection name, and hints only. **No flags, hashes, private evidence, student activity, or lab bindings.** Imports create draft templates with blank flag hashes; edit each to supply a fresh flag before deployment.
* Files and VM infrastructure are intentionally not copied automatically, to avoid breaking storage isolation or granting unauthorized lab access.
* JSON import: `{"version":1,"challenges":[{"name":"DNS 101","category":"Networking","difficulty":"beginner","description":"Investigate DNS","points":100,"tags":"dns","collection":"Network","hints":[{"cost":0,"text":"Review records"}]}]}`
* Upload limits: 1 MiB, 200 imported rows per request. Export is bounded at 5,000 templates; current UI displays first 250 matches. No bulk destructive action.

## Production deployment

This change introduces migration `0074_ctf_challenge_bank` which depends on `0073_ctf_team_invitations_scoreboard_controls`. Apply migrations using the normal LabTech deployment workflow. Existing CTF models and scoring data are unchanged.

Note: the existing Cyber City SOC migration drift described in Phase 2 is outside the scope of this PR. Confirm schema consistency separately before rolling out to production.

## Validation

Run `python manage.py test app.test_ctf_phase3b app.test_ctf_phase3 app.test_ctf_phase2 app.test_ctf2 --settings=app.test_settings`. Manual smoke test bank edit, source snapshot, imported draft completion, deployment and competition release before production.
