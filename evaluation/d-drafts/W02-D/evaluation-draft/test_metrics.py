"""W02-D 草稿：用 5 個範例驗證各指標的分子、分母與 NA 處理。
預期值都是 D 先用手算出來，再寫進測試，不是拿程式的輸出反推。
全部離線，不呼叫模型。
"""

import csv
import io
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import metrics as m  # noqa: E402
import mock_runner as r  # noqa: E402


# ---- 範例1：全部有支持 ----
def test_example1_all_supported():
    out = m.evidence_support_rate(["supported"] * 3)
    assert (out["numerator"], out["denominator"], out["na_count"]) == (3, 3, 0)
    assert out["value"] == 1.0


# ---- 範例2：有不支持、也有 unknown；unknown 留在分母、不當 supported ----
def test_example2_unknown_stays_in_denominator():
    out = m.evidence_support_rate(["supported", "supported", "unsupported", "unknown"])
    assert (out["numerator"], out["denominator"]) == (2, 4)  # 2/4
    assert out["value"] == 0.5
    assert out["unsupported_count"] == 1
    assert out["unknown_count"] == 1


# ---- 範例3：沒有任何主張（例如 CASE-13 合理停止）要回 NA，不是 0 ----
def test_example3_no_claims_is_NA_not_zero():
    out = m.evidence_support_rate([])
    assert out["value"] is None and out["status"] == "NA"
    assert out["value"] != 0
    only_unscored = m.evidence_support_rate([None, None])
    assert only_unscored["na_count"] == 2
    assert only_unscored["value"] is None and only_unscored["denominator"] == 0


def test_invalid_label_rejected():
    with pytest.raises(ValueError):
        m.evidence_support_rate(["supported", "maybe"])


# ---- 範例4：植入錯誤檢出率與誤報率分開算 ----
def test_example4_planted_detection_and_false_alarm():
    cases = [
        {"case_id": "A", "planted": ["e1", "e2"], "flagged": ["e1"]},       # 檢出 1/2
        {"case_id": "B", "planted": ["e3"], "flagged": ["e3", "e9"]},       # 檢出 1/1（e9 是多報，不影響分子）
        {"case_id": "C", "planted": [], "flagged": []},                      # 乾淨案例，沒誤報
        {"case_id": "D", "planted": [], "flagged": ["e7"]},                  # 乾淨案例，誤報
    ]
    out = m.planted_error_detection(cases)
    assert (out["numerator"], out["denominator"]) == (2, 3)  # 2/3
    fa = out["false_alarm"]
    assert (fa["numerator"], fa["denominator"]) == (1, 2)  # 1/2
    assert fa["value"] == 0.5


def test_no_planted_errors_is_NA():
    out = m.planted_error_detection([{"case_id": "C", "planted": [], "flagged": []}])
    assert out["value"] is None and out["status"] == "NA"
    assert out["false_alarm"]["value"] == 0.0  # 分母是 1，這個 0 是真的 0


def test_fix_rate_and_NA():
    out = m.fix_rate({"a", "b", "c"}, {"b"})
    assert (out["numerator"], out["denominator"]) == (2, 3)
    assert m.fix_rate([], [])["value"] is None


# ---- 範例5：合理拒答、作業成功率、成本都不能把缺值變成 0 ----
def test_example5_refusal_job_success_cost():
    runs = [
        {"case_id": "CASE-13", "data_sufficient": False, "decision": "insufficient", "states_gap": True},
        {"case_id": "CASE-14", "data_sufficient": False, "decision": "pass", "states_gap": False},
        {"case_id": "CASE-01", "data_sufficient": True, "decision": "insufficient", "states_gap": True},
    ]
    ref = m.reasonable_refusal_rate(runs)
    assert (ref["numerator"], ref["denominator"]) == (1, 2)
    assert ref["refused_when_sufficient"] == ["CASE-01"]

    jobs = m.job_success_rate(["succeeded", "succeeded", "failed", "timed_out", "paused_quota"])
    assert (jobs["numerator"], jobs["denominator"]) == (2, 5)  # 失敗與逾時留在分母
    assert jobs["status_counts"]["failed"] == 1

    cost = m.cost_perf([1000, None, 3000])
    assert cost["n"] == 2 and cost["na_count"] == 1 and cost["mean"] == 2000
    no_bill = m.cost_perf([None, None])
    assert no_bill["mean"] is None and no_bill["status"] == "NA"  # 沒有帳單不能填 0


def test_citation_rate():
    out = m.citation_resolvable_rate([True, True, False, None])
    assert (out["numerator"], out["denominator"], out["na_count"]) == (2, 3, 1)


# ---- mock runner：模式可辨識、標明 mock、不新增 LLM 樣本 ----
CASES = [
    {"case_id": "CASE-01", "allow_insufficient": False},
    {"case_id": "CASE-13", "allow_insufficient": True},
]


def test_runner_modes_identifiable_and_mock():
    runs = r.make_runs(CASES)
    assert len(runs) == 2 * 3
    assert {x["mode"] for x in runs} == {"workflow", "single", "dual"}
    assert all(x["run_kind"] == "mock" and x["llm_calls"] == 0 for x in runs)
    by_id = {x["run_id"]: x for x in runs}
    assert by_id["CASE-13-single"]["decision"] == "insufficient"
    assert by_id["CASE-01-dual"]["decision"] == "pass"


def test_runner_rejects_unknown_mode():
    with pytest.raises(ValueError):
        r.make_runs(CASES, modes=("workflow", "turbo"))


def test_anonymize_hides_mode_and_keeps_key():
    runs = r.make_runs(CASES)
    blind, key = r.anonymize(runs, seed=1)
    text = json.dumps(blind, ensure_ascii=False)
    assert "workflow" not in text and "single" not in text and "dual" not in text
    assert "mode" not in blind[0]
    assert sorted(key.values()) == sorted(x["run_id"] for x in runs)
    again, _ = r.anonymize(runs, seed=1)
    assert again == blind  # 同一個 seed 結果可重現


def test_score_sheet_blank_label_is_NA():
    blind = [{"blind_id": "R001", "case_id": "CASE-01", "decision": "pass",
              "claims": [{"claim_id": "c1"}, {"claim_id": "c2"}]}]
    sheet = r.blank_score_sheet(blind, scorer="D")
    rows = list(csv.DictReader(io.StringIO(sheet)))
    assert len(rows) == 2 and all(x["label"] == "" for x in rows)
    out = m.evidence_support_rate([x["label"] or None for x in rows])
    assert out["na_count"] == 2 and out["value"] is None  # 還沒標，不能算 0


def test_validate_score_rows():
    good = {"blind_id": "R001", "scorer": "D", "claim_id": "c1", "label": "supported",
            "severity": "", "reason": "", "required_evidence": ""}
    assert r.validate_score_rows([good]) == []
    bad_label = dict(good, label="maybe")
    bad_critical = dict(good, label="unsupported", severity="critical", reason="", required_evidence="")
    errs = r.validate_score_rows([bad_label, bad_critical])
    assert len(errs) == 2
