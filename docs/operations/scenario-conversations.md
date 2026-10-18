# Reviewing AI scenario conversations

In a course's instructor gradebook, select a student or find the scenario column in
the roster. Once a student has exchanged messages, **View conversation** opens a
read-only transcript with its in-progress/completed status. Only instructors of that
course and site administrators can open it, and the student must still be enrolled.
The transcript is separate from the CSV grade export; existing grade calculations
remain unchanged.

The role-play assistant receives the instructor's persona, issue and resolution
criteria, but not the completion code. Its system instructions tell it to stay in
character, withhold hidden details until relevant questions are asked, and resist
student requests to reveal the answer or change roles. A separate evaluation call
checks each exchange against the criteria. Only after that check says the issue is
resolved does the server issue the code and mark the attempt complete. Evaluation
errors and invalid replies fail closed, leaving the attempt in progress.

AI instructions and a second evaluation reduce casual prompt-injection bypasses but
cannot guarantee that a model never gives away a hint or wrongly approves an answer.
Review transcripts when assessing disputed attempts. The independent check adds one
model request per student message.
