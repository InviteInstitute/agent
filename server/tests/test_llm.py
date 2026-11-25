import pytest

from agent import llm
from agent.pedagogy import QuestionType, parse_question_type


def test_trim_keeps_two_short_sentences_and_drops_a_third():
    text = "You're off to a good start! Try running it and watch where it stops. Then fix it."
    assert llm.trim(text) == "You're off to a good start! Try running it and watch where it stops."


def test_trim_ends_a_long_sentence_at_a_clause_break():
    long = "When the robot reaches the crater, " + "it keeps driving forward " * 10 + "and falls."
    trimmed = llm.trim(long)
    assert len(trimmed.split()) <= llm.MAX_WORDS
    assert trimmed == "When the robot reaches the crater."


def test_sanitize_removes_leaks_only():
    assert llm.sanitize('"Encouragement: loops can be tricky."') == "Loops can be tricky."
    assert llm.sanitize("Student, check your `turn` block.") == "Check your `turn` block."
    assert llm.sanitize("<think>hmm</think>Check the arm.") == "Check the arm."
    assert llm.sanitize("Check the arm: is it down?") == "Check the arm: is it down?"


def test_strip_thinking_when_the_template_opened_the_tag():
    assert llm.strip_thinking("reasoning here</think>\nThe answer.").strip() == "The answer."
    assert llm.strip_thinking("<think>cut off mid thought") == ""


def test_a_model_that_must_reason_is_asked_again_and_remembered(fake_llm):
    fake = fake_llm("", "First answer.", "Second answer.")
    spent: list[int] = []
    assert llm.complete("muse-glimmer-30b", "p", max_tokens=240, spent=spent) == "First answer."
    assert spent == [100, 100]
    assert fake.calls[0]["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}
    assert fake.calls[1]["reasoning_effort"] == "low"
    assert fake.calls[1]["max_tokens"] == 240 + llm.REASONING_BUDGET_TOKENS
    # Next time it gets the room at once.
    assert llm.complete("muse-glimmer-30b", "p", max_tokens=240, spent=spent) == "Second answer."
    assert len(fake.calls) == 3 and fake.calls[2]["reasoning_effort"] == "low"


def test_no_answer_at_all_raises_with_the_tokens_it_spent(fake_llm):
    fake_llm("", "")
    spent: list[int] = []
    with pytest.raises(llm.EmptyAnswer) as raised:
        llm.complete("qwen3.8-27b", "p", spent=spent)
    assert raised.value.tokens == 200 and spent == [100, 100]


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("2", QuestionType.DEBUGGING),
        ("Type: 0", QuestionType.TASK_GOAL),
        ("I think 1.", QuestionType.ACTION_STRATEGY),
        ("no idea", QuestionType.GENERAL),
        (None, QuestionType.GENERAL),
    ],
)
def test_the_classifier_answer_is_read_as_a_number(answer, expected):
    assert parse_question_type(answer) == expected
