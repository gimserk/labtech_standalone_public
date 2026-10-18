# Gradebook Points and Category Weighting Design

**Date:** 2026-09-27  
**Status:** Implemented on the feature branch; pending review and deployment validation

## Purpose

An instructor needs one reliable gradebook that includes every course content type, shows the difference between progress and a grade, and exports the same results displayed on screen. Instructors can assign points to individual items such as text pages. Each course starts in points mode; an instructor can enable optional category weighting by activity type. Students see the same calculated grades as instructors.

The instructor should be able to answer: what work counts, how many points is it worth, what has this student earned, which submissions await grading, and how was the course percentage calculated? Existing student attempts, completions, and instructor scores must survive the transition.

## Scope and Existing Defects

- Include Text Pages, Videos, Audio, Quizzes, Labs, Hotspots, Drag and Drop, Coding, Scenarios, Flashcards, and File Submissions in the gradebook inventory, whether graded or completion only.
- Replace separate calculations in `app/views.py` (`_get_single_student_grade_data`, `_get_gradebook_data`) with one shared scoring service used by the instructor roster, individual student view, student grade page, and CSV export. Keep course completion separate from course grade.
- Replace the unweighted average of graded item percentages. Currently a ten-point quiz and a hundred-point assignment have equal influence regardless of points.
- Repair `instructor_gradebook_export_csv`: the function reads `data['overall_completion']` although the helper provides `course_completion`, which fails on a student row; it also appends grade dictionaries to CSV rows instead of scalar values. Add the missing course grade and a faithful status/points breakdown.
- The legacy `course_gradebook_view` is not routed in `app/urls.py`. Verify no active caller uses it and retire its competing calculation, or delegate it to the shared service if a supported caller is found.

Out of scope: new student activity types, rubrics, letter-grade scales, grade curves, dropped lowest scores, late penalties, extra credit, manual override grades, per-student exemptions, and changing lab check execution. Lab guest-agent checks remain part of lab completion; they are not independent gradebook columns.

## Decisions and Alternatives

Selected: **activity-type categories and one shared scoring service**. Eleven fixed categories correspond to the eleven course content types listed above. An instructor sets one category weight for all items of that type and separately sets the points available on each item. This directly supports “Text Pages 20%; individual pages worth 5 or 10 points.”

Rejected: custom instructor-defined categories, which require reassignment rules and a larger editing interface; adding a `points` field to every existing content model, which duplicates configuration and complicates forms, copies, and imports; keeping independent calculation paths, which perpetuates inconsistent views and broken exports.

## Data Model and Upgrade

- `CourseGradingPolicy`: one row per `Course`, `mode` in `points` or `weighted`, with `points` the default. Old courses without a row use the default through the same service; there is no mass rewrite of existing submissions or grades.
- `CourseCategoryWeight`: course, fixed content-type key, decimal percentage (`0` through `100`, at most two decimal places); unique per `(course, type)`. Create or update all eleven values in one validated, atomic course-level operation. In weighted mode the weights of categories with included, positive-point items must total exactly `100.00`. All other categories have weight zero. Disallow enabling weighting or changing inclusion/points if that would invalidate this rule. When a new type is introduced to a weighted course, its items start excluded from grading until the instructor assigns a positive weight and enables them in one save.
- `GradebookItemPolicy`: course, content type, object ID, `included_in_grade` boolean, and nonnegative decimal `points_possible` with at most two decimal places; unique per `(course, content type, object ID)`. Validate the item actually belongs to that course; reject unknown models, NaN, negative, zero-point included items, and unsupported values. Delete or ignore configuration for deleted content and prevent ID reuse from inheriting stale configuration. Updates to points or weighting recalculate the displayed grade from existing attempt percentages; they do not rewrite student attempt records.
- Initially, Quizzes, Labs, Hotspots, Drag and Drop, Coding, Scenarios, and File Submissions retain graded status. Their point defaults are `100`, except quiz points default to the sum of question points when positive and file submission points default to `max_score` when positive. Text Pages, Videos, Audio, and Flashcards initially have zero grade contribution but remain visible for completion; the instructor can give each item a positive point value and include it. Explicit item policies remain fixed when questions are subsequently edited, so an existing gradebook denominator does not silently change.
- For file submissions the activity's `max_score` remains the grading rubric's denominator. Gradebook points may differ and multiply the resulting percentage. Do not change `max_score` as a side effect of changing gradebook points. For previously graded submissions, prevent changing `max_score` through this feature because the saved raw score has no historical maximum snapshot; preserve the currently stored score and grading state.
- Use `Decimal` for points and weights, validate on both forms and service boundaries, and round only when presenting output. Existing float percentages are clamped to the supported `0–100` range for calculation while displaying an invalid-source warning to instructors; no student record is silently edited.

The first load of a course can derive default policies without persisting every item. An instructor save materializes edited policies. Course copy and course backup/import must carry the course mode, category weights, and per-item policies with new content IDs; exporting a course must not export student grades or submissions. The existing clone, package import, and content backup paths omit File Submission activities, so extend those paths to carry the activity definition (never its student submissions) wherever they need that item in order to preserve its gradebook policy. Existing grade attempts, file grades, and progress remain linked to their original content.

## Which Items Count

The inventory lists all eleven content types and shows unpublished drafts or items scheduled for future release as **Not yet included**. Published/released items contribute to the grade denominator even after their due date or availability window closes, so earned grades do not disappear on course close. Items with `included_in_grade=False` or zero points show **Completion only**. Recalculate when publication/release state or grading policy changes; the grade UI and CSV display an as-of timestamp and the applicable item set. Course completion retains the established progress rules for these same activity types and is never treated as a point score.

Unattempted, available, included work contributes `0 / points_possible` immediately, as previously chosen for the gradebook. A submitted file awaiting instructor grading shows **Pending**; it contributes neither earned nor possible points until graded, with the course grade labeled **Provisional**. Do not treat pending as a zero. A course with no assessable included items shows **N/A**, never an invented `0%` or `100%`.

For repeated attempts, preserve the currently displayed scoring policy: latest Quiz, Hotspot, Drag and Drop, and Coding attempt; Scenario completion; unique File Submission; and the current Lab step-answer/completion logic. Text Pages, Videos, and Audio earn full configured points on a completion record. Flashcards can earn points proportional to cards mastered; an empty deck is completion only and cannot earn points until it has cards. Scenario and Coding items use their current complete/pass rules for full points, otherwise zero. Labs without step questions earn full points only on completion. Lab step questions keep their existing fraction of correct questions for partial credit, while guest-agent checks continue gating lab completion and do not grant extra points. Show an in-progress status independently of a partial score.

For every assessable item: `item_earned = points_possible × normalized_score_percent / 100`. Use the saved quiz attempt percentage; normalize Hotspot and Drag and Drop correct/total; use file submission raw score divided by its own `max_score`; use the existing lab fraction; and apply the completion/mastery rules above. A failed graded Coding submission is a submitted `0`, while a missing submission is **Not started**. Labels must not mistake these two states.

## Calculation Rules

**Points mode (default):** `course_grade = sum(item_earned) / sum(item_points_possible) × 100` over available, included, assessable work. Show `earned / possible` and percentage at both item and course levels; show **N/A** if the denominator is zero.

**Weighted mode:** for each category with assessable items, calculate `category_percent = sum(item_earned) / sum(item_points_possible) × 100`. Each category's contribution is `category_percent × category_weight / 100`. This makes per-item point values matter *within* a weighted category. When a category contains only pending work, mark it Pending and temporarily normalize the weights of assessable categories to 100 for the displayed **Provisional** grade; show the configured category weights alongside the effective weights. If no category is assessable, show **N/A**. Zero-point and excluded items never dilute a category. Unattempted available items *are* assessable zeros.

Example: Text Pages weight `20%`, Quizzes `80%`. Two pages worth `5` and `15` points, with only the first complete, give Text Pages `5 / 20 = 25%`. A `60 / 100` quiz gives Quizzes `60%`; the course grade is `25% × 20% + 60% × 80% = 53%`. In points mode, the same items give `(5 + 60) / (5 + 15 + 100) = 54.17%`.

## Instructor and Student Experience

- The instructor gradebook opens on the roster, with student search, chapter/category filters, horizontal scrolling with a sticky student column, and clear links to pending file submissions. Each item header shows type, chapter, and points; columns show **earned / possible**, percentage, and status. Category subtotals, course grade, and course completion remain visible. A selected student view explains the same score item by item.
- A **Grading setup** screen shows a points/weighted toggle, a row for each content type, per-item points and inclusion controls, and a live calculation preview with the example interpretation of weights. Validate the category sum and missing point values before saving. Only course instructors or superusers may view/edit setup and roster.
- Students see their own grades and completion in `my_course_grades.html`; they cannot see other students or edit the policy. Instructor and student screens display the same item status and calculated course percentage for the same course and time.
- Preserve existing activity launch, completion, quiz attempt, file grading, and instructor navigation. Do not collapse progress percentages into academic grades.

## CSV Export Contract and Audit

`instructor_gradebook_export_csv` must reuse the same prepared roster rows and item ordering as the screen, not recalculate scores. It must require an authenticated course instructor or superuser and return a forbidden response otherwise; do not broaden access to every staff user.

- Return UTF-8 `text/csv` with one header row and exactly one data row per enrolled student, including zero students. Maintain a safe course-title-based download filename.
- Start with Student Name, Student Email, Course Grade %, Earned Points, Possible Points, Grade Status, and Course Completion %. Add a stable set of category subtotal and weight columns, then chapter completion columns. Each content item has distinct columns for status, earned points, possible points, and score percent. Include category, chapter, and immutable content-type/ID identifiers in item headers so duplicate titles remain distinguishable.
- Every row has exactly the same number/order of columns as its header. Emit scalar numeric or display text values, never Python dictionary representations. Use a consistent blank marker for N/A or Pending numeric values; never export `None` or a misleading zero in those cases. Include configured/effective weights and a provisional indicator where pending grades affect a weighted result.
- CSV-escape or neutralize spreadsheet formulas in user-entered names, emails, chapter titles, and item titles (including leading whitespace and control characters before `=`, `+`, `-`, or `@`). Preserve correct quoting of commas, quotes, and newlines; numeric score columns remain numeric for spreadsheet analysis. Limit export to this course's enrolled students and content.
- Verification must reproduce the existing `overall_completion` KeyError with a real enrolled-student export and show the correction; test dict-free scalar item cells, headers/row width, pending and unattempted work, both grading modes, duplicate names/titles, CSV injection text, no enrollments, and forbidden access. Test agreement among CSV, roster, selected-student, and student percentages from the same fixtures.

## Implementation Boundaries

The gradebook service owns: ordered course item inventory, batched attempt/completion loading, grade/status normalization, category and course calculations, and a stable view/export data contract. Views handle authorization and request selection; forms handle instructor inputs; templates display already prepared values. Avoid per-student-per-item database queries by fetching attempts and completions in batches for a course or roster page. Keep scoring free from writes; changes to policy use one atomic transaction and invalidate derived caches if any are introduced.

Inventory should be defined once so content types added to LabTech later trigger an explicit inclusion decision. Guard against cross-course generic foreign keys, deleted objects, duplicate attempts, orphaned completion records, zero denominators, and a gradebook containing no students. Determine visibility at the same as-of time for roster and CSV, and restrict a selected student ID to an enrollment in the current course.

## Acceptance Criteria

1. A course without an explicit grading policy uses points mode; its existing attempts and completion data remain intact.
2. Every listed activity type appears in instructor and student grade details with correct completion/graded distinction, including audio and new labs with guest-agent checks.
3. An instructor can assign points to an individual text page; on completion the student earns those points. Available unattempted included work counts as zero. Pending file grades do not count as zero and are visibly provisional.
4. A course can enable category weights by type, exactly `100.00` across active graded categories, and item points affect results within a category. Switching back to points mode changes only the calculation, not submitted data.
5. For the same fixture, roster, single-student view, student page, and CSV agree on grades and completion. Grade calculations are precise before rounding.
6. CSV downloads for empty and populated courses, never crashes on an enrolled student, has matching header/row widths and scalar item cells, accurately identifies categories and duplicate titles, and blocks unauthorized exports.
7. Instructor setup, course copy, backup/import, and existing course workflows preserve grading configuration without exposing grades or changing activity behavior.
