"""scripts/scores_to_csv.py：盲評紀錄轉 CSV 的格式檢查（只用合成資料，不讀保留集）。"""
from __future__ import annotations

import ast
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import scores_to_csv as s2c  # noqa: E402

FILLED = """正式評估 v2 盲評紀錄（B）。
A-001 | 案例: CASE-90
  c1(fact): 標註: supported   理由: 營收與快照一致，單季
  c2(fact): 標註: unsupported   理由: 單季當 TTM
  c3(inference): 標註:   理由:
  引用可解析數/總數: 2/3
  植入錯誤: 預期1 指出1 修正0
  拒答: 否 說明缺口: 否
  整體結果: 不符合預期   理由: 口徑錯誤未修正
  備註: 無

A-002 | 案例: CASE-91
  c1: unknown  理由: 來源讀不到
  c2(unknown類): 不計分,草稿自述缺資料
  引用可解析數/總數: 0/1
  整體結果: 符合預期   理由: 有說明缺口
  停止原因與執行紀錄: 這行不讀
  備註:

A-003 | 案例: CASE-92
  c1(fact): 標註:   理由:
  引用可解析數/總數:
  整體結果: 符合預期 / 不符合預期   理由:
"""


def test_filled_answers_parse_with_denominators():
    answers, errors = s2c.parse(FILLED)
    assert [e for e in errors if e.startswith(("A-001", "A-002"))] == []
    a1, a2 = answers[0], answers[1]
    assert [c["label"] for c in a1["claims"]] == ["supported", "unsupported", "不計分"]
    assert [c["scored"] for c in a1["claims"]] == [True, True, False]
    assert a1["cites"] == (2, 3) and a1["inject"] == (1, 1, 0) and a1["refuse"] == ("否", "否")
    assert a2["claims"][1]["scored"] is False and a2["inject"] is None


def test_unfilled_template_is_rejected():
    _, errors = s2c.parse(FILLED)
    a3 = [e for e in errors if e.startswith("A-003")]
    assert any("c1" in e and "標註" in e for e in a3)
    assert any("引用可解析數" in e for e in a3)
    assert any("整體結果" in e for e in a3)


def test_uncertain_label_and_impossible_citation_count_are_errors():
    text = "X-1 | 案例: CASE-93\n  c1: 不確定  理由: 待核\n  引用可解析數/總數: 3/2\n  整體結果: 不確定\n"
    _, errors = s2c.parse(text)
    assert any("c1" in e for e in errors)
    assert any("大於總數" in e for e in errors)
    assert any("整體結果" in e for e in errors)


def test_duplicate_answer_ids_are_errors():
    text = ("D-1 | 案例: CASE-94\n  引用可解析數/總數: 0/0\n  整體結果: 符合預期\n"
            "D-1 | 案例: CASE-94\n  引用可解析數/總數: 0/0\n  整體結果: 符合預期\n")
    _, errors = s2c.parse(text)
    assert any("重複" in e for e in errors)


def test_main_writes_only_requested_cases_and_counts(tmp_path):
    src = tmp_path / "scores-B.txt"
    src.write_text(FILLED, encoding="utf-8")
    rc = s2c.main([str(src), "--cases", "CASE-90,CASE-91", "--batch", "batch1", "--out-dir", str(tmp_path)])
    assert rc == 0
    rows = list(csv.DictReader((tmp_path / "v12-batch1-scores.csv").open(encoding="utf-8")))
    assert [r["answer_id"] for r in rows] == ["A-001", "A-002"]
    assert rows[0]["claims_scored"] == "2" and rows[0]["supported"] == "1" and rows[0]["unsupported"] == "1"
    assert rows[1]["unknown"] == "1" and rows[1]["inject_expected"] == "NA"
    ratings = list(csv.DictReader((tmp_path / "ratings-B-batch1.csv").open(encoding="utf-8")))
    assert len(ratings) == 5 and {r["rater"] for r in ratings} == {"B"}
    assert b"\r" not in (tmp_path / "ratings-B-batch1.csv").read_bytes()


def test_main_refuses_when_a_case_has_no_answer_or_errors(tmp_path):
    src = tmp_path / "scores-B.txt"
    src.write_text(FILLED, encoding="utf-8")
    assert s2c.main([str(src), "--cases", "CASE-90,CASE-99", "--batch", "batch1", "--out-dir", str(tmp_path)]) == 1
    assert s2c.main([str(src), "--cases", "CASE-92", "--batch", "batch1", "--out-dir", str(tmp_path)]) == 1
    assert not (tmp_path / "v12-batch1-scores.csv").exists()


def _real_template():
    """組長匯出程式的 template()，只用 ast 取出這一個函式（不 import 整支程式，避免載入 Agent 套件）。"""
    src = (Path(__file__).resolve().parents[1] / "scripts" / "export_for_scoring.py").read_text(encoding="utf-8")
    node = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "template")
    ns: dict = {}
    exec(compile(ast.Module([node], []), "export_for_scoring.template", "exec"), ns)
    return ns["template"]


def _fake_answers():
    return [{"answer_id": f"Z-{i:03d}", "case_id": f"CASE-9{i}",
             "draft": {"claims": [{"claim_id": "c1", "kind": "fact"}, {"claim_id": "c2", "kind": "inference"}]}}
            for i in range(2)]


def test_real_template_unfilled_is_rejected_row_by_row():
    text = _real_template()(_fake_answers(), "B")
    _, errors = s2c.parse(text)
    z0 = [e for e in errors if e.startswith("Z-000")]
    assert any("c1" in e for e in z0)
    assert any("植入錯誤未填完" in e for e in z0)
    assert any("拒答未填完" in e for e in z0)
    assert any("引用可解析數" in e for e in z0)
    assert any("整體結果" in e for e in z0)


def test_real_template_filled_parses_new_rows(tmp_path):
    text = _real_template()(_fake_answers(), "B")
    text = (text.replace("c1(fact): 標註:   理由: ", "c1(fact): 標註: supported   理由: 與快照一致")
                .replace("c2(inference): 標註:   理由: ", "c2(inference): 標註: 不計分   理由: 推論")
                .replace("引用可解析數/總數: ", "引用可解析數/總數: 2/2")
                .replace("植入錯誤: 預期   個、被指出   個、修正   個", "植入錯誤: 預期 1 個、被指出 1 個、修正 0 個")
                .replace("拒答: 是否選 insufficient: 是 / 否   是否說明缺口: 是 / 否",
                         "拒答: 是否選 insufficient: 否   是否說明缺口: 否")
                .replace("整體結果: 符合預期 / 不符合預期   理由: ", "整體結果: 符合預期   理由: 測試"))
    answers, errors = s2c.parse(text)
    assert errors == []
    assert answers[0]["inject"] == (1, 1, 0) and answers[0]["refuse"] == ("否", "否")
    src = tmp_path / "scores-B.txt"
    src.write_text(text, encoding="utf-8")
    assert s2c.main([str(src), "--cases", "CASE-90,CASE-91", "--batch", "batch1", "--out-dir", str(tmp_path)]) == 0
    rows = list(csv.DictReader((tmp_path / "v12-batch1-scores.csv").open(encoding="utf-8")))
    assert rows[0]["inject_expected"] == "1" and rows[0]["chose_insufficient"] == "否"


def test_batches_follow_run_plan_days():
    """決策 42：前 5 個配額日的案例為 batch1、後 5 日為 batch2，各 10 案、不重疊。"""
    plan = Path(__file__).resolve().parents[1] / "evaluation" / "run-plan.json"
    b1, b2 = s2c.cases_for_batch(plan, "batch1"), s2c.cases_for_batch(plan, "batch2")
    assert len(b1) == 10 and len(b2) == 10 and not set(b1) & set(b2)