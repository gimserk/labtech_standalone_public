# AI Course Creator: EagleAI 504 Gateway Time-out

## Why Tutor works while Course Creator fails

The Tutor sends `stream=True` Chat Completions requests and receives tokens
incrementally. Previously, Course Creator used `stream=False`, required the
provider to generate the **entire course blueprint** in one response and set a
500-second client timeout. A reverse proxy may enforce a much shorter
`proxy_read_timeout` or upstream duration limit regardless of the client's
timeout. The resulting provider-side 504 is not evidence of invalid API keys
or a stopped model; Tutor responses can work normally.

## New Course Creator behavior

- Requests stream SSE Chat Completions tokens and recognize standard
  OpenAI/OpenWebUI-compatible responses. Retains the same configured active
  assistant, URL, model, API key and SSL verification policy.
- Temporary HTTP 429, 502, 503, 504 or 524 responses, network timeouts and
  incomplete streams receive up to **three transport attempts** with bounded
  2s/5s delays. Permanent authorization/configuration errors do not retry.
- OpenWebUI servers that reject `response_format=json_object` while
  streaming can fall back to prompt-enforced JSON.
- Generates a **small course outline first**, then makes **one separate
  activity-plan call per chapter** rather than waiting for a 27- or 60-chapter
  JSON completion in one proxy request. Global 480-activity limits and required
  final project/exam remain enforced.
- Each successful chapter updates the existing job's
  `ai_blueprint._progress` with a human-readable stage and chapter count.
  This temporary object is replaced with the finished blueprint before status
  changes to `PENDING_REVIEW`. No new migration is needed.
- The AI Course Generation Queue and the Blueprint waiting screen show
  chapter progress. Background jobs run in Celery, not inside a web request.
- Course content generation also uses streamed transport. Existing instructor
  review flow, generated activity types, private textbook storage, AI Tutor
  streaming and grading restrictions remain unchanged.

## Deploy and retry

After merging the fix:

```bash
cd /opt/labtech
sudo ./deploy/update.sh
```

Ensure `labtech-worker` is restarted with the new code by the deployment
process. On the **AI Course Generation Queue**, select **Retry** for the
failed blueprint job. A retry does not affect existing completed courses.

If EagleAI still returns 504 for small, streamed chapter requests, inspect
its reverse proxy and upstream inference service. In particular, check
whether `proxy_buffering` prevents streamed tokens from reaching LabTech,
whether the route has a shorter `proxy_read_timeout` than expected, and
whether the model backend itself has a request deadline. Changing LabTech's
HTTP client timeout alone **cannot** override these gateway limits.

Example server-side checks (use the actual EagleAI nginx config):

```bash
sudo nginx -T | grep -nE 'proxy_read_timeout|proxy_buffering|api/chat/completions'
sudo journalctl -u labtech-worker -n 100 --no-pager
```

Avoid logging or printing private API tokens, textbook excerpts or student
content. If a provider-side gateway policy cannot be changed, choose smaller
chapter plans or a faster active AI model in LabTech.
