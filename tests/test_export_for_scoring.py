"""W11 blind export (lead 11/11). Offline; synthetic jobs on DEV cases only, never holdout content."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import export_for_scoring as ex  # noqa: E402
import formal_runs as fr  # noqa: E402

DEV = {c["case_id"]: c for c in json.loads((ROOT / "evaluation" / "dev-cases.json").read_text(encoding="utf-8"))["cases"]}
CASES = ["CASE-01", "CASE-04", "CASE-08"]


@pytest.fixture
def env(tmp_path, monkeypatch):
    plan = fr.make_plan(CASES)
    (tmp_path / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    monkeypatch.setattr(fr, "PLAN", tmp_path / "plan.json")
    monkeypatch.setattr(fr, "RUNS", tmp_path / "runs.jsonl")
    monkeypatch.setattr(fr, "load_holdout", lambda: {c: {k: DEV[c][k] for k in fr.RUN_FIELDS if k in DEV[c]} for c in CASES})
    monkeypatch.setattr(ex, "OUT", tmp_path / "out")
    monkeypatch.setattr(ex, "KEY", tmp_path / "key.json")
    db = tmp_path / "jobs.sqlite3"
    con = sqlite3.connect(db)
    con.execute("create table research_jobs (job_id text, data text)")
    rows = []
    for r in plan["runs"]:
        jid = f"job-{r['seq']}"
        failed = r["seq"] == 2
        draft = None if failed else {
            "status": "draft", "decision_summary": "S", "next_signals": ["下次財報"],
            "claims": [{"claim_id": "c1", "kind": "fact", "text": "T", "evidence_refs": ["obs-1", "ev-dev-01-official-1"]}]}
        job = {"job_id": jid, "mode": r["mode"], "status": "failed" if failed else "succeeded",
               "stop_reason": "review_pass", "review": {"decision": "pass"}, "draft": draft,
               "checkpoint": {"observations": [
                   {"obs_id": "obs-1", "role": "researcher", "tool_name": "get_financial_snapshot", "status": "ok", "brief": "EPS 27.25",
                    "data": {"eps_ttm": 86.28, "ttm_periods": ["2025Q3", "2025Q4", "2026Q1", "2026Q2"]}},
                   {"obs_id": "obs-2", "role": "reviewer", "tool_name": "read_evidence", "status": "ok", "brief": "REVIEWER"}]}}
        con.execute("insert into research_jobs values (?, ?)", (jid, json.dumps(job, ensure_ascii=False)))
        rows.append({"run_id": r["run_id"], "case_id": r["case_id"], "mode": r["mode"], "job_id": jid,
                     "status": job["status"], "stop_reason": "review_pass"})
    con.commit()
    con.close()
    (tmp_path / "runs.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rows), encoding="utf-8")
    return tmp_path, db


def test_export_blinds_modes_and_commits_to_the_key(env):
    tmp, db = env
    commit = ex.export(db=db)
    answers = [json.loads(line) for line in (tmp / "out" / "answers.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(answers) == 9 and len({a["answer_id"] for a in answers}) == 9
    text = (tmp / "out" / "answers.jsonl").read_text(encoding="utf-8") + (tmp / "out" / "answers.md").read_text(encoding="utf-8")
    for leak in ("single", "dual", "workflow", "review_pass", "REVIEWER", "formal-v2-"):
        assert leak not in text
    assert hashlib.sha256((tmp / "key.json").read_bytes()).hexdigest() == commit["key_sha256"]
    key = json.loads((tmp / "key.json").read_text(encoding="utf-8"))["key"]
    assert {k["answer_id"] for k in key} == {a["answer_id"] for a in answers}
    a = next(x for x in answers if x["draft"])
    assert a["cited_observations"] == [{"obs_id": "obs-1", "found": True, "tool": "get_financial_snapshot",
                                         "status": "ok", "result_brief": "EPS 27.25",
                                         "result_data": {"eps_ttm": 86.28, "ttm_periods": ["2025Q3", "2025Q4", "2026Q1", "2026Q2"]}}]
    assert a["draft"]["next_signals"] == ["下次財報"]
    assert sum(1 for x in answers if x["draft"] is None) == 1  # the failed run is kept, not dropped
    for who in ("B", "D"):
        assert (tmp / "out" / f"score-template-{who}.txt").exists()


def test_export_refuses_incomplete_runs_and_second_export(env):
    tmp, db = env
    lines = (tmp / "runs.jsonl").read_text(encoding="utf-8").splitlines()
    (tmp / "runs.jsonl").write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        ex.export(db=db)
    ex.export(partial=True, db=db)
    with pytest.raises(SystemExit):
        ex.export(partial=True, db=db)


def test_reveal_needs_both_scores_and_a_matching_key(env):
    tmp, db = env
    ex.export(db=db)
    with pytest.raises(SystemExit):
        ex.reveal()
    (tmp / "out" / "scores-B.txt").write_text("b", encoding="utf-8")
    (tmp / "out" / "scores-D.txt").write_text("d", encoding="utf-8")
    (tmp / "key.json").write_text("{}", encoding="utf-8")  # tampered key
    with pytest.raises(SystemExit):
        ex.reveal()


def test_export_shows_scorers_the_task_and_the_fields_given_to_the_agent(env, monkeypatch):
    """Decision 31. Synthetic values: the task and as-is fields the Agent got, and required_elements for scorers only."""
    tmp, db = env
    monkeypatch.setattr(fr, "load_holdout", lambda: {c: {**{k: DEV[c][k] for k in fr.RUN_FIELDS if k in DEV[c]}, "task": "合成題目"}
                                                     for c in CASES})
    monkeypatch.setattr(ex, "load_case_snapshot", lambda sid: {"task_input": {"n": 1}, "required_elements": ["SYN-EL"],
                                                               "perturbation": "NOT-EXPORTED"})
    ex.export(db=db)
    answers = [json.loads(line) for line in (tmp / "out" / "answers.jsonl").read_text(encoding="utf-8").splitlines()]
    assert all(a["given_to_agent"] == {"task": "合成題目", "task_input": {"n": 1}} for a in answers)
    assert all(a["scorer_only"] == {"required_elements": ["SYN-EL"]} for a in answers)
    md = (tmp / "out" / "answers.md").read_text(encoding="utf-8")
    assert "給 Agent 的 task：合成題目" in md and "只給評分者的 required_elements（沒有給 Agent）" in md
    assert "NOT-EXPORTED" not in md


def test_score_templates_carry_rubric_rows_and_the_file_name_reveal_expects(env):
    """11/16（B 提出，決策 42）：rubric 第六節的植入錯誤、拒答兩欄每份答卷都有；表頭寫明 --reveal 認的檔名。"""
    tmp, db = env
    ex.export(db=db)
    for who in ("B", "D"):
        text = (tmp / "out" / f"score-template-{who}.txt").read_text(encoding="utf-8")
        n = text.count(" | 案例: ")
        assert n == 9
        assert text.count("植入錯誤: 預期") == n and text.count("拒答: 是否選 insufficient") == n
        assert f"scores-{who}" in text
        for leak in ("single", "dual", "workflow", "formal-v2-"):
            assert leak not in text
