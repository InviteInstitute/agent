# Using The Agent

## For Students

1. Open [agent.inviteai.org](https://agent.inviteai.org).
2. Pass the quick "Checking you're not a bot" check, which usually ticks itself.
3. Pick the coding space if the site serves more than one, and type the student ID your teacher
   gave you. ZANY asks for the class code too.
4. Code as usual. The agent's chat floats on the right, over the coding space.

A teacher's link can fill the form in, like `agent.inviteai.org/?env=zany&class=room-4&student=S01`.

In the chat a student can do these things.

- Type a question and press Send.
- Press **Help** to get a hint without typing anything.
- Press the microphone to ask out loud, then press it again to send. The question shows as text
  first, so they see what the tutor heard. A site turns this on with `TRANSCRIBE_MODEL`.
- Rate a reply with a thumb, and add a note on what helped or what was confusing.
- Press **Hide** to fold the chat into the blue tab on the right edge. The tab counts the check-ins
  that came in while it was folded.
- Press **Tutor** to hide or show the 3D tutor. Hiding it pauses it, so a slow computer gets its
  speed back.
- Press **Mute** to stop the tutor talking.

The agent keeps the chat, so a reload picks up where they left off. **Sign out** goes back to the
form.

A student in an ATLAS study never sees the form. ATLAS opens the agent for them, already signed in,
and there is no Sign out. [ZANY In An ATLAS Study](../concepts/atlas-study.md) explains why.

## For Researchers

The research view is at [agent.inviteai.org/research](https://agent.inviteai.org/research). Students
use the plain address and never see it.

Sign in as a student and the Research view opens. **Chat** and **Research** at the bottom of the
panel switch between it and the chat. In the Research view you can change what produces the
replies.

| Setting | What it changes |
| --- | --- |
| Model | any of the research models Lumen serves. The production one is marked. |
| Temperature | empty is the model's default |
| Max tokens | empty is 240 |
| Trim replies to bite size | off shows the model's whole answer, on trims it the way students get it |
| Prompt template | the whole reply prompt, with placeholders for the student's program, the facts and the chat |

While any setting differs from production, the view says "Custom settings are on". Your replies
then go to a research chat, kept apart from the student's chat, so an experiment never becomes part
of what a student's reply reads. A research reply also shows the model, the prompt it was given and
the tokens it used.

Your settings for a student also apply to that student's check-ins, since a check-in has no
request to carry them.

The view shows how many LLM tokens this browser session has used, out of its budget.
