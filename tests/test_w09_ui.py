"""W09-A: replay list shows Agent v2 runs, labelled by version, for the three demo paths.

Before this change the replay list only had pre-v1 development runs (researcher-v1.2.0/1.2.1), all stopped at
insufficient evidence, with no version label: the "Reviewer asks for more evidence, Researcher revises" demo path
had no recorded run to show, and nothing told a viewer which Agent version a run came from.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from research_ui.replays import DEMO_PATHS, TRACE_FILES, V2, V2_TASK, V2_VARIANT, list_replays

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def ui(tmp_path, clock):
    from test_research_ui import make_app
    return make_app(tmp_path, clock).test_client()


def _researcher_minor(row) -> int:
    return int(row["prompt_versions"]["researcher"].rsplit(".", 1)[1])


def test_every_replay_carries_its_agent_version_and_run_condition(ui):
    rows = ui.get("/api/ui/replays").get_json()["replays"]
    assert rows and all(r["agent_version"] and r["condition"] and r["prompt_versions"] for r in rows)
    v2 = [r for r in rows if r["agent_version"] == V2]
    other = [r for r in rows if r["agent_version"] != V2]
    assert v2, "Agent v2 runs must be available for the demo"
    # v2 = researcher-v1.2.3 and later (handoff/agent-version-changes.md); development runs predate v1 (1.2.2).
    assert all(_researcher_minor(r) >= 3 for r in v2)
    assert all(_researcher_minor(r) < 2 for r in other)


def test_groups_are_contiguous_newest_first_and_task_runs_are_apart_from_variant_runs():
    rows = list_replays()
    order = list(dict.fromkeys(r["group"] for r in rows))
    assert order[:2] == [V2_TASK, V2_VARIANT]
    assert len(order) == len({v["group"] for v in TRACE_FILES.values()})
    blocks = [r["group"] for r in rows]
    # each group forms one contiguous block, so the dropdown's <optgroup>s never interleave
    assert all(blocks[blocks.index(g):blocks.index(g) + blocks.count(g)] == [g] * blocks.count(g) for g in order)
    # from 11/14 the question is sent as `task` (decision 31): those files, and only those, are in the task group
    for rel, meta in TRACE_FILES.items():
        assert (meta["group"] == V2_TASK) == ("題目送 task" in meta["condition"]), rel
    js = (ROOT / "static" / "research.js").read_text(encoding="utf-8")
    assert "<optgroup label=" in js and "r.group ||" in js


def test_new_task_batches_carry_the_lead_conditions():
    rows = {r["replay_id"]: r for r in list_replays()}
    assert rows["calib-v2-rules-check-1115-dual:CASE-04"]["condition"] == \
        "補股價後・題目送 task・11/14 覆核規則修正後（第 35、37、38 節）"
    assert rows["calib-v2-task-rehearsal-1114-dual:CASE-19"]["condition"] == \
        "補股價後・題目送 task・11/14 覆核規則修正前（第 35、37、38 節）"
    assert sum(r.startswith("calib-v2-rules-check-1115-dual:") for r in rows) == 4
    assert sum(r.startswith("calib-v2-task-rehearsal-1114-dual:") for r in rows) == 4


def test_three_demo_paths_use_one_condition_group_and_match_their_records(ui):
    rows = {r["replay_id"]: r for r in ui.get("/api/ui/replays").get_json()["replays"]}
    assert {rows[rid]["group"] for rid in DEMO_PATHS} == {V2_TASK}
    assert [r for r in rows if rows[r]["demo_path"]] and set(r for r in rows if rows[r]["demo_path"]) == set(DEMO_PATHS)

    def rounds(rid):
        return [x["final_decision"] for x in ui.get(f"/api/ui/replays/{rid}").get_json()["review_view"]["rounds"]]

    ok = "calib-v2-rules-check-1115-dual:CASE-04"
    assert rows[ok]["status"] == "succeeded" and rounds(ok) == ["pass"]
    fixed = "calib-v2-task-rehearsal-1114-dual:CASE-19"
    assert rows[fixed]["status"] == "succeeded" and rounds(fixed) == ["revise", "pass"]
    stop = "calib-v2-rules-check-1115-dual:CASE-15"
    assert rows[stop]["status"] == "insufficient_evidence" and rows[stop]["stop_reason"] == "researcher_insufficient"
    r = ui.get(f"/api/ui/replays/{fixed}").get_json()
    assert r["case"]["demo_path"] and r["source"]["group"] == V2_TASK


def test_revise_path_has_a_recorded_v2_run_with_two_review_rounds(ui):
    rows = {r["replay_id"]: r for r in ui.get("/api/ui/replays").get_json()["replays"]}
    rid = "calib-v2-dual-day3:CASE-15"
    assert rows[rid]["review_rounds"] == 2
    r = ui.get(f"/api/ui/replays/{rid}").get_json()
    rounds = r["review_view"]["rounds"]
    assert rounds[0]["final_decision"] == "revise" and rounds[1]["final_decision"] == "insufficient"
    # recorded as it happened: this run ends at insufficient evidence, not a pass
    assert r["job"]["status"] == "insufficient_evidence"
    assert r["source"]["agent_version"] == V2 and r["label"] == "REPLAY"


def test_v2_replays_show_the_frozen_dev_case_cutoff_and_snapshot(ui):
    r = ui.get("/api/ui/replays/calib-v2-dual-day3:CASE-15").get_json()
    assert r["job"]["cutoff_at"] == "2026-08-05T17:00:00+08:00"
    assert r["job"]["source_snapshot_id"] == "snap-dev-case-15"
    old = ui.get("/api/ui/replays/dev-v14-batch1:CASE-15").get_json()
    assert old["job"]["cutoff_at"] is None and old["job"]["source_snapshot_id"] is None  # pre-freeze: not guessed


def test_case04_runs_misjudged_by_since_fixed_rules_are_annotated_and_nothing_else_is(ui):
    rows = ui.get("/api/ui/replays").get_json()["replays"]
    noted = sorted(r["replay_id"] for r in rows if r["record_note"])
    assert noted == ["calib-v2-dual-postprice-1112:CASE-04", "calib-v2-task-rehearsal-1114-dual:CASE-04"]
    old = ui.get("/api/ui/replays/calib-v2-dual-postprice-1112:CASE-04").get_json()
    assert "第 28 節" in old["case"]["record_note"]["note"]
    new = ui.get("/api/ui/replays/calib-v2-task-rehearsal-1114-dual:CASE-04").get_json()
    assert "第 35 節" in new["case"]["record_note"]["note"]
    # the 11/15 rerun under the fixed rule is a normal result: no note; CASE-22 stays as recorded, no note
    fixed = {r["replay_id"]: r for r in rows}
    assert fixed["calib-v2-rules-check-1115-dual:CASE-04"]["record_note"] is None
    assert fixed["calib-v2-rules-check-1115-dual:CASE-22"]["record_note"] is None


def test_replays_never_read_the_sealed_holdout():
    assert all("holdout" not in rel and rel.startswith("agent/") for rel in TRACE_FILES)
