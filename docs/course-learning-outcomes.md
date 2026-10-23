# Course learning outcomes and left curriculum panel

Instructors: course management > **Learning Outcomes** to add/edit/delete unlimited outcomes and set an optional code and display order. Each assignment's Actions > **Learning Outcomes** can select any number of the course's outcomes. Student course overview displays the course outcome statements and count of linked learning activities.

The existing sliding **Course Curriculum** drawer is now left-anchored, using LabTech theme variables and desktop left margin. No change to the global account navigation.

Migration: `0029_course_learning_outcomes` creates the outcome and relationship tables. Apply migrations on dev only after resolving any other migration branches.

Verification:
```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
python manage.py test app.test_course_learning_outcomes
```
Then manually verify the outcome editor, assignment Actions > Learning Outcomes, student course home, and mobile/dark-mode drawer.

This PR does not implement learning outcome attainment analytics, mappings for TeamScenario (not in gradebook activity registry), or migration of mappings in course clone/export/import. Those should be handled as subsequent work. No Django test execution performed from the GitHub connector.
