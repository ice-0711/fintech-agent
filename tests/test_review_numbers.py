"""B 10/28 / lead 10/29: a fact's number must appear in what it cites — the snapshot's tool numbers, a tool
observation, or an evidence paragraph — not only when it cites an announcement. Dev snapshot CASE-04 only."""

from agents.review_checks import check_draft, value_matches
from agents.snapshot import SnapshotToolbox

CUT, SNAP = "2026-09-30T17:30:00+08:00", "snap-dev-case-04"


def _review(facts, refs=(SNAP,), observations=None):
    draft = {"status": "draft", "decision_summary": "t", "conflicts": [], "limitations": [],
             "claims": [{"claim_id": "c1", "kind": "fact", "text": "t", "evidence_refs": list(refs), "limitations": [],
                         "facts": facts}]}
    view = SnapshotToolbox("2330", SNAP, CUT).snapshot_view()
    return check_draft(draft, view, CUT, SNAP, observations=observations)["review"]


def _flagged(review):
    return [i for i in review["issues"] if i["severity"] == "critical" and "找不到" in i["reason"]]


def test_snapshot_number_that_matches_passes():
    assert not _flagged(_review([{"metric": "eps_ttm", "value": 86.28, "source_ref": SNAP}]))


def test_snapshot_number_that_does_not_match_is_critical():
    assert _flagged(_review([{"metric": "eps_ttm", "value": 4.27, "source_ref": SNAP}]))


def test_rounded_number_needs_matching_precision():
    assert not value_matches(86.0, [86.28])          # 86 is not 86.28
    assert value_matches(12703.8, [1270380250.0])    # 千元 → 億元, one decimal
    assert value_matches(67.7, [0.6768])              # ratio → percent, rounded


def test_observation_number_is_checked_against_its_result():
    obs = [{"obs_id": "obs-1", "tool_name": "calculate_metrics", "status": "ok", "brief": '{"result": 23.23}'}]
    assert not _flagged(_review([{"metric": "pe_peer", "value": 23.23, "source_ref": "obs-1"}], ("obs-1",), obs))
    assert _flagged(_review([{"metric": "pe_peer", "value": 30.1, "source_ref": "obs-1"}], ("obs-1",), obs))


def test_computed_facts_are_left_to_their_own_rules():
    assert not _flagged(_review([{"metric": "growth", "value": 12.3, "operation": "ratio", "source_ref": SNAP}]))
