"""W09 (lead 11/06): what a draft says happened to its tools must be in the trace (calibration v1: S30, S17, S27),
the stop reason comes from the trace, and digested tool results tell the model it can read them again."""

from agents.research_graph import shrink_history
from agents.review_checks import unsupported_system_claims

PRICE_NOT_CALLED = {"decision_summary": "已取得部分財務快照，但來源文章與價格視窗工具皆無資料，關鍵事實不足", "claims": []}
OBS_SNAPSHOT_ONLY = [{"tool_name": "search_evidence", "status": "no_data"}, {"tool_name": "get_financial_snapshot", "status": "ok"}]


def test_no_data_for_a_tool_that_was_never_called_is_flagged():  # S30, CASE-04 dual 85c6b6c1
    assert unsupported_system_claims(PRICE_NOT_CALLED, OBS_SNAPSHOT_ONLY, set())


def test_no_data_that_really_happened_is_not_flagged():
    obs = OBS_SNAPSHOT_ONLY + [{"tool_name": "get_price_window", "status": "no_data"}]
    assert not unsupported_system_claims(PRICE_NOT_CALLED, obs, set())


def test_timeout_needs_a_timed_out_tool():  # S17, CASE-26 single 173860b7
    draft = {"decision_summary": "因 read_evidence 逾時，證據不足", "claims": []}
    assert unsupported_system_claims(draft, OBS_SNAPSHOT_ONLY, set())
    timed_out = [{"tool_name": "read_evidence", "status": "tool_error", "reason": "TimeoutError: 模擬逾時"}]
    assert not unsupported_system_claims(draft, timed_out, set())


def test_truncation_and_tools_off_need_the_system_event():
    draft = {"decision_summary": "財務快照資料遭截斷，且無法再呼叫工具", "claims": []}
    assert len(unsupported_system_claims(draft, OBS_SNAPSHOT_ONLY, set())) == 1  # one sentence, first rule wins
    assert not unsupported_system_claims(draft, OBS_SNAPSHOT_ONLY, {"digested", "tools_off"})


def test_ordinary_text_is_not_flagged():
    draft = {"decision_summary": "2026Q2 營收 25,258.94 億元，與財報快照一致", "limitations": ["缺同日股價，P/E 不可算"],
             "claims": [{"text": "TTM EPS 86.28", "limitations": []}]}
    assert not unsupported_system_claims(draft, OBS_SNAPSHOT_ONLY, set())


def test_digested_result_says_it_can_be_read_again():
    from google.genai import types
    obs = [{"obs_id": "obs-1", "digest": "{...}"}]
    part = types.Part.from_function_response(name="get_financial_snapshot", response={"obs_id": "obs-1", "status": "ok", "data": {}})
    contents = [types.Content(role="user", parts=[part]), types.Content(role="user", parts=[types.Part.from_text(text="x")])]
    assert shrink_history(contents, obs) == 1
    assert "重新呼叫" in contents[0].parts[0].function_response.response["note"]
