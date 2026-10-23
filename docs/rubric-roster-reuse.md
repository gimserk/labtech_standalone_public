# Rubric grading roster and reuse

The instructor rubric builder offers an **Open student grading roster** link for an existing rubric. The roster shows enrolled students and whether an assessment is unstarted, draft or released, and links to per-student criterion grading.

When an assignment has no rubric, an instructor can copy another rubric **within the same course**, including its ordered criteria and performance levels. The new copy starts unpublished. No student assessments or grades are copied, and existing rubric definitions cannot be overwritten.

Both endpoints enforce `can_manage_course_content`; course/activity ownership is checked again on the server. Rubric copying is a CSRF-protected POST. Neither operation changes the official gradebook.

After deployment to a test server, run:
```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test app.test_rubrics app.test_rubric_workflow app.test_rubric_release app.test_rubric_roster_reuse
```

**Still needed:** same-screen performance-level authoring, gradebook display of student feedback links, full rubric cloning across courses, and automatic regression checks of points/weighted grade calculations. Not yet tested on a running LabTech instance.
