"""How the agent teaches: which kinds of feedback fit what the student is doing, what kind of
question a student asked and how to scaffold it, and the prompt that puts it all together.

The feedback classes decide HOW a reply sounds (praise, a hint, a question). The question
type's scaffolding decides WHAT it says next. Proactive check-ins have no question, so they
are steered by the feedback classes alone.
"""

import re
from dataclasses import dataclass
from enum import Enum

from agent.situation import Cognition, Persistence, Snapshot


@dataclass(frozen=True)
class FeedbackSpec:
    name: str
    description: str
    examples: tuple[str, ...]
    notes: tuple[str, ...] = ()


class Feedback(Enum):
    POSITIVE = FeedbackSpec(
        "Positive Feedback",
        "Confirms that the action is fully correct. Clearly identifies what was done correctly and why it works. Focus on the task.",
        (
            "You specified an appropriate distance for the robot to move forward, so it will not fall over the cliff.",
            "You used the [x] block, which allowed the robot to pick up the trash.",
        ),
        (
            "Keep the message concise and specific without excessive praise. Emphasize what makes the text correct and the student's apparent reasoning, rather than their abilities.",
        ),
    )
    PARTIAL_CORRECTNESS = FeedbackSpec(
        "Partial Correctness",
        "Acknowledges what is correct, but also acknowledges what needs adjustment.",
        (
            "You took the correct steps to avoid the debris, but you need to turn right earlier to avoid getting stuck. Make the turn right block appear earlier.",
        ),
        (
            "Start with what works, then address what needs revision. Keep feedback manageable and focused on one or two issues, or keep the feedback more high level.",
        ),
    )
    CORRECTIVE_GUIDANCE = FeedbackSpec(
        "Corrective Guidance",
        "Indicates that the action is incorrect and provides clear guidance on how to fix it.",
        (
            "The move forward command runs for too long, which is why your robot falls off the cliff. Replace the distance with something shorter.",
            "Your if block is always going to be true, so your robot will never turn left.",
        ),
    )
    EVIDENCE_BASED_PRAISE = FeedbackSpec(
        "Evidence-Based Praise",
        "Highlights a specific successful action and explains why it was effective. The goal is to encourage effort based on evidence.",
        (
            "Your use of the conditional if statement allows your agent to move in the correct way without requiring a lot of code.",
            "You cleaned up the trash with very few lines of code.",
        ),
        (
            "Ensure that praise is tied to a specific accomplishment to avoid directing attention to the self.",
            "As long as the student is making progress, validate their work, which is not the same as praise.",
            "Focus on strategies and decisions, not the person.",
        ),
    )
    REASSURE = FeedbackSpec(
        "Reassure",
        "Encourages persistence by reducing student frustration. Validates prior effort and lets them know they are on the right track.",
        (
            "Loops can be tricky. It is very common to have loops run forever until you find the right solution.",
            "You are definitely on the right track and taking the necessary steps. A lot of students struggle with this problem.",
        ),
    )
    ERROR_FLAGGING = FeedbackSpec(
        "Error Flagging",
        "Identifies a specific error clearly and objectively without immediately providing the full solution.",
        (
            "The while statement is always true and will run forever.",
            "You did not connect the two blocks.",
            "The blocks are in the wrong order.",
        ),
        ("Name the exact issue. Avoid framing it around the person.",),
    )
    HOW_TO = FeedbackSpec(
        "How To",
        "Provides step-by-step instructions to do a task or solve the problem.",
        ("To solve the problem of [problem], take steps a, b, c, and n.",),
        (
            "Break the explanation into small steps. Do not overwhelm the student with technical terms.",
        ),
    )
    INFORM = FeedbackSpec(
        "Inform",
        "Provides relevant knowledge about VEX VR components or behavior.",
        ("Changing the speed affects how fast you go and how fast you turn.",),
    )
    NUDGE = FeedbackSpec(
        "Hint",
        "Encourages the learner to examine a specific part of their code without giving an explicit solution.",
        (
            "Check where the stop driving block is placed.",
            "Look at the order of each of your commands.",
        ),
        ("Keep the solution subtle.",),
    )
    DIAGNOSE = FeedbackSpec(
        "Encourage Testing (Diagnose)",
        "Guides the learner to test the behavior of the robot to discover the issue independently.",
        (
            "Does the condition in the while block ever become false?",
            "If you reduce the speed, does turning become more accurate?",
        ),
        ("Encourage experimentation in the VR environment and develop debugging skills.",),
    )
    QUESTION = FeedbackSpec(
        "Question",
        "Provides a focused question to stimulate reasoning about the problem.",
        (
            "How many degrees should the robot turn to face the next obstacle?",
            "At what point does the condition in the block become false?",
        ),
        ("Questions should be purposeful.",),
    )
    ELABORATE = FeedbackSpec(
        "Elaborate",
        "Provides a deeper explanation of why something happens.",
        (
            "The robot misses the item because the drive distance is longer than it should be before turning.",
            "The robot continues turning because the turn block or loop is never false.",
        ),
        ("Do this in small segments.",),
    )
    REMIND = FeedbackSpec(
        "Remind",
        "Restates the robotic goal.",
        (
            "The goal is for the robot to pick up all objects.",
            "Right now, the robot keeps driving because the condition to stop is never met.",
        ),
        ("This is useful when the learner is possibly misunderstanding the task or outcome.",),
    )
    NEXT_STEP = FeedbackSpec(
        "Next Step",
        "Gives a single immediate robotics action to try next.",
        (
            "You could try changing the turn value to 90 degrees and try again.",
            "What if you lower the speed to 75% and test the path?",
        ),
        ("Use this as a last resort.",),
    )


def feedback_for(snap: Snapshot | None) -> set[Feedback]:
    """The feedback classes for what the student is doing (the study's flowchart). A focused
    question when nothing in the flowchart fits."""
    if snap is None:
        return {Feedback.QUESTION}
    cognition, persistence = snap.cognition, snap.persistence
    chosen: set[Feedback] = set()
    if cognition == Cognition.LONG_TERM_STALLED_PROGRESS:
        chosen.add(Feedback.ERROR_FLAGGING)
    elif cognition == Cognition.DEVELOPMENT_INCREASES_PROGRESS:
        chosen.add(Feedback.ELABORATE)
    elif cognition == Cognition.DEVELOPMENT_STATIC_PROGRESS:
        chosen.add(Feedback.REASSURE)
    elif cognition in (Cognition.DEVELOPMENT_DECREASES_PROGRESS, Cognition.SNAP_N_TEST):
        chosen.add(Feedback.INFORM)
    elif cognition == Cognition.TRIAL_AND_ERROR:
        chosen.add(Feedback.PARTIAL_CORRECTNESS)
        extra = {
            Persistence.EXPECTED_COMPLETION: Feedback.EVIDENCE_BASED_PRAISE,
            Persistence.HIGH_PERSISTER: Feedback.REASSURE,
            Persistence.EARLY_QUITTER: Feedback.HOW_TO,
        }.get(persistence)
        if extra:
            chosen.add(extra)
    elif cognition == Cognition.CODE_ABANDONMENT:
        if persistence in (Persistence.EXPECTED_COMPLETION, Persistence.EARLY_QUITTER):
            chosen.add(Feedback.DIAGNOSE)
        elif persistence == Persistence.HIGH_PERSISTER:
            chosen.update({Feedback.REASSURE, Feedback.ELABORATE})
    elif cognition == Cognition.STEP_BY_STEP_ELIMINATION:
        chosen.add(Feedback.NUDGE)
    return chosen or {Feedback.QUESTION}


def feedback_names(chosen: set[Feedback]) -> list[str]:
    return sorted(feedback.value.name for feedback in chosen)


# --- question types (the study's taxonomy) ---


@dataclass(frozen=True)
class QuestionSpec:
    name: str
    definition: str
    include: str
    exclude: str
    scaffolding: str


_EVIDENCE = (
    "Use the Student message as the primary evidence. Use Recent chat, the student's "
    "current program, and What's happening now as supporting context. Treat any goal you "
    "infer as an estimate unless the student confirmed it. Do not invent missing information."
)


class QuestionType(Enum):
    TASK_GOAL = QuestionSpec(
        "Task / Goal Understanding",
        "The student is asking about the meaning of the task or playground, rather than how to code something: what they are supposed to accomplish, what an object/location means, what the rules are, how scoring works, or what counts as success.",
        "Questions about the task goal, mission, scoring, rules, objects, or locations. For example: “what is my goal”; “what’s the main mission?”; “where is the lab”; “is the lab the green area i started in?”; “How many samples can you hold at once”; “Do you get more points if you place the craters on the right color?”",
        "How to code an action, choose a block, improve a strategy, or debug a failure. For example: “how do you tell the bot to lower its arms” → Action / Strategy / Solution Support; “why is my vehicle picking up the object but dropping right away” → Debugging / Problem Diagnosis; “Help” → General / Unclear Help-Seeking.",
        f"""{_EVIDENCE}
Move through these steps across turns:
1. Directly clarify the task fact, rule, object, location, requirement, or success condition the student asked about.
2. Connect the clarification to one immediate goal the student can work on. If that goal is unclear, ask one short goal question instead of assuming it.
3. Identify one observable sign that would show the immediate goal was achieved.
4. Ask one focused question that connects the clarified information to the student's next action.
Do not provide a complete program.""",
    )
    ACTION_STRATEGY = QuestionSpec(
        "Action / Strategy / Solution Support",
        "The student is asking how to make the robot do something or how to build/improve a solution: which block to use, how to perform an action, what a block/code segment does, how to make the robot faster or more efficient, or asking for code.",
        "Which block to use, how to perform an action, what code/block does, how to improve speed/score/efficiency, or code/solution requests. For example: “Which block lets me raise the arms and lower the arms”; “How do i use a sensor block?”; “If i have collected my sample how do i deposit it at the lab”; “what the spin armMotor do”; “how do i make it faster”; “can you give me the code to do it.”",
        "A specific failure or unexpected behavior: “why is it going sidways” → Debugging / Problem Diagnosis. Vague help requests: “Help”; “idk” → General / Unclear Help-Seeking. Task/location/rule questions: “where is the lab” → Task / Goal Understanding.",
        f"""{_EVIDENCE}
First identify what the student is trying to accomplish. If the immediate goal is unclear, ask one short goal question and stop.
Then choose the least specific support that fits the evidence:
1. FIRST RELATED REQUEST: Give a conceptual cue. Explain the programming idea without giving a block sequence, and ask what the next block or pattern must accomplish.
2. AFTER ONE UNSUCCESSFUL RELEVANT ATTEMPT: Name the relevant block family or programming structure, explain why it fits, and give one local test.
3. AFTER REPEATED UNSUCCESSFUL RELEVANT ATTEMPTS: Give a partial sequence, a contrast between two choices, or a small incomplete structure. Leave a meaningful decision to the student.
Use Recent chat and What's happening now to decide whether an attempt occurred; if they don't show one, do not assume an unsuccessful attempt.
After progress, reduce support and ask the student to identify the next step. Never provide the complete program.""",
    )
    DEBUGGING = QuestionSpec(
        "Debugging / Problem Diagnosis",
        "The student reports that their robot, code, or current attempt is not working as expected: a bug, failure, unexpected behavior, or mismatch between intended and actual robot behavior.",
        "A specific problem, bug, failed attempt, unexpected behavior, or mismatch. For example: “That code does not work”; “that still does not work what can i do”; “why is my vehicle picking up the object but dropping right away”; “why is it going sidways”; “how come im getting stuck?”; “What if it is not releasing when spinning the armotor down”; “why does it do that.”",
        "Vague help without describing what is wrong: “Help”; “Idk” → General / Unclear Help-Seeking. Block/action requests without a failure: “which block should i use” → Action / Strategy / Solution Support. Task/goal/location questions: “where is the lab” → Task / Goal Understanding.",
        """Use the Student message and Recent chat as the primary evidence, and the student's current program and What's happening now as measured evidence. Never invent a goal, expected behavior, observed behavior, block, or log event.
Move through these steps across turns, skipping any the recent chat already settled:
1. GOAL: Identify what the student is trying to make the robot accomplish. If unclear, ask one short goal question and stop.
2. EXPECTED: Identify what the student expected at the point of failure.
3. ACTUAL: Restate what actually happened using only available evidence.
4. LOCALIZE: Focus on the first block, transition, condition, loop iteration, movement, or event where actual behavior differs from expected.
5. HYPOTHESIS: Offer one possible explanation supported by the evidence.
6. TEST: Ask the student to change or isolate one thing and observe one result.
7. FOLLOW-UP: Use the next reported result to support or reject the hypothesis before proposing another change.
Do not list many possible bugs or change several values at once. After repeated unsuccessful tests, narrow the code region or give one small incorrect-versus-correct contrast. When the problem is fixed, ask the student to explain why the change worked. Do not provide the complete program.""",
    )
    GENERAL = QuestionSpec(
        "General / Unclear Help-Seeking",
        "Last resort: the message is too vague, short, off-task, or non-substantive to determine a specific need (generic help, “I don't know”, yes/no, unrelated answers, pushing the task back to the agent) with no goal, object, block, action, strategy, or failure named.",
        "Generic help requests, vague uncertainty, or non-substantive/off-task comments. For example: “Help”; “idk”; “I dont know”; “sure”; “Yes”; “2”; “orange”; “that’s your job buddy”; “figure it out”; “hello”; “what did you eat for dinner.”",
        "Any specific goal, object, location, rule, block, action, strategy, solution request, or failure. For example: “where is the lab” → Task / Goal Understanding; “how do i make it faster” → Action / Strategy / Solution Support; “why is it going sidways” → Debugging / Problem Diagnosis.",
        """There is not enough information to tell whether the student needs task clarification, action support, or debugging. Do not state an inferred goal as though the student confirmed it. Do not invent missing information.
Respond calmly and ask one bounded choice question that helps the student say whether they need: help understanding the task or goal; help deciding or coding the next action; or help fixing something that behaved differently than expected.
Do not combine several kinds of scaffolding. The next student message will be classified again.""",
    )


# The classifier answers with the type's number. Unreadable answers fall back to GENERAL.
QUESTION_ORDER = (
    QuestionType.TASK_GOAL,
    QuestionType.ACTION_STRATEGY,
    QuestionType.DEBUGGING,
    QuestionType.GENERAL,
)

CLASSIFIER_PROMPT = """Classify a middle school student's message to a {tool} tutor into exactly one question type.

Question types:
{question_types}

Student message:
{student_message}

Output only the number of the question type (0, 1, 2, or 3). No other text."""


def classifier_prompt(student_message: str, tool: str) -> str:
    types = "\n".join(
        f"{number} = {q.value.name}\n"
        f"  Definition: {q.value.definition}\n"
        f"  Include: {q.value.include}\n"
        f"  Exclude: {q.value.exclude}"
        for number, q in enumerate(QUESTION_ORDER)
    )
    return CLASSIFIER_PROMPT.format(
        tool=tool, question_types=types, student_message=student_message
    )


_DIGIT = re.compile(r"\b([0-3])\b")


def parse_question_type(answer: str | None) -> QuestionType:
    """The first standalone 0 to 3 in the classifier's answer."""
    match = _DIGIT.search(answer or "")
    return QUESTION_ORDER[int(match.group(1))] if match else QuestionType.GENERAL


# --- the reply prompt ---

PROMPT_TEMPLATE = """You are an educational feedback assistant for {tool}.

Your job is to write one short feedback message for the student.

INPUTS

Task:
{task}

Available blocks:
{available_blocks}

Student's current program (parsed from their workspace):
{current_program}

Student message:
{student_message}

Student question type:
{question_type}

Scaffolding for this question type:
{scaffolding}

What's happening now (measured from the session's telemetry):
{situation}

Recent chat in this session:
{recent_chat}

Feedback types to use:
{feedback_types}

Feedback type descriptions:
{descriptions}

Examples of each feedback type:
{examples}

Extra notes:
{extra_notes}

INSTRUCTIONS

Use these sources in this priority order:
1. Student message
2. The student's current program (what blocks are actually on the workspace)
3. What's happening now (the measured telemetry facts)
4. Recent chat
5. Task
6. Scaffolding for the question type
7. Feedback type descriptions/examples/notes

How to combine scaffolding and feedback types:
- The scaffolding decides WHAT to say next; the feedback types decide HOW to say it.
- The scaffolding may describe several steps, but the student sees at most two short sentences. Deliver only the next step that the recent chat has not already covered.

Before writing feedback:
- Use the student's current program as the source of truth for which blocks are on the workspace and how they are connected.
- Use the measured telemetry facts to understand the student's progress, trajectory, and any error the robot reported. These facts are measured, not guessed -- trust them, but do not restate a number the student can already see.
- Only mention a block that appears in the current program. If the current program is empty or unavailable, do not guess or mention a specific block.
- Do not invent actions, errors, goals, or progress that are not supported by the inputs.

How to write the feedback:
- Write for a middle school student.
- Use simple, direct, natural language.
- Be specific and clear.
- Keep feedback as simple as possible, but no simpler.
- Give unbiased, objective feedback.
- Combine ALL listed feedback types into one cohesive message.
- If the feedback types pull in different directions, blend them naturally into one message instead of forcing separate ideas.
- Prefer the most immediately useful next step for the student.

Behavior rules:
- Do not give an overall evaluation or grade.
- Do not discourage the student or threaten self-esteem.
- Use praise sparingly and only if supported by the student's recent work.
- Do not interrupt active productive work with unnecessary advice.
- If the student's input is unclear or vague, ask them to restate their question clearly.
- In extreme cases of long-term struggle or no progress, tell the student to ask their teacher for help.

Block reference rule:
- When referring to a specific block, wrap only the exact block name in backticks.
- Preserve the exact capitalization and wording from the Available blocks list.

OUTPUT RULES
- Output only the feedback message.
- Do not include labels, explanations, bullet points, or quotation marks.
- Prefer one bite-sized hint or explanation over a full paragraph.
- Keep it to 1-2 short sentences.
- Aim for about 20-35 words when possible.
- Never exceed 40 words.
"""

# What each placeholder carries, for researchers editing the template.
PLACEHOLDERS = {
    "tool": "The coding environment, as the prompt names it.",
    "task": "The playground's task description.",
    "available_blocks": "The block catalog for this playground, one block per line.",
    "current_program": "The student's current workspace, rendered as compact pseudo-code.",
    "student_message": "What the student typed (or 'Help').",
    "situation": "Measured telemetry facts: progress, milestones, work pattern, last error.",
    "recent_chat": "The recent chat turns in this session.",
    "question_type": "The question type the classifier gave the student's message.",
    "scaffolding": "The study's scaffolding guidance for that question type.",
    "feedback_types": "The feedback types the policy picked for this turn.",
    "descriptions": "Descriptions of the picked feedback types.",
    "examples": "Examples of the picked feedback types.",
    "extra_notes": "Extra notes for the picked feedback types.",
}

_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def render(template: str, values: dict[str, str]) -> str:
    """Fill the {name} placeholders that have a value and leave everything else as written,
    so a researcher's template can hold stray braces (JSON, code) without breaking."""
    return _PLACEHOLDER.sub(lambda m: values.get(m.group(1), m.group(0)), template)


def build_prompt(
    *,
    template: str,
    tool: str,
    task: str,
    blocks: tuple[str, ...],
    program: str,
    student_message: str,
    question: QuestionType | None,
    situation: str,
    recent_chat: list[dict],
    feedback: set[Feedback],
) -> str:
    specs = sorted((f.value for f in feedback), key=lambda spec: spec.name)
    speaker = {"student": "Student", "agent": "Assistant"}
    chat = "\n".join(f"{speaker[turn['role']]}: {turn['body']}" for turn in recent_chat)
    return render(
        template,
        {
            "tool": tool,
            "task": task,
            "available_blocks": "\n".join(f"- {block}" for block in blocks) or "None provided",
            "current_program": program or "None available (no project snapshot yet)",
            "student_message": student_message,
            "question_type": question.value.name
            if question
            else "None (no student question; this is a proactive check-in)",
            "scaffolding": question.value.scaffolding if question else "None",
            "situation": situation,
            "recent_chat": chat or "None",
            "feedback_types": "\n".join(f"- {s.name}" for s in specs),
            "descriptions": "\n\n".join(f"{s.name}:\n{s.description}" for s in specs),
            "examples": "\n\n".join(
                f"{s.name}:\n" + "\n".join(f"- {e}" for e in s.examples) for s in specs
            ),
            "extra_notes": "\n\n".join(
                f"{s.name}:\n" + ("\n".join(f"- {n}" for n in s.notes) or "None") for s in specs
            ),
        },
    )
