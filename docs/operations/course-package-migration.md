# Move a course from an older LabTech installation

1. In the old installation, export a `.coursepkg` with **Course Content** and
   **Course Resources** selected. Save the original export; do not edit or
   re-zip it. Add enrollments only when the new installation already has the
   same students with unique, nonblank email addresses.
2. In the standalone installation, open **Import Course** as an administrator
   and upload the package. Import checks the ZIP and manifest before creating
   anything. It creates a separate, inactive course; it never overwrites an
   existing course. A missing or unsupported file produces an error.
3. Open the imported course. Compare its chapter and activity counts with the
   old course, inspect lesson images and files, and configure any missing
   Proxmox templates. Guest-agent checks requiring a secret remain inactive
   until an instructor re-enters that secret.
4. Review enrollment warnings. Blank, missing and ambiguous email matches are
   skipped, along with those students' completion records. Create or match
   students on the new installation and enroll them through its normal course
   controls; imports never create accounts automatically.
5. Confirm your grading settings and activity content before activating the
   course. Keep a separate gradebook export from the old installation if you
   need historical marks: `.coursepkg` carries optional completion markers,
   not complete quiz attempts, lab answers, student submissions, or grade
   history. Forum discussions are not in the package format.

The provided historical ZIP with an unversioned manifest was tested in an
isolated database: 18 chapters, 127 text pages, 16 videos, 17 quizzes, 34 labs,
6 hotspot activities, 11 drag-and-drop activities, 12 coding activities and 15
flashcard decks imported and cloned with matching counts. Its old enrollment
records had blank addresses and its Proxmox templates were not installed in the
isolated test database; they require review on the destination server.

For current exports, the package identifies its version and includes course
announcements, flashcard images, resources, audio and portable guest-agent
checks. An instructor cloning a course gets a new enrollment code and independent
uploaded files, with no student enrollments or attempts. Check secrets are
never put in the package; copied checks that require them are disabled.
