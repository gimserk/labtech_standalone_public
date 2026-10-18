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
