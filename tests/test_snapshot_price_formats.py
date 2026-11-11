"""Price snapshots come in two shapes (lead 11/11): one close at the top level (dev cases) or a `closes` list
with per-row available_at (holdout cases). Synthetic data only; no holdout content is read here."""

from __future__ import annotations

import pytest

from agents import snapshot as snap
from agents.snapshot import SnapshotToolbox

CUTOFF = "2026-09-30T17:30:00+08:00"
ROW1 = {"trade_date": "2026-09-22", "close_price": 100.0, "available_at": "2026-09-22T17:30:00+08:00",
        "available_at_basis": "rule_close_1730"}
ROW2 = {"trade_date": "2026-09-30", "close_price": 110.0, "available_at": "2026-09-30T17:30:00+08:00",
        "available_at_basis": "rule_close_1730"}


def box(monkeypatch, price, cutoff=CUTOFF):
    monkeypatch.setattr(snap, "load_case_snapshot", lambda sid: {"ticker": "2330", "evidences": [], "price_snapshot": price})
    return SnapshotToolbox("2330", "snap-dev-synthetic", cutoff)


def test_closes_list_is_served_latest_first_by_cutoff(monkeypatch):
    price = {"closes": [ROW2, ROW1], "currency": "TWD", "price_basis": "raw_close", "unit": "TWD/share", "source_id": "x"}
    r = box(monkeypatch, price).get_price_window("2330", CUTOFF, 1)
    assert r["status"] == "ok" and r["data"]["closes"] == [{"trade_date": "2026-09-30", "close_price": 110.0}]
    r = box(monkeypatch, price, "2026-09-29T17:00:00+08:00").get_price_window("2330", CUTOFF, 1)
    assert r["data"]["closes"] == [{"trade_date": "2026-09-22", "close_price": 100.0}]  # 09-30 is after this cutoff
    assert box(monkeypatch, price, "2026-09-01T17:00:00+08:00").get_price_window("2330", CUTOFF, 1)["status"] == "no_data"
    assert box(monkeypatch, price).get_price_window("2330", CUTOFF, 5)["status"] == "no_data"  # only 2 sessions


def test_synthetic_adjusted_is_passed_through_unchanged(monkeypatch):
    extra = {"any_key": "any text", "n": [1, 2.5]}  # made-up shape: the tool must not interpret or reword it
    price = {"closes": [ROW1, ROW2], "currency": "TWD", "price_basis": "raw_close", "synthetic_adjusted": extra}
    data = box(monkeypatch, price).get_price_window("2330", CUTOFF, 1)["data"]
    assert data["synthetic_adjusted"] == extra
    assert set(data) == {"ticker", "currency", "price_basis", "sessions", "closes", "synthetic_adjusted", "snapshot_id"}
    del price["synthetic_adjusted"]
    assert "synthetic_adjusted" not in box(monkeypatch, price).get_price_window("2330", CUTOFF, 1)["data"]


def test_single_close_shape_still_works(monkeypatch):
    price = {"trade_date": "2026-09-30", "close_price": 110.0, "eps_ttm": 5.0, "available_at": ROW2["available_at"]}
    r = box(monkeypatch, price).get_price_window("2330", CUTOFF, 1)
    assert r["status"] == "ok" and r["data"]["closes"] == [{"trade_date": "2026-09-30", "close_price": 110.0}]
    assert box(monkeypatch, price).get_price_window("2330", CUTOFF, 5)["status"] == "no_data"


@pytest.mark.parametrize("price", [{"closes": [{"trade_date": "2026-09-30", "close_price": 110.0}]}, {"eps_ttm": 5.0}])
def test_price_without_available_at_is_no_data_not_an_exception(monkeypatch, price):
    assert box(monkeypatch, price).get_price_window("2330", CUTOFF, 1)["status"] == "no_data"


def _pe_codes(price, p):
    from agents.review_checks import check_draft
    draft = {"status": "draft", "decision_summary": "t", "conflicts": [], "limitations": [],
             "claims": [{"claim_id": "c1", "kind": "fact", "text": "t", "evidence_refs": ["snap-dev-synthetic"],
                         "limitations": [], "facts": [{"metric": "pe_ttm", "value": round(p / 5.0, 2),
                                                       "inputs": {"price": p, "eps_ttm": 5.0},
                                                       "source_ref": "snap-dev-synthetic"}]}]}
    view = {"ticker": "2330", "evidences": [], "price_snapshot": price, "tool_numbers": [p, 5.0, round(p / 5.0, 2)]}
    out = check_draft(draft, view, CUTOFF, "snap-dev-synthetic")
    return [t for t in out["trace"] if "pe_input_mismatch" in str(t)], out["review"]["issues"]


def test_pe_input_check_accepts_a_listed_close_and_rejects_others():
    price = {"closes": [ROW1, ROW2]}
    assert not any("不一致" in i["reason"] for i in _pe_codes(price, 110.0)[1])
    assert any("不一致" in i["reason"] for i in _pe_codes(price, 123.0)[1])
    single = {"trade_date": "2026-09-30", "close_price": 110.0, "eps_ttm": 5.0, "available_at": ROW2["available_at"]}
    assert not any("不一致" in i["reason"] for i in _pe_codes(single, 110.0)[1])
    assert any("不一致" in i["reason"] for i in _pe_codes(single, 123.0)[1])
