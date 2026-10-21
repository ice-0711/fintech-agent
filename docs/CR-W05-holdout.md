# CR-W05：保留集執行所需之 agents/snapshot.py 調整（組長負責）

B 已依固定分配表重建 20 個保留案例（`evaluation/test-cases-sealed.json`、`fixtures/test/case_fixtures.json`，封存紀錄 `fixtures/test/SEAL.json`）。`agents/snapshot.py` 目前只讀開發集快照，保留集正式執行（W10、60 run）前需以下調整。B 不直接修改組長檔案。

| # | 現況 | 建議 |
|---|---|---|
| 1 | `load_case_snapshot()` 只讀 `fixtures/dev/case_fixtures.json` | 依 `snapshot_id` 前綴：`snap-dev-` 讀開發集、`snap-test-` 讀 `fixtures/test/case_fixtures.json`；保留集只在評分執行時載入 |
| 2 | `tool_simulation` 只在 CR-02 處理 `read_evidence` timeout | CASE-30：`tool_name = get_financial_snapshot`、`behavior = no_data` 時回傳 `{"status": "no_data", "reason": <reason>, "data": None}` |
| 3 | `financial_snapshot` 欄位為 null（CASE-14 EPS、CASE-17 淨負債）時直接回傳 | 保持 null 並帶 `missing_reason`，不可由全域快照補值 |
| 4 | 片段 `available_at` 為 null 時 `_t()` 會拋例外 | 以 `captured_at` 判定（CASE-16），兩者皆無視為不可得 |
| 5 | 案例的 `task_input`（CASE-23）、`draft_under_review`（CASE-28）未傳入 job | 由組長決定如何放入研究題目；保留集答案欄位（expected_*）不得進入 prompt |

保留集封存後若需修改，請重跑 `python scripts/build_holdout_cases.py` 並以 `python scripts/check_cases.py` 驗證，再由 D 與組長確認新的 SEAL hash。