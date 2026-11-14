# LabTech activity navigation audit (November 2026)

## Observed issues

- `generic_base.html` already rendered breadcrumbs when the view supplied
  `breadcrumbs`, but many instructor/student activity views did not supply them.
- Drag-and-drop and file-submission editor templates rendered **additional**
  breadcrumbs, sometimes producing two separate navigation trails.
- The lab student screen rendered its own unrelated breadcrumb markup; the
  quiz, scenario, and file-submission student screens rendered independent
  Back links. Coding, PBQ and flashcard activity screens were inconsistent.
- Quiz question editing, lab steps, hotspot zone management, coding activity
  editing, rubric screens, and PBQ grading did not consistently show a return
  to the correct parent screen.

## New shared navigation

`app/templatetags/activity_navigation.py` builds an allowlisted route-aware
navigation model. `generic_base.html` renders it through
`partials/activity_navigation.html`. It does not change unrelated admin
or general site pages.

**Instructors:** Dashboard → Teaching courses → Course → Course Builder →
Activity. Deep child pages add their actual parent before the current page.

**Students:** Dashboard → My courses → Course → Activity. Back returns
to the course. Flashcard Learn/Review return to the deck's study-mode
selection. A student reviewing their PBQ submission receives student links;
an instructor reviewing the same attempt receives instructor links.

| Activity family | Instructor authoring and management | Student / review screen |
| --- | --- | --- |
| Text lesson | Add, edit, delete | Course reader |
| Video | Add, edit, delete | Course reader |
| Audio | Add, edit, delete | Course player |
| Quiz | Add/edit/delete, question list, question editing, CSV/bank import | Take quiz and results |
| Technical lab | Add/edit/delete, machines, steps, step questions, VM checks/history | View lab/session |
| Hotspot | Add/edit/delete, answer zones | Take hotspot |
| Drag-and-drop | Add/edit/delete, answer zones | Take drag-and-drop |
| Coding | Add/edit/delete and tests | Take coding activity |
| AI scenario | Add/edit/delete and persona | Take AI scenario |
| Flashcards | Add/edit/delete, CSV import | Study hub, learn and review modes |
| File submission | Add/edit/delete, grading | Submit files |
| Team scenario | Add/edit/delete, machine/service setup | Team scenario hub |
| Performance-based question | New/edit/manage, artifacts, questions, answers, preview, grading | Take PBQ, attempt history/results |
| Assessment support | Rubric builder, criteria levels, grading roster, per-student assessment; activity learning outcomes | Student rubric feedback |

Course reader/player items are displayed within `course_detail` rather than
separate pages, so they inherit the course's own navigation. PDF exports,
download handlers, JSON APIs, POST-only operations, and other non-HTML
responses are excluded.

### Parent destinations

- Quiz questions / question editors → **Manage Quiz Questions**
- Lab steps / step-question editors → **Manage Lab Steps**
- VM check editing → **Manage VM Checks** (or lab steps when step ID is absent)
- PBQ subeditors and instructor results → **Manage PBQ**
- Rubric levels / roster / grading → **Rubric Builder**
- Team scenario service configuration → **Edit Team Scenario**
- Flashcard CSV import → **Edit Flashcard Deck**
- Student flashcard learn/review → **Flashcard Study Modes**
- Other activity editing → **Course Builder**
- Other student activity screens → **Course**

### Accessibility and consistency

- One `<nav aria-label="Activity breadcrumb">` with semantic ordered list.
- One top **Back to Course** or **Back to [parent]** link in consistent placement.
- Visible focus states, responsive wrapping, and light/dark/high-contrast
  theme tokens; no browser-history-based return URLs.
- Long-page footer **Cancel** buttons remain when useful for unsaved edits.
- Student pages with unsaved responses display a reminder to save before
  leaving; navigation itself never silently submits or changes student work.

### Adding a new activity

1. Reuse `generic_base.html` and do not add a second breadcrumb trail.
2. Add the new named HTML route to `INSTRUCTOR_ACTIVITY_ROUTES` or
   `STUDENT_ACTIVITY_ROUTES` in `activity_navigation.py`.
3. Add a parent mapping if the screen is nested in an activity editor.
4. Make sure the view provides `course` or `course_id`.
5. Add a test in `app/test_activity_navigation.py`; execute
   `python manage.py test app.test_activity_navigation --settings=app.test_settings`.

The shared navigation is intentionally allowlisted: it is never inferred from
the URL query string and never changes authorization rules in underlying views.
