# Light, dark, and high-contrast appearance

The profile's existing Light, Dark, and Follow device choices work with Standard
or High contrast. Follow device responds to operating-system changes while the
page is open. High contrast applies to both light and dark palettes.

## Template authoring

`app/static/labtech/css/appearance.css` owns the palettes and shared Bootstrap
components. Application templates use semantic `--lt-*` CSS properties:

| Purpose | Properties |
| --- | --- |
| Page and cards | `--lt-page`, `--lt-surface`, `--lt-surface-muted` |
| Text and boundaries | `--lt-text`, `--lt-muted`, `--lt-border` |
| Status and actions | `--lt-primary`, `--lt-secondary`, `--lt-success`, `--lt-danger`, `--lt-info` |
| Text on filled status/action backgrounds | `--lt-on-accent` |
| Warning background and text | `--lt-warning` with `--lt-on-warning`; `--lt-warning-text` on plain surfaces |
| Subtle status panels | `--lt-success-subtle`, `--lt-danger-subtle`, `--lt-info-subtle`, `--lt-warning-subtle` |
| Persistent dark navigation | `--lt-nav-bg`, `--lt-nav-hover`, `--lt-nav-text`, `--lt-nav-border`, `--lt-nav-success` |
| Keyboard focus | `--lt-focus`, `--lt-focus-halo` |

Keep background and foreground pairs together. Avoid hardcoded white cards,
black headings, or Bootstrap `text-white` on custom status backgrounds. Use the
shared button, alert, table, and form classes instead of adding another palette.
Preserve a visible keyboard focus outline and textual status labels.

`appearance.js` synchronizes CKEditor's editable iframe and CodeMirror with the
page. It changes editor presentation without rewriting saved rich-text HTML.
CyberCity canvases read the same palette and redraw when the mode changes.

Uploaded images, author-specified inline colors, third-party embeds, email
notifications, and the separate public login/maintenance pages are outside this
application-theme pass. Authors should check their own rich text and diagrams
in each mode. No filter is applied to instructional images.

## Regression checks

Install the application's Python requirements in a virtual environment first.
Node dependencies below are for development/CI only, not the deployed server.
From the repository root:

```bash
npm ci --prefix scripts/theme-tests --ignore-scripts
scripts/theme-tests/node_modules/.bin/playwright-core install --with-deps chromium
export PYTHON_BIN="$PWD/venv/bin/python"
export NODE_PATH="$PWD/scripts/theme-tests/node_modules"
"$PYTHON_BIN" scripts/render_theme_fixtures.py /tmp/theme-pages.json
node scripts/test_theme_contrast.cjs /tmp/theme-pages.json /tmp/theme-results
```

The renderer uses an isolated in-memory SQLite database, real Django views, and
sample records. The browser serves pinned Bootstrap, editor, and axe assets
locally; external services and network mutations are stubbed. It checks 39
pages/component fixtures in four theme combinations, editor and canvas surfaces,
button hover contrast, keyboard focus, saved rich-text preservation, and live
Follow device changes. Standard mode uses axe's `color-contrast` rule; high
contrast uses `color-contrast-enhanced`. These are text-contrast checks, not a
complete WCAG conformance audit. See the W3C explanations for
[minimum contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)
and [enhanced contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-enhanced.html).

`THEME_ONLY=pbq_edit,course_detail` limits pages, `THEME_WIDTH=390` checks a narrow
viewport, and `THEME_SCREENSHOTS=1` saves screenshots for selected course, PBQ,
flashcard, and gradebook pages. Set `CHROMIUM_PATH` to use an existing compatible
Chromium executable. Results are written to the output directory as `contrast.json`.

Also run the application suite and migration check:

```bash
"$PYTHON_BIN" manage.py test app --top-level-directory . --settings=app.test_settings
"$PYTHON_BIN" manage.py makemigrations --check --dry-run --settings=app.test_settings
```

The Application regression tests workflow runs the browser checks alongside the
existing Django/PBQ checks. Manually review actual course content, keyboard
navigation, and production assets in supported browsers before rollout; automated
contrast checks cannot assess every image, interaction, or custom embed.

## Deployment

Use the normal [safe update procedure](../installation.md) after merging the
change. Run `collectstatic` with the deployment settings/environment and restart
the web service. This change introduces no database migration or new production
Python/Node dependency. Refresh cached styles in the browser after deployment.
