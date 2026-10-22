# CR-W06：保留集執行前 `agents/snapshot.py` 的防護（組長負責，建議 10/23 凍結工具前合併）

- 提出：B，2026-10-22（依 10/22 pull 後的組長版 snapshot.py 檢查）
- 背景：組長已完成 CR-W05-holdout 第 1 項（`snap-test-` 讀保留集快照）。B 以**合成快照**（不讀保留集內容）測試其餘項目，發現兩處會在 W10 保留集正式執行時出錯。`agents/snapshot.py` 在凍結工具清單內，凍結後再改需另立版本，故建議凍結前合併。

## 一、問題

| # | 情境 | 現行行為 | 影響 |
|---|---|---|---|
| 1 | 片段沒有官方發布時間（`available_at = null`），只有 `captured_at`（保留類別「沒有可信發布時間與截止前捕獲」） | `_evidences()` 呼叫 `_t(None)` 拋 `AttributeError`，整個 job 失敗 | 該案無法執行；違反手冊「未知公告以 captured_at 判可得」 |
| 2 | `tool_simulation` 的 `behavior = no_data`（保留類別「financial 工具回結構化 no_data」） | 只處理 `timeout`，`no_data` 被忽略，改走全域快照回傳真實數字 | 擾動無效，案例測不到預期行為 |
| 3 | 保留案例的 `task_input`、`draft_under_review` 欄位 | job 建立時沒有讀取 | 由組長／D 的 W09 runner 決定如何放入題目；`expected_*` 不得進 prompt |

## 二、建議修改（`CR-W06-snapshot-holdout.diff`，只動 snapshot.py）

1. 新增 `_avail(e)`：`available_at` 優先，否則 `captured_at`（basis = `captured_at_fallback`）；兩者皆無視為不可得。
2. `_evidences()`、`search_evidence()`、`read_evidence()` 改用 `_available_by(e, limit)`，並回傳 `available_at_basis`。
3. 新增 `_simulated_no_data(name)`：`behavior = no_data` 且工具名相符時，回 `{"status": "no_data", "tool": name, "data": None, "reason": ...}`，不拋例外、不補值。

## 三、驗證（B 於雲端，合成快照）

| 測試 | 現行 snapshot.py | 套用建議後 |
|---|---|---|
| 無發布時間片段：cutoff 前擷取者可讀、cutoff 後擷取者與兩者皆無者不可讀 | ❌ 例外 | ✅ |
| `tool_simulation = no_data` 回結構化 no_data | ❌ 回真實數字 | ✅ |
| 其餘可執行測試 | 178 passed | 178 passed（另加 2 項新測試全過） |

測試檔 `docs/test_snapshot_holdout_guard.py.txt`：組長合併 diff 時請改名為 `tests/test_snapshot_holdout_guard.py` 一併加入。`test_research_graph.py` 需 google-genai，B 的環境無法執行，請組長本機跑全套確認。
