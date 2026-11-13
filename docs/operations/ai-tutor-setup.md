# AI provider and course tutor setup

1. Open **Site Admin → AI Tutor & Providers** and add or edit an assistant.
2. For **OpenAI API**, leave Host blank, enter a model ID available to your
   API account, and provide an API key. Alternatively, set `OPENAI_API_KEY` in
   the server's environment. Existing assistants continue using **OpenWebUI**.
3. Choose a tutor behavior, add teaching instructions, and enable **Course
   grounding** if the tutor should search the student's selected course.
4. Save, then click **Test connection**. The test sends one short prompt and
   reports success or a safe configuration/error message. It does not expose
   your API key or student messages.
5. Open the AI Tutor as an enrolled student, select a course, and ask a
   question covered by its material. The tutor should cite a matching source
   title. Try an unrelated question: it should say no matching course excerpt
   was found rather than inventing a course citation.

The same provider selection now handles the scenario customer, the separate
scenario completion check, and course-generation jobs. Only the first active
assistant is used by this standalone installation.

Grounding reads current student-visible text pages, chapter/course overviews,
activity instructions and descriptions, published labs and quizzes, flashcards,
announcements, and visible uploaded PDF, TXT, MD, CSV, DOCX and PPTX resources.
Students can only select enrolled courses during their configured availability
dates; instructors and site administrators can preview their courses at any time.
Quiz answer keys, private resources, unpublished work, and scenario secrets
stay out of the prompt. An uploaded scanned PDF needs OCR before it becomes
searchable; audio and video need authored text descriptions. Retrieval is
keyword-based and bounded; the model can still make mistakes, so instructors
should verify consequential answers against course materials.


## Student chat Markdown rendering

The AI Tutor chat displays assistant replies as Markdown, including headings,
bold/italic text, ordered and unordered lists, fenced code blocks, tables, and
links. Markdown is parsed using the **locally hosted** Showdown 2.1.0 and
sanitized using **locally hosted** DOMPurify 3.4.17. No CDN request or new
Python package is required. Unsafe HTML, event attributes, images, forms, and
active content are not allowed in tutor output. Student-authored messages,
network errors, and conversation-history payloads remain plain text. If the
renderer cannot load, answers fall back to plain text rather than trusting
unfiltered HTML.

The locally vendored JavaScript and upstream notices are under
`app/static/labtech/vendor/`. The streaming response is
re-rendered at most once per animation frame and flushed on completion.
If you deploy with Django `collectstatic`, collect the new static
files as part of the normal `deploy/update.sh` upgrade.

Checks before release:

```shell
node --test tests/js/ai_tutor_markdown.test.cjs
python manage.py test app.test_ai_tutor --settings=app.test_settings
```

For a browser acceptance test, sign in as a student and ask the tutor to
"answer using a Markdown heading, bold text, a numbered list, a fenced
PowerShell command, and a two-column table." Confirm all elements render in
light, dark, and high-contrast modes; verify long code and tables scroll inside
the chat message. Check that literal HTML such as
`<img src=x onerror=alert(1)>` does not execute. Test both
direct OpenAI and OpenWebUI when available, since both use the same chat page.
