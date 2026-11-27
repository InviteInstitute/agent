"""The analysis end to end on the 27 scenario sessions: each fixture is a GO-Mars session built
to land in one work pattern and persistence category, and so in one set of feedback classes."""

import pytest

from agent import environments
from agent.pedagogy import Feedback, feedback_for
from agent.situation import Cognition, Persistence, describe, snapshot
from tests.conftest import FIXTURES, events_of

F = Feedback
EXPECTED = {
    "01": (Cognition.LONG_TERM_STALLED_PROGRESS, Persistence.IN_PROGRESS, {F.ERROR_FLAGGING}),
    "02": (
        Cognition.DEVELOPMENT_INCREASES_PROGRESS,
        Persistence.EXPECTED_COMPLETION,
        {F.ELABORATE},
    ),
    "03": (Cognition.DEVELOPMENT_STATIC_PROGRESS, Persistence.IN_PROGRESS, {F.REASSURE}),
    "04": (Cognition.DEVELOPMENT_DECREASES_PROGRESS, Persistence.IN_PROGRESS, {F.INFORM}),
    "05": (Cognition.TRIAL_AND_ERROR, Persistence.IN_PROGRESS, {F.PARTIAL_CORRECTNESS}),
    "06": (
        Cognition.TRIAL_AND_ERROR,
        Persistence.EXPECTED_COMPLETION,
        {F.PARTIAL_CORRECTNESS, F.EVIDENCE_BASED_PRAISE},
    ),
    "07": (
        Cognition.TRIAL_AND_ERROR,
        Persistence.HIGH_PERSISTER,
        {F.PARTIAL_CORRECTNESS, F.REASSURE},
    ),
    "08": (Cognition.CODE_ABANDONMENT, Persistence.EXPECTED_COMPLETION, {F.DIAGNOSE}),
    "09": (Cognition.CODE_ABANDONMENT, Persistence.HIGH_PERSISTER, {F.REASSURE, F.ELABORATE}),
}
# 04_inform_c is the snap-and-test variant of Inform.
EXCEPTIONS = {"04_inform_c.ndjson": Cognition.SNAP_N_TEST}

GO_MARS = environments.all_environments()["vexcode-vr"].playground("GO-Mars")


@pytest.mark.parametrize("name", sorted(p.name for p in (FIXTURES / "vexcode_vr").glob("*.ndjson")))
def test_each_scenario_gets_its_feedback(name):
    cognition, persistence, feedback = EXPECTED[name[:2]]
    snap = snapshot(events_of(name), GO_MARS)
    assert snap.playground == "GO-Mars"
    assert snap.cognition == EXCEPTIONS.get(name, cognition)
    assert snap.persistence == persistence
    assert feedback_for(snap) == feedback


def test_the_situation_is_measured_facts_in_words():
    events = events_of("02_elaborate_a.ndjson")
    text = describe(snapshot(events, GO_MARS), events, GO_MARS)
    assert text.startswith("Goal progress:")
    assert "Milestones done:" in text or "Still to do:" in text
    assert "run(s) so far" in text
    assert "DEVELOPMENT" not in text  # never an internal label


def test_no_events_means_no_snapshot_and_a_question():
    assert snapshot([], GO_MARS) is None
    assert describe(None, [], GO_MARS) == "None"
    assert feedback_for(None) == {F.QUESTION}


def test_a_playground_with_no_score_skips_the_progress_rules():
    events = events_of("01_error_flagging_a.ndjson")  # a long, stalled session
    snap = snapshot(events, None)
    assert snap.progress_pct is None
    assert snap.cognition != Cognition.LONG_TERM_STALLED_PROGRESS
    assert snap.persistence == Persistence.IN_PROGRESS
    assert not describe(snap, events, None).startswith("Goal progress")
