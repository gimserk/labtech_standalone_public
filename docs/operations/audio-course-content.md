# Audio course content operations

LabTech supports instructor-owned uploads and direct external HTTPS audio links. Uploaded files may be MP3, M4A, AAC, OGG/OGA, or WAV. Extension, MIME type, size, and a bounded file signature are validated. The default maximum is 250 MiB and can be changed with `AUDIO_MAX_UPLOAD_BYTES`.

## Deployment requirements

- Set the reverse proxy and application request-body limits at or above `AUDIO_MAX_UPLOAD_BYTES`, allowing modest multipart overhead.
- Configure Django's default storage with enough capacity and with working `open`, `save`, and `delete` operations. Opened objects must support binary seek/read because browser range requests depend on seeking.
- Keep course-audio storage private. Students access uploads only through authenticated, course-scoped stream and download routes; storage URLs are not rendered.
- Include `course_audio/` objects in media backups and restore drills. Database rows and storage objects form one ownership unit.
- Expect playback to generate byte-range traffic. A single range is supported; malformed, multiple, or unsatisfiable ranges return `416`.

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

## Verification

Run after configuration changes or deployment:

```bash
python manage.py check --deploy
python manage.py test app.test_audio --settings=app.test_settings -v 1
```

Then upload one supported file in a staging course, verify play/seek/download as an enrolled student, mark it complete, and confirm course progress updates. Also test one external HTTPS file from the target student browser network.

The application regression workflow also runs `scripts/render_audio_player.py` and `scripts/test_audio_player.cjs` with the pinned dependencies in `scripts/theme-tests`. These checks cover browser decoding, seeking, an HTML response in place of audio, retry recovery, source links, mobile sizing, and theme accessibility. They use local fixture media and do not certify a particular external host.
