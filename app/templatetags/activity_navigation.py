"""A single, course-aware navigation trail for every LabTech activity screen.

Used by the shared page layout so new activity pages inherit the same navigation
without each view writing independent breadcrumb or back-button markup.
Only explicitly approved, HTML-rendering activity routes are included.
"""
from django import template
from django.urls import NoReverseMatch, reverse

register = template.Library()

# Instructor creation, editing and child-management screens. These names are
# explicit, so unrelated CMS and admin pages retain their existing breadcrumbs.
INSTRUCTOR_ACTIVITY_ROUTES = frozenset("""
labtech_add_text_page labtech_edit_text_page labtech_delete_text_page
labtech_add_video labtech_edit_video labtech_delete_video labtech_add_audio labtech_edit_audio labtech_delete_audio
labtech_add_quiz labtech_edit_quiz labtech_delete_quiz labtech_manage_quiz_questions
labtech_add_question_to_quiz labtech_edit_question_in_quiz labtech_delete_question_from_quiz
labtech_import_questions import_from_bank
labtech_add_lab labtech_edit_lab labtech_delete_lab labtech_manage_lab_machines
labtech_manage_lab_steps labtech_add_step_to_lab labtech_edit_step_in_lab labtech_delete_step_from_lab
add_step_question edit_step_question delete_step_question
labtech_add_hotspot labtech_edit_hotspot labtech_manage_hotspot labtech_delete_hotspot
labtech_add_drag_and_drop labtech_edit_drag_and_drop labtech_manage_drag_and_drop labtech_delete_drag_and_drop
labtech_add_coding_activity labtech_edit_coding_activity labtech_delete_coding_activity
add_scenario_activity edit_scenario_activity delete_scenario_activity
add_flashcard_deck edit_flashcard_deck delete_flashcard_deck import_flashcards_csv
add_file_submission edit_file_submission delete_file_submission grade_file_submissions
add_team_scenario edit_team_scenario delete_team_scenario manage_scenario_services
pbq_create pbq_edit pbq_manage pbq_preview pbq_question_add pbq_question_edit
pbq_field_add pbq_field_edit pbq_artifact_add pbq_grade
instructor_rubric_builder instructor_rubric_levels instructor_rubric_roster
instructor_rubric_assessment activity_learning_outcomes
manage_step_checks create_step_check edit_step_check preview_step_check
lab_check_history
""".split())

STUDENT_ACTIVITY_ROUTES = frozenset("""
take_quiz quiz_result view_lab take_hotspot_activity
take_drag_and_drop_activity take_coding_activity take_scenario_activity
flashcard_deck_hub learn_flashcard_deck review_flashcard_deck
take_file_submission team_scenario_hub pbq_take
student_rubric_feedback
""".split())

# The PBQ result is used both by students checking their submissions and by
# instructors reviewing attempts; do not route a student to instructor pages.
AMBIGUOUS_ACTIVITY_ROUTES = frozenset({"pbq_result"})

QUESTION_CHILDREN = frozenset("""
labtech_add_question_to_quiz labtech_edit_question_in_quiz labtech_delete_question_from_quiz
labtech_import_questions import_from_bank
""".split())
STEP_CHILDREN = frozenset("""
labtech_add_step_to_lab labtech_edit_step_in_lab labtech_delete_step_from_lab
add_step_question edit_step_question delete_step_question
manage_step_checks create_step_check edit_step_check preview_step_check lab_check_history
""".split())
PBQ_CHILDREN = frozenset("""
pbq_edit pbq_preview pbq_question_add pbq_question_edit pbq_field_add
pbq_field_edit pbq_artifact_add pbq_grade
""".split())
FLASHCARD_MODES = frozenset({"learn_flashcard_deck", "review_flashcard_deck"})
RUBRIC_CHILDREN = frozenset({"instructor_rubric_levels", "instructor_rubric_roster", "instructor_rubric_assessment"})

LABEL_OVERRIDES = {
    "labtech_manage_quiz_questions": "Quiz questions",
    "labtech_manage_lab_steps": "Lab steps",
    "labtech_manage_lab_machines": "Lab machines",
    "labtech_manage_hotspot": "Hotspot zones",
    "labtech_manage_drag_and_drop": "Drag-and-drop zones",
    "grade_file_submissions": "Grade submissions",
    "pbq_manage": "Manage PBQ",
    "pbq_preview": "Student preview",
    "pbq_grade": "Grade PBQ",
    "instructor_rubric_builder": "Rubric builder",
    "instructor_rubric_levels": "Rubric performance levels",
    "instructor_rubric_roster": "Rubric grading roster",
    "instructor_rubric_assessment": "Grade with rubric",
    "activity_learning_outcomes": "Activity learning outcomes",
    "manage_step_checks": "Lab step checks",
    "create_step_check": "Add VM check",
    "edit_step_check": "Edit VM check",
    "preview_step_check": "Preview VM check",
    "lab_check_history": "Lab check history",
    "flashcard_deck_hub": "Flashcard study modes",
    "learn_flashcard_deck": "Learn flashcards",
    "review_flashcard_deck": "Review flashcards",
    "quiz_result": "Quiz results",
    "pbq_result": "PBQ results",
    "pbq_take": "Performance-based question",
    "pbq_question_add": "Add PBQ question",
    "pbq_question_edit": "Edit PBQ question",
    "pbq_field_add": "Add answer field",
    "pbq_field_edit": "Edit answer field",
    "pbq_artifact_add": "Add evidence artifact",
    "import_flashcards_csv": "Import flashcards",
}


def _url(name, *args):
    try:
        return reverse(name, args=args)
    except NoReverseMatch:
        return ""


def _course_from_context(context, kwargs):
    from app.models import Course

    for key in ("course", "activity", "quiz", "lab", "deck", "attempt", "step", "rubric", "criterion"):
        value = context.get(key)
        if value is None:
            continue
        if isinstance(value, Course):
            return value
        course = getattr(value, "course", None)
        if isinstance(course, Course):
            return course
        # Nested grading objects, quiz results, and lab step screens.
        for relation in ("quiz", "lab", "activity", "deck", "rubric"):
            parent = getattr(value, relation, None)
            course = getattr(parent, "course", None)
            if isinstance(course, Course):
                return course
    course_id = kwargs.get("course_id")
    if course_id is None:
        return None
    return Course.objects.only("id", "title").filter(pk=course_id).first()


def _activity_from_context(context):
    for key in ("activity", "quiz", "lab", "deck", "scenario", "item"):
        value = context.get(key)
        if value is not None and getattr(value, "title", None):
            return value
    attempt = context.get("attempt")
    if attempt is not None:
        for attr in ("quiz", "activity"):
            value = getattr(attempt, attr, None)
            if value is not None and getattr(value, "title", None):
                return value
    return None


def _name_for_page(context, route):
    heading = context.get("title")
    if isinstance(heading, str) and heading.strip() and len(heading) <= 130:
        return heading.strip()
    if route in LABEL_OVERRIDES:
        return LABEL_OVERRIDES[route]
    activity = _activity_from_context(context)
    if activity is not None:
        return str(activity.title)[:130]
    return route.replace("labtech_", "").replace("_", " ").capitalize()[:130]


@register.simple_tag(takes_context=True)
def activity_navigation(context):
    """Return uniform breadcrumbs/back target or None on non-activity pages."""
    request = context.get("request")
    match = getattr(request, "resolver_match", None)
    if not match or not getattr(request.user, "is_authenticated", False):
        return None

    route = match.url_name
    if route not in INSTRUCTOR_ACTIVITY_ROUTES | STUDENT_ACTIVITY_ROUTES | AMBIGUOUS_ACTIVITY_ROUTES:
        return None

    kwargs = match.kwargs
    course = _course_from_context(context, kwargs)
    if not course:
        return None

    instructor = route in INSTRUCTOR_ACTIVITY_ROUTES
    if route in AMBIGUOUS_ACTIVITY_ROUTES:
        attempt = context.get("attempt")
        # Grading a student's result is an instructor task; reviewing your own
        # submission is a student task. Never infer roles from an untrusted query.
        instructor = bool(attempt and getattr(attempt, "user_id", None) != request.user.pk
                          and (request.user.is_superuser or course.instructors.filter(pk=request.user.pk).exists()))

    course_id = course.pk
    nav = {
        "mode": "instructor" if instructor else "student",
        "course_title": course.title,
        "current": _name_for_page(context, route),
        "crumbs": [],
        "back_url": "",
        "back_label": "",
        "save_notice": route in ("pbq_take", "take_quiz", "take_coding_activity", "take_file_submission"),
    }

    def crumb(label, url=""):
        nav["crumbs"].append({"label": str(label)[:130], "url": url})

    crumb("Dashboard", _url("home"))
    crumb("Teaching courses" if instructor else "My courses",
          _url("instructor_my_courses" if instructor else "my_courses"))
    if instructor:
        crumb(course.title, _url("course_detail", course_id))
        parent_url = _url("labtech_manage_course_content", course_id)
        parent_label = "Course Builder"
    else:
        crumb(course.title, _url("course_detail", course_id))
        parent_url = _url("course_detail", course_id)
        parent_label = "Course"

    activity = _activity_from_context(context)
    activity_title = str(activity.title)[:110] if activity is not None else ""

    if instructor:
        crumb("Course Builder", parent_url)
        quiz_id = kwargs.get("quiz_id") or getattr(context.get("quiz"), "pk", None)
        lab_id = kwargs.get("lab_id") or getattr(context.get("lab"), "pk", None)
        pbq_id = kwargs.get("activity_id") if route.startswith("pbq_") else None

        if route in QUESTION_CHILDREN and quiz_id:
            url = _url("labtech_manage_quiz_questions", course_id, quiz_id)
            crumb("Quiz questions", url)
            parent_url, parent_label = url, "Quiz questions"
        elif route in STEP_CHILDREN and lab_id:
            url = _url("labtech_manage_lab_steps", course_id, lab_id)
            crumb("Lab steps", url)
            parent_url, parent_label = url, "Lab steps"
            step_id = kwargs.get("step_id")
            if route in ("create_step_check", "edit_step_check", "preview_step_check") and step_id:
                url = _url("manage_step_checks", course_id, lab_id, step_id)
                if url:
                    crumb("VM checks", url)
                    parent_url, parent_label = url, "VM checks"
        elif (route in PBQ_CHILDREN or route == "pbq_result") and (pbq_id or kwargs.get("activity_id")):
            url = _url("pbq_manage", course_id, pbq_id or kwargs.get("activity_id"))
            crumb("Manage PBQ", url)
            parent_url, parent_label = url, "PBQ"
        elif route in RUBRIC_CHILDREN:
            model_name, activity_id = kwargs.get("model_name"), kwargs.get("activity_id")
            if model_name and activity_id:
                url = _url("instructor_rubric_builder", course_id, model_name, activity_id)
                crumb("Rubric builder", url)
                parent_url, parent_label = url, "Rubric builder"
        elif route == "manage_scenario_services":
            scenario_id = kwargs.get("scenario_id")
            if scenario_id:
                url = _url("edit_team_scenario", course_id, scenario_id)
                if url:
                    crumb("Team scenario", url)
                    parent_url, parent_label = url, "Team scenario"
        elif route == "import_flashcards_csv":
            deck_id = kwargs.get("deck_id")
            if deck_id:
                url = _url("edit_flashcard_deck", course_id, deck_id)
                crumb("Flashcards", url)
                parent_url, parent_label = url, "Flashcards"
    elif route in FLASHCARD_MODES:
        deck_id = kwargs.get("deck_id")
        if deck_id:
            url = _url("flashcard_deck_hub", course_id, deck_id)
            crumb("Flashcard study modes", url)
            parent_url, parent_label = url, "Flashcards"

    # Current page is announced once and cannot lead to a self-link.
    crumb(nav["current"])
    nav["back_url"] = parent_url
    nav["back_label"] = parent_label
    return nav
