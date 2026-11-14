# CTF Phase 5A — AI Challenge Generator

This first Phase 5 increment generates **one complete instructor-reviewable challenge proposal at a time**, using the same LabTech AIClient transport used by course creation (OpenWebUI/EagleAI or configured OpenAI provider). It does not create VM templates or publish a student challenge.

## Instructor workflow

1. From **CTF Mission Control → Challenge Bank**, select **Generate with AI**.
2. Provide topic / learning objective, category, optional collection, difficulty, point value and environment (log analysis, network forensics, systems, SOC, or cryptography).
3. EagleAI returns JSON. LabTech validates shape, section lengths, hint costs, and sanitizes simple scenario HTML before showing any preview.
4. Review the separate **student story/task**, **plain-text evidence artifact**, two to five progressive **hints**, **instructor-only solution**, and tags. Verify that every correct answer is supported by the artifact.
5. Enter a final flag chosen by the instructor (it is never sent to EagleAI). Select **Save to Challenge Bank**.
6. The template is private to the instructor. Review it in Challenge Bank, then add to a competition as a hidden challenge for a second review before publishing.

## Safety and limits

- AI proposals require an active configured LabTech AI assistant; streaming and bounded retries reuse AIClient.
- Generated drafts live in instructor session state for at most 30 minutes and are not saved as public competition resources.
- The AI does not invent flags, links to live infrastructure, arbitrary executable payloads, or new VM configurations. LabTech never executes generated content.
- A fresh, instructor-entered flag is hashed before being stored.
- A private plain-text evidence attachment is generated independently from the bank template whenever that template is added to a competition. It is not embedded into the scenario, not publicly accessible, and not shared between competitions.
- Instructor solutions are **never** copied into student-visible challenges or portable challenge exports.
- CSV/JSON portable exports include reviewed plain-text artifacts (max 12,000 chars), but **not** instructor solutions or flags.
- No automated publishing, grading modifications, Wazuh/Checkmk API action or Cyber City VM execution occurs.
- The generated content is not automatically technically verified: an instructor must assess factual accuracy, evidence-to-answer consistency, and suitability.

## Deployment and tests

This change adds migration `0078_ctf_template_artifact_solution`, after Phase 4C migration `0077`. Run the Phase 5 tests and existing CTF suites before deploying. Test AI gateway timeout/invalid JSON, preview review, flag hashing, private artifact storage, export redaction and copy-to-event in development.

## Next increment

Phase 5B can add multi-challenge batch generation with independent preview/review, structured evidence attachment types beyond text, and AI generation of an optional draft verification plan for existing Cyber City/SOC resources (without creating or changing those resources automatically).
