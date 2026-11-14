# AI course generation — full draft builder

## Instructor workflow

1. Navigate to **My Courses → Generate Course with AI**.
2. Describe the subject, student audience, chapter count, certification objectives,
   and any required activities. Optionally attach a **PDF, DOCX, or UTF-8 TXT book**.
3. Use the AI generation queue to open **Review Blueprint**.
4. Edit course title, description, learning outcomes, chapters, lesson titles,
   objectives and activity types. LabTech supports text, quiz, PBQ,
   drag-and-drop, hotspot, flashcard, file submission, lab, coding,
   AI scenario, and video/audio *recording briefs*.
5. Choose **Generate Complete Draft Course**.
6. Inspect **My Courses → Course Content** and the **AI Jobs** quality-check notes.
   Generate missing real recordings and attach them as Video/Audio.
   Verify PBQ answer keys, quiz answers, code exercises, diagrams and VM template choices.
7. Publish individual quizzes, PBQs, and labs and then activate the course when ready.

A final project (file submission with rubric) and final quiz are added to
AI-created blueprints unless already present. All generated courses start with
`is_active=False` and code-required enrollment. Grading items use native
**points** mode initially; instructors can customize gradebook weighting.

## What is created

- **Text**: formatted and sanitized lesson content.
- **Quiz**: native multiple-choice questions and answer choices.
- **PBQ**: a separate story-only scenario, *private* text evidence artifact(s),
  and structured question/answer fields.
- **Drag/drop and hotspot**: usable generated numbered PNG diagrams with
  clue text, native labels and answer zones. Review before publishing.
- **Flashcards**: technical term/definition cards.
- **Submission**: student instructions with published criterion rubrics.
- **Lab**: draft scenario, instructor-reviewable steps, and optional VM template
  matches. Missing VM mappings are included in job setup notes.
- **Coding**: draft code exercises and test cases for instructor inspection.
- **AI scenario**: a student-facing scenario with private AI persona details
  and a generated secret resolution code.
- **Audio/video**: hidden instructor-only recording scripts under **Course Resources**,
  not fake recordings. Instructors provide actual media.
- **Learning outcomes and gradebook**: linked via native LabTech models.

## Reference book handling

Textbooks are **optional**. Uploads are capped at **50 MB** and validated by
extension and basic file signature. Default storage location is
`<BASE_DIR>/private_ai_textbooks`, outside `MEDIA_ROOT` and `STATIC_ROOT`.
A private filesystem storage class has no public URL. Books are not attached
to student Course Resources. Jobs keep the original private textbook for
regeneration until an instructor removes the generation job.

**Relevant excerpts, not the entire book**, are included in generation
requests to the configured AI provider. Upload only materials that you are
authorized to use and that may be processed by that provider. Uploaded text
is treated as untrusted source data, not prompt instructions.

PDFs use `pypdf` text extraction (first 500 pages maximum).
DOCX parses `word/document.xml`; TXT uses UTF-8. Scanned PDFs without
text must be OCR'd before upload. Book references in generated lessons should
be checked by the instructor against the original source.

The web server and Celery worker must have read/write access to the same
private textbook directory, with filesystem permissions limited to LabTech.
Back up this directory along with other persistent user uploads; do not
include it in public web roots.

## Deployment

1. Apply migration `app.0070_ai_course_reference_textbook`.
2. Restart web and Celery worker services after application updates.
3. Ensure sufficient private storage and a configured, active AI provider.
4. Run tests:
   `python manage.py test app.test_ai_course_generation_full --settings=app.test_settings`

Other repository workflows may report pre-existing migration drift in
legacy Cyber City SOC primary key IDs. That drift is independent of the
private textbook migration.

## Important constraints

This creates complete **reviewable drafts**, not instructor-free deployment.
Generated answers, diagrams and AI-produced code can be inaccurate.
Do not activate courses without assessment and accessibility review.
Large books and extensive multi-chapter courses can make long-running,
high-cost AI generation jobs. Video/audio cannot be synthesized by this
feature; the instructor must supply actual media recordings.
