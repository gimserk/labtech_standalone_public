# Rubric instructor workflow (second-phase draft)

This PR adds course-instructor builder and per-enrolled-student draft scoring views.

## Navigation
Course gradebook setup shows links for course activity types; selecting Edit rubric opens an activity-specific builder. Assignment type and activity ID are routed on the server, always revalidated against the selected course. Existing `can_manage_course_content` policy controls edit access.

## Authoring
Instructors may create and edit the rubric title, instructions, visibility flag, and criterion title/description/max points/order. Performance levels are currently managed via the Django Admin Rubric criteria editor.

## Draft student grading
The assessment URL is `/courses/<course_id>/rubrics/<model_name>/<activity_id>/students/<student_id>/`. It validates course access and enrollment, supports per-criterion points/feedback and overall feedback, and saves a draft. It does not publish or update Grade or existing FileSubmission.score.

## Not yet complete
- Criterion performance-level editing inside the course instructor page
- One-click release to the official Grade records (with audit and concurrency protection)
- Student-facing rubric feedback
- A user-facing student roster for navigating directly to assessments
- Template rubric reuse, course cloning/export/import
- Dedicated authoring and grade release tests on the live Django environment

These items are intentionally kept separate to avoid changing existing points/weighted grading without controlled verification.

Run:
`python manage.py check`
`python manage.py test app.test_rubrics app.test_rubric_workflow`
