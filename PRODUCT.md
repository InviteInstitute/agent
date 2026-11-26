# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Middle-school students in INVITE partner classrooms, mostly on school Chromebooks, where the
browser window is about 600px tall. They are learning to program a virtual robot in block code,
in VEXcode VR or ZANY, and open the agent page from a link their teacher gives them.

Researchers are the second audience. They open `/research` to try other models, prompts and
sampling, and those replies stay apart from what students see.

## Product Purpose

The INVITE Agent is a tutor that sits on top of the student's coding environment. It reads the
student's program and run logs, answers questions about them, checks in when a behaviour trigger
fires (wheel-spinning, inactivity and others), and can say its replies out loud through a 3D
tutor.

Success is a student who keeps coding. The agent nudges them back to their program quickly, so
the chat stays small and out of the way and the coding environment stays the main thing on screen.

## Positioning

The agent sees the student's actual code and runs, in VEXcode VR or ZANY, and grounds every reply
in them. A general chatbot beside the editor cannot do that.

## Operating Context

- The page frames the coding environment full screen and floats the chat over it.
- VEXcode VR is framed as research-vr.vex.com, and the student logs into it themselves with the
  same Student ID. ZANY is framed as vr.inviteai.org with the class code and Student ID in the
  link.
- The agent can only help once it sees code, which happens after the student runs a program.
- Check-ins arrive over a live stream and are sent only while the student has the page open.
- Students can rate replies and add a note. Researchers read those.

## Capabilities and Constraints

- Questions, the Help button, check-ins, ratings and notes, spoken questions, and spoken replies.
- The 3D tutor is a Unity build beside the panel. Students can hide it, which pauses Unity, or
  mute it. It stays.
- A Turnstile gate and token budgets protect the API.
- The panel can be dragged and resized, and on a phone it is a sheet along the bottom.

## Brand Commitments

The page looks like ZANY, which looks like VEXcode VR: Open Sans, VEX-blue bars, gold buttons,
the dotted workspace, and ZANY's colour names and values. This is binding, so a student never
sees the style change between the coding space and the agent.

## Evidence on Hand

- Real test conversations in the live database, for the VEXcode VR student `maharsh` and the
  ZANY student `testermega` in class `megaspeed`.
- No student quotes, study results or classroom photos are on hand. Do not invent them.

## Product Principles

1. The code is the star. The agent helps and then gets out of the way.
2. Keep the chat quiet. The first-run steps say when the agent can see the code, and nothing
   else on screen repeats it.
3. Speak to a 12-year-old. Short sentences, plain words, one idea at a time.
4. A student should never be stuck on the agent itself, so every state says what to do next.

## Accessibility & Inclusion

Students read at many levels, and some have the replies read aloud. Text stays large enough to
read on a Chromebook, every control works from the keyboard, and motion respects reduced-motion
settings.
