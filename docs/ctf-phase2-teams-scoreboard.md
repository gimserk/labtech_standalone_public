# CTF Phase 2 — Team Competition, Live Scoreboard, Instructor Controls

## Instructor view

Open **CTF Mission Control → Manage** for a competition. Phase 2 adds:

- **Start Now** for scheduled events (records the new start time).
- **Pause/Resume Submissions** without ending the event. This blocks both flag
  submissions and purchases of new hints at the server, but retains scores.
- **End Event Now** for running events. Closes submissions and retains the
  final score ledger. Starting and ending early edit the competition's dates;
  there is no automatic reversal of End Event Now.
- **Freeze/Unfreeze Scoreboard**. Freeze captures the ranked standings and
  recent-solve feed at that instant. Any subsequently earned points and new
  solves remain hidden from participant leaderboards and classroom monitors
  until unfreezing. Flag submissions continue while frozen unless separately
  paused.
- **Release/Hide Challenge** actions in the challenge table. The existing
  authoring, attachments, and flags are unchanged.
- **Manual Score Adjustments** in the control panel. Select an enrolled
  individual or team, enter a positive or negative delta within 10,000
  points, and provide a 10–500 character reason. These are separate audited
  rows, never rewrites to historical correct submissions.
- **Control Audit** displays recent instructor actions and point changes.
  Entries include actor, timestamp, action, target and reason.

The teacher dashboard retains its prior readiness checks, challenge editor,
submission history, team/participant counts and evidence verification.

## Student teams

- Students can create and organize a team before the event begins.
- The captain invites an **eligible, already enrolled participant** by email.
  The invitation appears in the student's CTF challenge board, where they
  **Accept** or **Decline**. There is no automatic member addition.
- A pending invitation expires in seven days or at event end, whichever is
  sooner. A captain can cancel it. Only one pending invitation per student
  and event is permitted.
- Captains can transfer captaincy or remove a member before the team earns
  its first score or reveals a hint. Team leaders must transfer leadership
  before leaving a team containing other members.
- Team rosters **lock at the first successful solve or hint reveal**.
  Once locked, no ordinary member may join, leave, remove a member or transfer
  the captaincy. Team competition points therefore remain associated with
  a stable roster. An instructor must plan team assignments before scoring.
- Team-size and one-team-per-user requirements are checked inside a
  transaction that locks the event row, so simultaneous invitation
  acceptance cannot overfill a team.
- Students still join competitions using normal CTF enrollment and must
  remain eligible for a private/institutional competition.

This milestone does not send email invitations. It delivers invitations
inside the authenticated student CTF board; direct email notification can
be a later enhancement.

## Classroom scoreboard

The **Classroom Scoreboard** link is present in Mission Control, the
student challenge board and the standard leaderboard. It opens a wide
high-contrast view designed for a projected or classroom monitor display.

- Full-screen button, team/participant ranks, challenge solve counts,
  earned points and a short recent-solve feed
- Automatic authenticated polling every 12 seconds; no separate
  WebSocket/Celery infrastructure or public endpoint required
- Database-backed frozen standings, including a frozen activity feed
- Visibility respects the exact same private/institutional enrollment
  permissions as the existing leaderboard
- API response uses no-store caching and only includes display names,
  points, solved counts, and visible challenge names — no flags, API keys,
  hint content, email addresses or private machine credentials

## Safety and migration

**Required migration:** `0073_ctf_team_invitations_scoreboard_controls.py`
after the preceding CTF 2.0 `0072_ctf_foundation.py`.

The migration adds three audit/history models plus event pause/freeze
settings. Existing teams, participants, submissions, points and evidence
are retained, and all pre-existing competitions default to live standings
and unpaused submissions.

Run the normal production update after merging:

```bash
cd /opt/labtech
sudo ./deploy/update.sh
```

Verify the deployment runs migrations, restart the web/worker services, and
open a nonproduction CTF first. Verify a student can accept a team invite
and that the monitor scoreboard obeys Freeze without interrupting scoring.

## Tests

```bash
python manage.py test app.test_ctf_phase2 app.test_ctf2 \
    app.test_tekcon_nfc_scoped_ctf app.test_course_builder \
    --settings=app.test_settings
```

The suite checks enrollment restrictions, pending invitations, acceptance,
decline, cancellation, expiration, team size, captain controls, roster
locking, pause/resume, start/end, challenge release, adjusted scores,
frozen snapshots, private scoreboard API, CSRF and TEKCON integrations.

**Next milestone:** reusable challenge banks/import/export and real Cyber
City/SOC machine investigations. This phase deliberately does not create
simulated SOC integration or a separate ESP32 protocol.
