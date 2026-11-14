# LabTech Quizzes — Student Save/Resume and Instructor Navigation Controls

## Instructor settings

Open **Course Builder → Quiz → Edit**, and use:

| Option | Choices | Default |
| --- | --- | --- |
| Display mode | All questions on one page / One question at a time | All questions |
| Allow backtracking | Checked / unchecked | Checked |
| Max attempts | 0 (unlimited) or a positive number | Existing setting |
| Shuffle questions / answers | Checked / unchecked | Existing settings |

The backtracking checkbox only applies when **One question at a time** is
selected. With backtracking disabled, students can only move forward. Both
Previous and numbered links are removed, and the server rejects forged
requests to move backward or submit hidden question answers.

## Student experience

1. Open the quiz from the course. A new ungraded draft is created when the
   quiz opens for the first time.
2. In all-questions mode, enter any portion of your answers and choose
   **Save Progress** or **Save and Exit**.
3. In one-question mode, **Save and Next** stores the current response and
   advances the quiz. An answer is required before moving forward.
   **Previous Question** and a visited-question navigator are only shown
   when the instructor has allowed backtracking.
4. **Save and Exit** stores the current answer and returns to the course.
   The course activity then shows **Resume Quiz**. Resuming preserves
   the saved answers, quiz question order, and shuffled choice order.
5. **Submit Quiz** is only available on the last question in sequential
   mode, or at the end of the full quiz in all-questions mode.
   All questions must have answers to finalize. A confirmation prompt
   precedes final submission.
6. Only final submission creates `QuizAttempt` and `Answer` rows,
   calculates the grade, consumes an attempt, and marks the quiz complete.
   Student results and instructor gradebooks continue to use the
   existing completed-attempt models.

There is deliberately no timed autosubmission in this change; the student's
responses are persisted after explicit save and navigation actions.

## Existing quizzes and data

- Existing quiz records default to **all questions on one page**.
- Existing completed `QuizAttempt` and `Answer` rows are unchanged.
- `QuizDraft` is keyed by the (user, quiz) pair, with at most one unfinished
  draft per student per quiz. In-progress drafts are not imported into grades
  or counted as completed attempts.
- Question and answer ordering is snapshotted **per draft** to avoid reshuffling
  a resumed exam. A hash of the question, accepted answers, answer choices and
  points detects instructor edits during an active draft. A student receives a
  non-destructive warning rather than being graded against changed content.
  The student can contact the instructor or explicitly discard the affected
  draft and restart the revised quiz. Restart is only available when the
  instructor actually changed quiz content, so forward-only quiz settings
  cannot be bypassed by voluntarily restarting an unchanged quiz.
- A quiz must remain published and within its availability window for a student
  to resume or submit a saved draft. Instructors can preview unpublished quizzes.
- Duplicate submission of a finished draft cannot create a second graded
  attempt. Stale browser tabs are rejected if their draft ID is outdated.
- Instructor settings propagate through normal full-course serialization
  (the model's regular quiz fields), while saved student drafts are personal
  state and are not included in course templates.

## Deployment

Run the normal `deploy/update.sh` workflow **after merge**, ensuring the
Django migration `app/migrations/0071_quiz_draft_and_navigation_options.py`
has been applied. No frontend build step is required.

## Regression tests

```bash
python manage.py test app.test_quiz_progress app.test_course_builder app.test_course_curriculum_navigation app.test_gradebook_scoring --settings=app.test_settings
```

The tests cover progress persistence, final scoring, max-attempt behavior,
student isolation, valid answers, forged choice IDs, forward-only enforcement,
enabled backtracking, stable shuffles, CSRF, and duplicate submission.
