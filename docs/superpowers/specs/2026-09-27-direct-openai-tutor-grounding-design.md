# Direct OpenAI, tutor controls, and course grounding

## Goal

Make existing scenario and tutor chats work with an administrator-configured direct
OpenAI API model, while retaining OpenWebUI configurations. Let administrators
tune the tutor and let students ask questions against their own course material.

## Configuration and connectivity

- Each assistant selects **OpenWebUI** (existing default) or **OpenAI API**.
- The existing assistant management page and Django admin expose provider,
  model name, credential, status, tutor behavior, custom tutor instructions,
  and whether course grounding is enabled. A connection test reports a
  successful response or a safe, actionable failure. Link management from the
  Site Admin navigation.
- OpenAI uses the official Chat Completions endpoint with bearer authentication;
  a credential may be stored for the assistant or read from `OPENAI_API_KEY`
  on the server. Never send keys to the browser or log them. OpenWebUI keeps its
  configured host and behavior. Existing rows default to OpenWebUI on migration.
- Scenario role-play, its independent completion judge, tutor streaming, and
  course generation all use the same provider selection and configured model.

## Tutor behavior

- An administrator can choose Guided, Balanced (default), or Direct coaching
  and add custom instructions; server-owned instructions always precede
  student messages. Student-supplied system/developer messages are discarded.
- The tutor page offers an optional course chooser limited to enrolled courses
  currently available to students and courses the user teaches. The server
  checks enrollment and course availability on every proxy request. A student
  cannot attach another course's ID, early/expired content or private resources.
- When grounding is enabled and a course is selected, search the current,
  student-visible materials for the user's question and send a small set of
  relevant, labeled snippets with source names. The tutor references source
  names and admits when a fact was not found.
- Searchable material includes course/chapter descriptions, text pages,
  audio/video descriptions, published lab instructions, activity briefs,
  flashcards, announcements and student-visible uploaded text, PDF, DOCX,
  PPTX and CSV files. Never include unpublished/future/expired activities,
  instructor-only files, scenario persona secrets, quiz answer keys, grading
  criteria or hidden lab answers. Quiz titles/descriptions are available;
  individual assessment questions are deliberately withheld.
- Binary media without an authored description/transcript and scanned PDFs
  without extractable text cannot be searched. Grounding is request-time,
  bounded by file size, page count, record count, and total prompt size.

## Safety and compatibility

- Browser streaming handles SSE boundaries that split across network chunks.
  Server streaming does not log student content, responses or credentials.
- Existing accounts remain on OpenWebUI with grounding disabled until changed.
- Tests cover both provider URLs, auth and bad credentials, admin permissions,
  course isolation, unpublished/private/answer material exclusion, snippet
  selection, safe file extraction, and SSE fragment reassembly.
- No live OpenAI key is available in the test environment: mocked HTTP contract
  tests verify request shape, and the administrator connection test verifies the
  actual configured service after deployment.
