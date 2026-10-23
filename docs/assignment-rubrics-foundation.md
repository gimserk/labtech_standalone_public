# Assignment rubrics — foundation PR

This is the first phase of per-activity instructor rubrics in LabTech. It introduces reusable rubric data structures and a Django Admin authoring path without changing current student scoring or gradebook calculations.

## Supported assignment targets
All current gradebook activity types via ContentType/Object ID: quizzes, labs, PBQs, file submissions, scenarios, coding activities, hotspot and drag/drop activities; optional informational items are supported because the gradebook already knows their types.

## Existing grading stays intact
CourseGradingPolicy points/weighted calculations and Grade records are not modified in this phase. Existing submissions and scores continue to behave as before. Scores saved in RubricAssessment are drafts, not official gradebook grades. A later workflow must validate completion, publish to Grade atomically and expose criterion feedback to students.

## Admin usage
Django Admin > Assignment rubrics: choose the course, supported activity ContentType and object ID; add rubric criteria and maximum points. Admin > Rubric criteria: attach optional named performance levels. Admin > Rubric assessments: create per-student assessments and criterion scores.

## Phase 2 required before production grading
Implement instructor-facing rubric builder on the assignment editing screen, criterion grading on existing submission review screens, explicit release, Grade synchronization respecting existing grading policy, student-facing feedback, cloning/export/import, permission checks and integration tests for each assessment type. Avoid using the draft RubricAssessment scores as published grades until then.

## Verification
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test app.test_rubrics

No test suite was executed by the GitHub connector. Review and deploy this foundation PR separately from enabling instructor-facing grading.
