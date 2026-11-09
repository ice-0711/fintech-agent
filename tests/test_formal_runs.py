"""W10 formal runner (lead 11/09). Offline, 0 LLM. Assertions compare key sets and IDs only, so a failure never
prints holdout content."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import formal_runs as fr  # noqa: E402


def test_holdout_loader_keeps_execution_fields_only():
    cases = fr.load_holdout()
    assert len(cases) == 20
    keys = set().union(*[c.keys() for c in cases.values()])
    assert keys <= set(fr.RUN_FIELDS)
    assert not any(k.startswith("expected") or k in ("allow_insufficient", "perturbation_location") for k in keys)


def test_plan_is_fixed_balanced_and_complete():
    ids = list(fr.load_holdout())
    a, b = fr.make_plan(ids), fr.make_plan(ids)
    assert a == b and a["n_runs"] == 60 and a["quota_days"] == 10
    pairs = {(r["case_id"], r["mode"]) for r in a["runs"]}
    assert len(pairs) == 60 and {c for c, _ in pairs} == set(ids)
    for day in range(1, 11):  # every quota day holds two whole cases, all three modes each
        runs = [r for r in a["runs"] if r["quota_day_index"] == day]
        assert len(runs) == 6 and all(sum(1 for r in runs if r["mode"] == m) == 2 for m in fr.MODES)
    firsts = [a["runs"][i]["mode"] for i in range(0, 60, 3)]
    assert all(firsts.count(m) in (6, 7) for m in fr.MODES)  # starting mode rotates


def test_rows_carry_no_draft_or_review():
    row = fr.row_for({"run_id": "x", "case_id": "CASE-00", "mode": "dual", "seq": 1},
                     {"job_id": "j", "status": "succeeded", "draft": {"claims": []}, "review": {}, "steps": []},
                     "m", "c", "t")
    assert not {"draft", "review", "claims"} & set(row)


def test_live_refused_until_stage2_locked(monkeypatch, capsys):
    import json
    fm = json.loads((ROOT / "data" / "v12-frozen-manifest.json").read_text(encoding="utf-8"))
    if fm["freeze_stages"]["stage2"].get("locked"):
        return  # after 11/13 the guard is exercised by --verify --strict instead
    assert fr.lock_ok() is False
