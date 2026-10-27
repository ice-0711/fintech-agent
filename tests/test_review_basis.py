"""basis_unspecified rule (B 10/24 proposal, lead 10/24 decision): a fact citing a source that does not
say consolidated or standalone must not pass review. Uses the CASE-11 dev snapshot only."""

from agents.review_checks import check_draft
from agents.snapshot import SnapshotToolbox

CUT = "2026-09-30T23:59:00+08:00"


def _draft(ref: str, value: float, text: str) -> dict:
    return {"status": "draft", "decision_summary": "t", "conflicts": [], "limitations": [],
            "claims": [{"claim_id": "c1", "kind": "fact", "text": text, "evidence_refs": [ref], "limitations": [],
                        "facts": [{"metric": "revenue", "value": value, "currency": "TWD", "period": "2026Q2",
                                   "period_basis": "single_quarter", "source_ref": ref}]}]}


def _check(draft: dict) -> dict:
    tb = SnapshotToolbox("2317", "snap-dev-case-11", CUT)
    return check_draft(draft, tb.snapshot_view(), CUT, "snap-dev-case-11")["review"]


def test_case11_flawed_unspecified_basis_is_revised():
    review = _check(_draft("ev-dev-11-no-basis", 25259, "鴻海 2026Q2 個體營收約 25,259 億元"))
    assert review["decision"] != "pass"
    assert any(i["severity"] == "critical" and "口徑" in i["reason"] for i in review["issues"])


def test_consolidated_source_is_not_flagged_for_basis():
    review = _check(_draft("ev-dev-11-consolidated", 2525894433, "鴻海 2026Q2 合併營業收入 2,525,894,433 千元"))
    assert not any("口徑" in i["reason"] for i in review["issues"])
