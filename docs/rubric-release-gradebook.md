# Rubric release / student feedback (review draft)

Requires merged rubric foundation and instructor builder.

- Instructor grading remains a draft until **Release completed rubric grade** is submitted.
- Release requires an enrolled student, course management authorization, and a score for every criterion.
- Released scores override that activity's calculated percentage in the existing gradebook snapshot. Gradebook points/weights are unchanged. This intentionally does not overwrite historical QuizAttempt, FileSubmission, PBQAttempt, or Grade rows.
- Students may view only their own released criterion feedback at the dedicated route. Draft feedback is hidden.
- An instructor may not edit already released assessments through the draft grading page.
- No changes to database schema.

## Verification on staging

```bash
python manage.py check
python manage.py test app.test_rubrics app.test_rubric_workflow app.test_rubric_release
```

Also run the existing gradebook tests and verify points and weighted modes. Confirm release handles each activity category (including PBQ and file submissions) and the course is not publishing other students' feedback. Live deployment tests have not been executed via GitHub.

## Follow-up work

Rubric levels inline editor, instructor grade roster links, rubric template reuse and course clone serialization, audited release/regrade, end-to-end gradebook regression tests, and integration on every assignment's editing/review screen.
