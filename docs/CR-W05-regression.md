# CR-W05-regression：全套回歸 10 項失敗之原因與建議（組長、A 負責）

執行：`pytest -q`（2026-10-20）→ 223 passed, 10 failed, 34 skipped, 2 xfailed。
B 的適配層與契約測試（`tests/test_adapter_tools.py`、`tests/test_tool_fixtures.py`）全數通過；
10 項失敗都在組長與 A 的測試檔，原因是測試內寫死了 B 改用真實資料前的舊假資料。

## 一、tests/test_research_graph.py（組長，7 項）

| 寫死的舊值 | 現行真實資料 | 位置 |
|---|---|---|
| 片段 ID `ev-dev-01-official` | `ev-dev-01-official-1`（營收、毛利）、`ev-dev-01-official-2`（獲利、EPS） | `fixtures/dev/case_fixtures.json` |
| CASE01 cutoff `2026-07-20T17:00` | `2026-08-12T17:00:00+08:00`（片段為合併損益表，08-11 18:46:58 才可得） | `evaluation/dev-cases.json` |
| 台積電 2026Q2 營收「約 6,735 億元」 | 12,703.80 億元（1,270,380,250 千元） | 快照、`ev-dev-01-official-1` |
| 毛利率 53.2% | 67.72% | `ev-dev-01-official-1` |
| CASE13 `snap-dev-case-13`（2317） | **CASE-13 是保留案例（2330），不得用於開發測試**；改用開發案例 CASE-15（`snap-dev-case-15`，2454，cutoff 2026-08-05T17:00，正文不可讀）或 CASE-18（證據在 cutoff 後） | 手冊第 06 章固定分配表 |

受影響：`test_researcher_path_follows_tool_results_and_review_passes`、`test_tool_error_is_returned_to_the_model_which_can_choose_again`、`test_fourth_research_call_must_return_a_draft`、`test_each_step_is_checkpointed_with_budget`、`test_invalid_draft_gets_one_format_retry`、`test_rules_override_model_pass_then_bounded_revision`、`test_crash_mid_run_resumes_from_checkpoint_without_resetting_budget`。

## 二、tests/test_research_ui.py 與 ui/v12-dashboard-fixture.json（A，3 項）

| 測試 | 原因 | 建議 |
|---|---|---|
| `test_missing_data_is_no_data_not_zero` | 預期 2317 的 `get_financial_snapshot` 回 `no_data`；真實快照已有 2317 五季資料，回 `ok` | 改用 cutoff 早於 2025Q2 公告（2025-08-14）的情境，或以不存在的片段 ID 測 `no_data` |
| `test_evidence_drawer_reports_hash_and_cutoff_honestly` | fixture 報告 c1 寫「2026Q2 合併營收 1,272.7 億元，單季 EPS 16.19 元」；`ev-2454-2026q2-01` 實際為 1,521.83 億元、EPS 15.28 | 更新 `ui/v12-dashboard-fixture.json` 第 84、122 行與測試第 247 行（2026Q1 EPS 為 15.17，非 19.85） |
| `test_comparison_rules` | 測試預期 2379 只有 1 季、快照 P/E 19.5；真實快照 2379 有 5 季、P/E 27.41。另 `comparison.py` 以 13:30 查價且讀 `close` 欄位 | 依 `docs/CR-W04-comparison.md` 改 17:30 與 `close_price`；斷言改為 2379 P/E 27.41、同業平均 23.23 |

## 三、B 的處理

- B 不直接修改組長與 A 的測試檔；以上數值均可由 `python scripts/verify_fact_sheet.py` 與 `python scripts/check_cases.py` 重現。
- 修正後請重跑 `pytest -q`，結果填入 `data/v12-adapter-tests.md` 第五節。

## 四、2026-10-21 重跑結果（origin/main e6b75ec）

執行：`pytest -q tests` → **212 passed, 10 failed**。
（全專案 `pytest -q` 會同時收到 D 草稿區同名的 `test_adapter_tools.py`，收集階段就中斷；建議 pytest.ini 加 `testpaths = tests`、`norecursedirs = evaluation .venv`。）

- 第二節 A 的 3 項：**已解決**（遠端已修正）。
- B 的測試（`test_adapter_tools.py`、`test_tool_fixtures.py`）：全數通過。
- 剩下 10 項**全部在 `tests/test_research_graph.py`**，仍為寫死舊值：

| 測試 | 實際結果 | 原因 | 建議修正 |
|---|---|---|---|
| researcher_path、tool_error_choose_again、fourth_research_call、each_step_checkpointed、invalid_draft_retry、rules_override（supplement_rounds 2≠1）、crash_mid_run、finished_job（8 項） | `read_evidence` 回 `no_data`，job 變 `failed`；草稿引用不存在的片段被規則審查擋下 | 測試與 `GOOD_CLAIMS` 仍用 `ev-dev-01-official` | 呼叫與 `GOOD_CLAIMS` 的 `evidence_refs`／`source_ref` 改為 `ev-dev-01-official-1`；營收 12,703.80 億元、毛利率 67.72%；CASE01 cutoff 用 `2026-08-12T17:00:00+08:00` |
| `test_unreadable_source_is_reported_not_crashing` | 兩次呼叫都 `no_data`（預期 ok、unreadable） | 測試內 CASE15 的 cutoff 早於片段可得時間 2026-07-31T18:41:57 | CASE15 改用 `evaluation/dev-cases.json` 的 cutoff `2026-08-05T17:00:00+08:00`、快照 `snap-dev-case-15`、ticker 2454 |
| `test_simulated_tool_timeout_counts_active_time_and_job_continues` | `no_data`（預期 `tool_error`、含「逾時」） | `snap-dev-case-26` 沒有 evidences，只有 `tool_simulation`（read_evidence、`ev-2317-2026q2-consolidated`、timeout 30 秒）；測試的 CASE26 或 snapshot.py 未走到模擬分支 | 確認測試 CASE26 的 `source_snapshot_id` 為 `snap-dev-case-26`、cutoff `2026-08-12T17:00:00+08:00`，且 `snapshot.py` 的 `read_evidence` 先檢查 `tool_simulation` 再查片段 |

根本建議：測試的 CASE01／CASE15／CASE26 直接從 `evaluation/dev-cases.json` 與 `fixtures/dev/case_fixtures.json` 載入，不要在測試檔寫死 ID、cutoff 與數字，之後資料更新就不會再壞。

狀態：**未解決**（待組長修 `tests/test_research_graph.py`），B 已於 `data/v12-adapter-tests.md` 第五節記錄本次結果。

## 五、2026-10-22 更新

- 組長已加入 `pytest.ini`（`testpaths = tests`、`norecursedirs = evaluation .venv .git tmp`），全專案 `pytest -q` 不再收到 D 草稿。
- TR-14（macro.csv content_hash 跨平台不一致）：組長已改為 LF 正規化後計算。
- `tests/test_research_graph.py` 於 10/22 pull 後未更新，第四節 10 項待組長修正後重跑確認。
