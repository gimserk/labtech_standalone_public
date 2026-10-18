# Per-user appearance and contrast

## Goal

Each signed-in user can choose a readable appearance in their own profile without changing anyone else's display. Preserve the current light appearance for existing accounts and visitors.

## Profile controls

- Appearance: Light (default), Dark, or Follow device. Follow device responds to operating-system light/dark changes while the page is open.
- Color contrast: Standard (default) or High contrast. The two controls can be combined.
- Show the choices under a private **Accessibility and appearance** heading on the profile edit page, separate from publicly visible profile details. Existing public profile fields and save behavior remain intact.
- Store choices on the existing `Profile` model with constrained values and a database migration. Unauthenticated pages use Light and Standard. Missing legacy profiles render with the defaults.

## Rendering

The shared `generic_base.html` sets the theme and contrast on the root element before loading Bootstrap. For Follow device, a small script reads `prefers-color-scheme` before styles load and updates it when the device preference changes. Bootstrap's color variables handle common controls; a scoped stylesheet covers LabTech's page background, cards, forms, navigation, links, focus, alerts, and profile pages. High contrast uses deliberately distinct foreground, surface, border, and focus colors. Do not rely on color alone to indicate validation: retain labels, icons, and status text.

## Compatibility and verification

- Saving profile preferences must not change another user's preferences or make them public on the profile detail page.
- Light/Standard keeps the existing page appearance; existing profile submissions and redirects still work.
- Test profile persistence, per-user rendering, anonymous and missing-profile defaults, invalid choices, and the migration. Verify Light, Dark, and High contrast text and control colors against W3C's contrast guidance and check the app's existing tests.
