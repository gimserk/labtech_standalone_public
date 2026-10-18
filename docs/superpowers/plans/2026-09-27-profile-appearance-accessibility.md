# Per-user Appearance Implementation Plan

Steps use checkboxes to track implementation and verification.

**Goal:** Let each user choose Light, Dark, or Follow device plus Standard or High contrast in their profile.

**Architecture:** Store constrained choices on `Profile`. Render the choices in the existing profile edit form and apply them through the shared base template and scoped CSS. Resolve device preference before styles load.

**Tech Stack:** Django models/forms/templates, Bootstrap 5.3 theme variables, CSS, small vanilla JavaScript.

**Spec:** `docs/superpowers/specs/2026-09-27-profile-appearance-accessibility-design.md`

## Global Constraints

- Keep existing accounts and anonymous pages Light/Standard by default.
- Preferences belong to the signed-in account and are private.
- Preserve profile form behavior and all existing course and lab flows.

## Review Focus

- A user with no Profile record still sees Light/Standard and can reach the edit form.
- An invalid appearance or contrast value is rejected without changing stored choices.
- Follow device changes with the operating-system setting without a page reload.
- Dark and High contrast keep foregrounds legible on custom profile components and Bootstrap controls.
- Existing profile edits retain unrelated fields and uploads.

### Task 1: Persist appearance choices

**Files:** `app/models.py`, `app/migrations/0013_profile_appearance.py`, `app/test_profile_appearance.py`

**Interfaces:** `Profile.display_theme` accepts `light`, `dark`, `system`; `Profile.color_contrast` accepts `standard`, `high`.

- [x] Write model default and valid choice tests, run them to see the missing fields.
- [x] Add two constrained fields with defaults and migration, run focused tests and migration checks.

### Task 2: Save and display profile settings

**Files:** `app/forms.py`, `app/views.py`, `app/templates/labtech/profile_form.html`, `app/test_profile_appearance.py`

**Interfaces:** The existing `profile_edit` view and `ProfileUpdateForm` save both choices; the edit template separates them from public details.

- [x] Write a student profile GET/POST test, a second-user isolation test, and an invalid-value test; verify failure before the change.
- [x] Add the fields to the form and edit-page section; keep all existing fields, image upload, redirects, and errors; rerun tests.

### Task 3: Apply the appearance throughout the shared layout

**Files:** `app/templates/labtech/generic_base.html`, `app/static/labtech/css/appearance.css`, `app/templates/labtech/profile_form.html`, `app/templates/labtech/profile_detail.html`, `app/test_profile_appearance.py`

**Interfaces:** `html[data-theme-choice]`, `html[data-bs-theme]`, and `html[data-contrast]` select the user's appearance.

- [x] Write tests for anonymous/light, two users' different themes, missing profile, and the device-preference script; verify failure before the change.
- [x] Add root attributes, early system-theme script, and scoped CSS for the shell, common controls, focus, and profile pages; rerun tests.
- [x] Run the existing app test suite, Django migration checks, and inspect CSS color pair contrast; publish a reviewable PR.
