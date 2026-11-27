# Check-Ins

A check-in is the agent reaching out without being asked, when a student seems stuck, idle or on a
good run. It shows in the chat as "Checking in", and the tutor says it out loud.

Check-ins message real students, so they are off until a site sets `CHECKINS_ENABLED=true`.

## The Daemon

A background thread in the API runs a pass every `CHECKIN_INTERVAL_S` seconds (5 by default). It
slows toward `CHECKIN_IDLE_MAX_S` (30) while no check-ins go out, and backs off after a failure.
Each pass does this.

1. It reads every environment's new logs.
2. It looks at each student with an event in the last `STUDENT_RECENCY_HOURS` (24).
3. The learner-model engine (`server/vendor/agent-lm-packages`) finds the triggers in how much each
   run changed from the one before.
4. A trigger it hasn't seen before is kept in `triggers`, and gets a check-in if the student's
   page is open.

A student's page counts as open while its check-in stream is connected. So someone who closed the
tab gets no check-ins, but their triggers are still kept for research.

## The Triggers

The thresholds live in the engine's `learner_models/constants.py`, shared with the Learner
Modeling Dashboard.

| Trigger | Fires when | Feedback classes |
| --- | --- | --- |
| Wheel-spinning | six runs in a row with no change to the program | Reassure, Encourage Testing (Diagnose) |
| Resilience | a real edit after four or more unchanged runs | Evidence-Based Praise |
| Explorer | one run changes 13 or more blocks | Encourage Testing (Diagnose) |
| Step-by-Step | a steady run of small edits, six on most playgrounds and five on Coral Reef Cleanup | Evidence-Based Praise |
| Inactive | no events for four minutes, again every ten minutes while it lasts | Reassure, Question |

Each trigger fires once per run in a session. `TRIGGER_DISABLED` names trigger types the daemon
still finds and keeps but doesn't act on, like `inactive,explorer`.

## How A Check-In Is Written

It goes through the same pipeline as a question ([How A Reply Is Made](how-a-reply-is-made.md)),
with the trigger's feedback classes and no question. The model gets a neutral fact about what the
student did, like "The student keeps running the same program without changing any blocks." It
never gets the trigger's name, which once leaked into replies.

A researcher's settings for that student, saved from the research view, apply to their check-ins
too. Check-in tokens count toward the site's daily ceiling.
