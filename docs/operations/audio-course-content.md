# Audio course content operations

LabTech supports instructor-owned uploads and direct external HTTPS audio links. Uploaded files may be MP3, M4A, AAC, OGG/OGA, or WAV. Extension, browser-supplied MIME type, size, and a bounded file signature are checked. The default maximum is 250 MiB and can be changed with `AUDIO_MAX_UPLOAD_BYTES`.

### M4A upload compatibility and limitations

An M4A recording is an ISO Base Media File Format/MP4 container. Different
browsers and operating systems report the very same `.m4a` file as
`audio/mp4`, `audio/x-m4a`, `video/mp4`, `application/mp4` or
`application/octet-stream`. The upload validator accepts these MIME aliases
**only when the file extension is supported and the file bytes contain a valid
MP4 `ftyp` box with a recognized M4A/ISO-compatible brand**. It also supports
64-bit extended-size `ftyp` boxes and compatible brands beyond the original
four values.

The server stores the normalized `audio/mp4` MIME for a valid M4A, not the
sometimes misleading browser MIME. Generic `application/octet-stream`
uploads are allowed for other supported extensions when their content
signatures match; incompatible explicit MIME types (for example,
`text/html`) and mismatched headers still fail. This is a format-signature
check, **not** a media decoder, antivirus scanner or audio-only stream proof;
a valid MP4 container can still contain a codec unsupported by a specific
browser. An M4A video track or encrypted AAC can similarly fail playback,
even when the header is valid. Re-encode to AAC-LC in a standard M4A container
(or MP3) rather than merely renaming extensions when needed.

If a genuine M4A is still rejected, record the original filename, its
browser-reported Content-Type if available, and the first box/brand obtained
with a local media inspector such as `ffprobe`. Do not upload confidential
course recordings to third-party conversion sites just to diagnose them.

## Deployment requirements

- Set the reverse proxy and application request-body limits at or above `AUDIO_MAX_UPLOAD_BYTES`, allowing modest multipart overhead.
- Configure Django's default storage with enough capacity and with working `open`, `save`, and `delete` operations. Opened objects must support binary seek/read because browser range requests depend on seeking.
- Keep course-audio storage private. Students access uploads only through authenticated, course-scoped stream and download routes; storage URLs are not rendered.
- Include `course_audio/` objects in media backups and restore drills. Database rows and storage objects form one ownership unit.
- Expect playback to generate byte-range traffic. A single range is supported; malformed, multiple, or unsatisfiable ranges return `416`.
- Authenticated uploads are served with `Cache-Control: private, no-store`, `X-Content-Type-Options: nosniff`, and a canonical server-derived audio `Content-Type`, not the client's original MIME or untrusted imported metadata. Downloads use Django's safe Content-Disposition filename handling. Empty/corrupted stored files are not streamed.

External audio is linked directly from the student's browser. LabTech does not fetch, proxy, cache, DNS-resolve, inspect availability, or back up an external file. Availability, CORS behavior, privacy, bandwidth, and link lifetime remain the external host's responsibility.

## Student player and external links

Uploaded recordings and HTTPS sources use the same responsive player card with native play, pause, seek, and volume controls. The card follows the light, dark, and high-contrast appearance settings. Playback status explains loading, buffering, and errors; **Retry loading** requests the audio again. Uploaded recordings keep an authenticated **Download audio** link. External recordings keep **Open audio source**, which opens the provider in a new tab. Native controls and source/download links remain usable without JavaScript.

An HTTPS URL must return playable audio for the embedded player. A sharing/preview page can open successfully in a tab while failing as an audio source. Expired links, host restrictions, authentication requirements, network failures, and unsupported codecs can also prevent playback. The player reports failure without guessing which cause applies. Use the provider's direct media URL or upload the recording when the provider does not support inline playback. LabTech does not rewrite signed URLs or add a `crossorigin` requirement to the player.

Completion stays explicit: listening or reaching the end does not automatically mark the lesson complete. Use **Mark as Complete** below the player.

Deploy this player update by collecting static assets and restarting the web service; no database migration is needed.

## Error meanings

- `404` during uploaded playback means the item is unavailable, outside its availability window, cross-course, external-only, or missing from storage. The response intentionally does not expose storage paths.
- `416` means the browser sent an unsupported or unsatisfiable byte range.
- `503` means the authorized storage object could not be opened or read safely. Check the storage service without exposing backend details to students.
- `audio.E001` from Django checks means `AUDIO_MAX_UPLOAD_BYTES` is missing, nonnumeric, or nonpositive.
- `audio.E002` means the configured default storage lacks a required operation.

## CI workflow failures

`.github/workflows/audio-content-tests.yml` now has two independently
named jobs: **Audio upload, delivery & package tests** (Django unit tests,
course-package integration, model checks) and **Audio browser playback &
accessibility** (Playwright Chromium play/pause/seek/retry and accessibility
checks), with failure screenshots uploaded when generated. Both use an
explicit supported Python 3.13 runtime. Unrelated lab cleanup, gradebook,
and AI tutor regressions belong to the broader application suite rather
than obscuring Audio failures.

**Prior failure diagnosis (October 31, 2026):** the Audio `django` job in
run `41179794880` reported `runner_id: 0`, no assigned runner name,
**zero executed steps**, and completion in around two seconds. Separate
application and updater jobs showed the same result. Their executable
test code was never reached. This strongly suggests an account-level or
repository-level GitHub Actions runner allocation issue (billing, limits,
permissions or runner availability), not an established test assertion
failure. The exact GitHub annotation was unavailable from the connected
API. See the run in GitHub → Actions and check its top-level failure
annotation, repository Actions settings and any account/org Actions
billing or usage restrictions. Changes to the Python code alone cannot
resolve unallocated GitHub hosted runners.

## Verification

Run after configuration changes or deployment:

```bash
python manage.py check --deploy
python manage.py test app.test_audio app.test_course_packages --settings=app.test_settings -v 2
python manage.py makemigrations --check --dry-run --settings=app.test_settings
```

Then upload one supported file in a staging course, verify play/seek/download as an enrolled student, mark it complete, and confirm course progress updates. Also test one external HTTPS file from the target student browser network.

The application regression workflow also runs `scripts/render_audio_player.py` and `scripts/test_audio_player.cjs` with the pinned dependencies in `scripts/theme-tests`. These checks cover browser decoding, seeking, an HTML response in place of audio, retry recovery, source links, mobile sizing, and theme accessibility. They use local fixture media and do not certify a particular external host.
