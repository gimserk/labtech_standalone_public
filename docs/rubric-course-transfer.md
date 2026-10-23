# Rubric course transfer
Rubric definitions are transferred when cloning a course, exporting/importing a course package, and backing up/restoring course content. Source activity IDs are translated through the existing course-item mapping. Criteria and performance levels copy; student rubric assessments, criterion scores, grader identities and release events never copy. New copies are unpublished.
Older packages without a rubrics key remain supported.

Deployment gates:
```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test app.test_rubrics app.test_rubric_transfer app.test_rubric_workflow app.test_rubric_release app.test_rubric_roster_reuse app.test_rubric_final_ux
```

Manually smoke test full clone, package export/import, and restore on a disposable test course. Not tested live by this connector.
