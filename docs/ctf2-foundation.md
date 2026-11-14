# CTF 2.0 Foundation — Instructor and Administrator Guide

## What this release changes

This phase improves the existing CTF (Capture the Flag) platform; it does **not**
replace campaign records, challenge categories, team IDs, successful solve
history, hint purchases, scoreboards, or links to existing LabTech labs.

### Instructor workflow

1. Open **CTF Mission Control** to create or manage a competition.
2. Select **Public**, **Institutional**, or **Private** visibility.
3. For Institutional or Private, link a **Course** so LabTech can verify
   eligibility. LabTech does not have a verified organization membership
   model, so this release treats institutional membership as an explicit
   course affiliation rather than using an unverified email domain. An old
   private/institutional campaign with no linked course is visible to its
   creator/admin only until a course is assigned.
4. Choose event dates and team settings. The form rejects an end time that
   precedes the start and invalid team sizes.
5. Select **Manage → Add Challenge** to set a category, difficulty, points,
   instructions and flag. Optional resources include a private evidence
   attachment, an external challenge site and a linked LabTech lab. Hints can
   be entered while first creating the challenge or when editing it.
6. Open **Manage** to check the readiness report and watch participants,
   teams, solves, revealed hints, and recent successful attempts.
7. When the event begins, enrolled students see a searchable challenge board
   with difficulty and solved-state filters. Flag submissions automatically
   validate enrollment, time and challenge visibility on the server.

### Student workflow

- Open **CTF Competitions**. The list shows only competitions for which the
  student is eligible.
- Enroll in an event. Students can enroll before it starts; they can open
  challenges once it is active.
- In solo events, submit flags directly. In team events, create or join a
  team before submitting.
- Open a challenge card to read its prompt, download evidence, visit the
  authorized LabTech lab or external challenge, reveal hints and submit a flag.
- Hints reduce the points earned **when the challenge is solved**. Multiple
  team members revealing the same hint only incurs one hint cost for the team.
- Check **Leaderboard** for current scores and solved challenge counts.

### Scoring and access control

- Only authenticated, enrolled participants of eligible competitions can
  submit flags or reveal hints.
- The event must be live, the challenge must be visible, and users must be
  in a team for team competitions.
- One successful solve is permitted per challenge per solo user or per team.
  PostgreSQL/SQLite conditional unique constraints protect the score ledger.
- Historical duplicate solves are archived to
  `CTFSubmissionDuplicate` before applying the new constraints. First credited
  solve is retained in the score ledger; the original IDs, participants,
  points, and timestamps of duplicates are preserved for audit.
- Incorrect flag submissions are throttled at six per user/challenge per
  minute. Incorrect raw flag guesses are never persisted.
- Challenge flags are now stored as salted Django password hashes and cannot
  be recovered from the database. An existing flag is retained when the
  instructor leaves the replacement field blank.
- Students never receive challenge hashes, unrevealed hint text, or access
  to unpublished/hidden challenges through CTF APIs.

## Important deployment migration

**Required:** Apply `app/migrations/0072_ctf_foundation.py`.

The migration converts all existing plaintext flags to one-way hashes, creates
the scoring constraints and duplicate-solve archive, and moves existing CTF
evidence from public media to private storage. It verifies each available
file before removing any legacy public copies. Missing legacy attachments
are recorded as readiness issues when the instructor visits Mission Control.

**File-system permissions:** Configure `CTF_PRIVATE_ROOT` to a persistent,
writable location outside `MEDIA_ROOT` and `STATIC_ROOT`. Without an explicit
setting, it defaults to `BASE_DIR / "private_ctf"`. On production, back up
both the database and `MEDIA_ROOT/ctf_files` first, ensure the LabTech service
user can write to the private directory, then run the normal migration/update
workflow. The web server must not expose the private root. Backup procedures
should be updated to include the new private directory.

For example, in Django deployment settings:

```python
CTF_PRIVATE_ROOT = "/var/lib/labtech/private_ctf"
```

Do not remove this directory during a normal LabTech upgrade. Do not serve it
through nginx, WhiteNoise, a public CDN or static files.

If a public-file cleanup fails because of permissions, the migration preserves
the verified private copy, but administrators should remove any leftover
`MEDIA_ROOT/ctf_files` public copies after checking that private downloads work.

### Compatibility

- Existing campaign, challenge, submission and category URLs remain unchanged.
- Existing successful attempts and points are retained except duplicate
  historical solves, whose details are archived for audit.
- Existing question banks, PBQs, courses, Cyber City, TEKCON, and gradebook
  structures are not changed by the new CTF controllers.
- All frontend controls use normal responsive Bootstrap components and
  accessible labels, including light/dark/high-contrast themes.
- Team invitations remain a later milestone. This foundation retains team
  membership management for eligible enrolled participants; the team leader's
  add-member action requires the target to already be enrolled.

### Focused regression tests

```bash
python manage.py test app.test_ctf2 app.test_course_builder \
    app.test_course_curriculum_navigation --settings=app.test_settings
```

Dedicated CI also checks Python and JavaScript syntax. If the broader audio
workflow reports new migrations for unrelated Cyber City SOC models, treat that
as separate pre-existing migration drift rather than a CTF scoring failure.
