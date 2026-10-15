# tool-validation　六工具驗證結果（草稿）

任務ID：W03-D
負責人：組員D
驗收人：B 交叉評分，組長核准結論
狀態：草稿，尚未經 B 與組長驗收。AI 協助產出不等於驗收。
更新：2026-10-09

## 一、先講結論

- 依 B 的規約 data/v12-adapter-tests.md 寫的 TEST-01 到 TEST-09，**9 項全部通過**（工具函式本身的邏輯是對的）。
- 但「經 dispatch 呼叫」的整合測試有問題：dispatch 是 provider.py 實際呼叫工具的路徑，在這條路徑上，**六個工具沒有一個能正常回傳資料**（原因見第三節 F1、F2）。
- 本次共 45 項測試：36 通過、9 失敗。失敗項目沒有刪，全部列在附錄，交給 B 修正。
- 這些都是離線測試（mock／本機資料檔），沒有呼叫任何模型，也沒有 live 實測。

## 二、來源與環境

- 被測程式：本機 repo fintech_project，HEAD 為 4f67d15（Merge pull request #2）。被測的 agents/、valuation_agent/、data/ 都沒有未 commit 的修改（git status 只有 4 個無關的未追蹤檔：batch_analyze.py、check_db.py、fix.py、test_gemini.py）。
- 執行環境：雲端工作環境（不是 D 的 Mac），Python 3.13.16、pytest 9.1.1，使用從本機複製過去的檔案。尚未在 D 的本機重跑。
- 測試檔：test_adapter_tools.py（本資料夾）。
- 命令：REPO_ROOT=<repo 根目錄> python -m pytest -q test_adapter_tools.py
- 結果：9 failed, 36 passed。
- 另外 B 既有的 repo 測試（tests/）在 D 本機 2026-10-08 執行：111 passed in 29.72s（離線 mock）。這 111 項沒有抓到第三節的問題，原因見 F1。

## 三、發現（交給 B 判斷與修正；D 只標出問題，沒有改 B 的程式）

### F1　工具實作與 dispatch 的呼叫方式不相容（影響最大）

- 現象：agents/tools.py 的 dispatch 用 `impl(args)` 把整包參數當成**一個字典**傳給工具（型別宣告 ToolImpl = Callable[[dict], dict]）。但 agents/tools_impl.py 的函式是分開的參數，例如 `search_evidence(ticker, query, cutoff, limit)`。
- 重現：載入 agents.register_tools 後，用 dispatch("researcher", "search_evidence", {...}) 呼叫，回 `tool_error`，原因 `TypeError: search_evidence() missing 2 required positional arguments`。get_financial_snapshot、get_price_window、calculate_metrics 同樣 TypeError。
- read_evidence 更隱蔽：沒有報錯，而是回 `no_data`（整包字典被當成 evidence_version_id，查不到任何資料），看起來像「查無此證據」。
- 為什麼 111 項既有測試沒抓到：既有測試註冊的是假工具（例如 `register_tool("get_price_window", lambda args: ...)`），沒有走真實工具。
- 影響：Agent 實際執行時，六個工具裡有五個會 tool_error，一個會假裝查無資料。
- 失敗測試：test_registered_impls_follow_dict_contract、test_dispatch_normal_call_returns_ok（5 項）。
- 建議（給 B 決定）：註冊時用轉接，例如 `register_tool("search_evidence", lambda a: search_evidence(**a))`，或把工具函式改成接收一個字典。

### F2　總經序列白名單是空的（已知待辦）

- agents/tools.py 的 MACRO_SERIES_WHITELIST 目前為空（原註解：待 W02 與 B 鎖定），所以任何總經序列都被 dispatch 擋下。資料檔裡有 CPIAUCSL、FEDFUNDS。
- 這不是新的錯誤，是尚未完成的鎖定項目；列出來是因為 get_macro_snapshot 目前經 dispatch 完全不能用。
- 失敗測試：test_dispatch_macro_normal_call_returns_ok。

### F3　TTM 沒檢查四個季度是否連續

- 手冊 F01：TTM 需要四個連續季度。
- 現象：get_financial_snapshot 只要有 4 個以上已公告的季度，就把「最後 4 筆」加總，沒檢查是否連續。
- 重現：構造 2025Q1、2025Q3、2026Q1、2026Q2 四季（缺 2025Q2、2025Q4），每季 EPS 為 1.0，回傳 eps_ttm = 4.0，預期應為 null。
- 失敗測試：test_ttm_requires_consecutive_quarters。
- 補充：只有 3 季時 TTM 正確回 null（TEST-03 通過）。

### F4　工具讀不到 dev 案例的快照

- 工具讀的是 data/financial-snapshots.json（證據編號例如 ev-2330-2026q2-01）；B 的 dev 案例證據在 fixtures/dev/case_fixtures.json（編號例如 ev-dev-01-official）。兩邊沒有接起來，read_evidence("ev-dev-01-official") 直接呼叫回 no_data。
- 影響：用 dev 案例跑 Agent 時，工具查不到案例要用的證據。
- 失敗測試：test_tools_can_read_dev_case_snapshots。這項是 D 依手冊「工具讀本 job 快照」的理解寫的，B 若有不同設計請說明，D 再調整測試。

### F5　資料檔沒有 2317

- data/financial-snapshots.json 的證據只有 2330、2454；財報與價格只有 2454、2379、3034、2330。**完全沒有 2317**。
- 影響：E01 的三個示範案例包含 2317，目前工具對 2317 只會回 no_data。（財報也只有 2454 有 4 季，2330 只有 1 季，TTM 只有 2454 算得出來。）
- 這項沒有寫成失敗測試，因為不確定 2317 的資料是否另有計畫補入，請 B 說明。

### 待 B 說明的問題（還不能算錯誤）

1. get_financial_snapshot 的說明寫「含 YTD 差分還原」，但程式裡沒有看到差分邏輯；資料有 period_basis 欄位，如何使用？
2. calculate_growth_rate 的分母用 abs(前期)：前期為負時，成長率符號是否符合手冊？

## 四、六工具 x 三情境結果

「直接」是直接呼叫工具函式，「dispatch」是 provider.py 實際走的路徑。

| 工具 | 情境 | 直接 | dispatch |
| --- | --- | --- | --- |
| search_evidence | 正常 | 通過 | 失敗（F1） |
| | 缺失（cutoff 前無資料） | 通過（no_data） | — |
| | 缺少必填欄位 | — | 通過（invalid_input） |
| | 無權限 | 通過（未授權標的 invalid_input） | 通過（reviewer 無權） |
| read_evidence | 正常 | 通過 | 失敗（F1，回 no_data） |
| | 缺失（查無編號） | 通過（no_data） | — |
| | 缺少必填欄位 | — | 通過 |
| | 無權限 | — | 未測（reviewer 本來就可用，無需擋） |
| get_financial_snapshot | 正常 | 通過 | 失敗（F1） |
| | 缺失（3 季、無 2317） | 通過（TTM 為 null、no_data） | — |
| | 缺少必填欄位 | — | 通過 |
| | TTM 不連續 | 失敗（F3） | — |
| get_macro_snapshot | 正常 | 通過 | 失敗（F2） |
| | 缺失（cutoff 前、未知序列） | 通過（no_data） | — |
| | 缺少必填欄位 | — | 通過 |
| get_price_window | 正常 | 通過 | 失敗（F1） |
| | 缺失（交易日不足） | 通過（no_data） | — |
| | 非法 sessions（10） | 通過（invalid_input） | — |
| | 缺少必填欄位 | — | 通過 |
| | 無權限 | — | 通過（reviewer 無權） |
| calculate_metrics | 正常（pe_ttm、dcf、peer） | 通過 | 失敗（F1） |
| | 缺失／非法（EPS 小於等於 0、WACC 小於等於 g、缺淨負債、非 2454 主體、超過 4 家） | 通過（invalid_input） | — |
| | 缺少必填欄位 | — | 通過 |

另外通過的 dispatch 防護：未知工具與未知角色被擋、超過 job cutoff 的資料被擋、參數含網址或 SQL 字樣被擋。

## 五、TEST-01 到 TEST-09 對照（B 的規約）

| 編號 | 內容 | 結果 |
| --- | --- | --- |
| TEST-01 | search_evidence 不可前視 | 通過 |
| TEST-02 | read_evidence 不存在的編號回 no_data | 通過 |
| TEST-03 | 只有 3 季時 TTM 為 null | 通過 |
| TEST-04 | get_price_window sessions=10 回 invalid_input | 通過 |
| TEST-05 | pe_ttm 的 EPS 小於等於 0 | 通過 |
| TEST-06 | DCF 的 WACC 小於等於 g | 通過 |
| TEST-07 | DCF 缺淨負債不補 0 | 通過 |
| TEST-08 | peer_comparison 主體非 2454、超過 4 家 | 通過 |
| TEST-09 | 同業平均排除 2330（手算：(20 + 10) / 2 = 15.0；PB (4.0 + 2.0) / 2 = 3.0） | 通過 |

## 六、未執行或未涵蓋（如實列出）

- 沒有 live 測試：沒有呼叫 Gemini，沒有連 Supabase、FinMind、FRED。
- peer_comparison 經 dispatch 的完整輸入檢查（價格基準日、快照編號、method_version、日期不得晚於 cutoff）：未逐項測。
- read_evidence 的「≤1,200 字」與「來源連結」內容檢查：未測。
- F1 修好之後，dispatch 正常路徑的測試要重跑，D 才能確認真正通過。
- 尚未在 D 本機重跑本次測試，尚未放進 repo。

## 七、可貼回 Notion 的文字

W03-D 草稿：六工具驗證測試 45 項（雲端環境，離線），36 通過、9 失敗；B 規約 TEST-01 到 TEST-09 全部通過；DCF 新舊實作與手算一致（167.44 元/股）。發現 dispatch 與工具簽名不相容（五個工具 TypeError、read_evidence 假性 no_data）、TTM 未檢查季度連續、工具讀不到 dev 快照、資料檔沒有 2317、總經白名單未鎖定。失敗項目已列出交 B 修正。未做 live 與本機重跑。尚未經 B 交叉評分與組長核准。

## 附錄　逐項測試結果（由 pytest 結果自動產生）

共 45 項：36 通過、9 失敗。失敗原因欄是 pytest 的原始訊息（截短）。

| 測試 | 結果 | 失敗原因 |
| --- | --- | --- |
| test_TEST01_search_evidence_no_lookahead | 通過 |  |
| test_search_evidence_normal_returns_source_ids | 通過 |  |
| test_search_evidence_unauthorized_ticker | 通過 |  |
| test_TEST02_read_evidence_unknown_id_is_no_data | 通過 |  |
| test_read_evidence_normal | 通過 |  |
| test_TEST03_ttm_needs_four_quarters | 通過 |  |
| test_financial_snapshot_ttm_four_quarters_matches_hand_sum | 通過 |  |
| test_ttm_requires_consecutive_quarters | 失敗 | assert 4.0 is None |
| test_financial_snapshot_missing_ticker_is_no_data | 通過 |  |
| test_TEST04_price_window_rejects_bad_sessions | 通過 |  |
| test_price_window_normal | 通過 |  |
| test_price_window_insufficient_sessions_is_no_data | 通過 |  |
| test_TEST05_pe_nonpositive_eps_not_applicable | 通過 |  |
| test_pe_normal_hand_value | 通過 |  |
| test_calculate_metrics_requires_evidence_refs | 通過 |  |
| test_TEST06_dcf_wacc_not_above_g | 通過 |  |
| test_TEST07_dcf_missing_net_debt_is_not_zero | 通過 |  |
| test_TEST08_peer_subject_must_be_2454 | 通過 |  |
| test_TEST08_peer_more_than_four_companies | 通過 |  |
| test_TEST09_peer_average_excludes_2330 | 通過 |  |
| test_macro_snapshot_direct_normal_and_no_lookahead | 通過 |  |
| test_macro_snapshot_direct_unknown_series_is_no_data | 通過 |  |
| test_tools_can_read_dev_case_snapshots | 失敗 | AssertionError: assert 'no_data' == 'ok'      - ok   + no_data |
| test_dispatch_normal_call_returns_ok[search_evidence] | 失敗 | AssertionError: search_evidence 經 dispatch 回 tool_error：TypeError: search_evidence() missing 2 required positi |
| test_dispatch_normal_call_returns_ok[read_evidence] | 失敗 | AssertionError: read_evidence 經 dispatch 回 no_data：查無指定片段: {'evidence_version_id': 'ev-2330-2026q2-01'} assert |
| test_dispatch_normal_call_returns_ok[get_financial_snapshot] | 失敗 | AssertionError: get_financial_snapshot 經 dispatch 回 tool_error：TypeError: get_financial_snapshot() missing 1 r |
| test_dispatch_normal_call_returns_ok[get_price_window] | 失敗 | AssertionError: get_price_window 經 dispatch 回 tool_error：TypeError: get_price_window() missing 2 required posi |
| test_dispatch_normal_call_returns_ok[calculate_metrics] | 失敗 | AssertionError: calculate_metrics 經 dispatch 回 tool_error：TypeError: calculate_metrics() missing 2 required po |
| test_dispatch_macro_normal_call_returns_ok | 失敗 | AssertionError: series ['CPIAUCSL'] 不在已核准白名單（白名單待 W02 與 B 鎖定） assert 'invalid_input' == 'ok'      - ok   + inv |
| test_registered_impls_follow_dict_contract | 失敗 | AssertionError: 這些工具需要多個必填參數，和 dispatch 的 impl(args) 不相容：[('search_evidence', ['ticker', 'query', 'cutoff']),  |
| test_dispatch_missing_required_field_is_invalid_input[search_evidence-researcher-args0] | 通過 |  |
| test_dispatch_missing_required_field_is_invalid_input[read_evidence-researcher-args1] | 通過 |  |
| test_dispatch_missing_required_field_is_invalid_input[get_financial_snapshot-researcher-args2] | 通過 |  |
| test_dispatch_missing_required_field_is_invalid_input[get_price_window-researcher-args3] | 通過 |  |
| test_dispatch_missing_required_field_is_invalid_input[calculate_metrics-researcher-args4] | 通過 |  |
| test_dispatch_missing_required_field_is_invalid_input[get_macro_snapshot-researcher-args5] | 通過 |  |
| test_dispatch_reviewer_cannot_use_researcher_only_tools[search_evidence-args0] | 通過 |  |
| test_dispatch_reviewer_cannot_use_researcher_only_tools[get_price_window-args1] | 通過 |  |
| test_dispatch_unknown_tool_and_unknown_role | 通過 |  |
| test_dispatch_refuses_data_after_job_cutoff | 通過 |  |
| test_dispatch_refuses_url_or_sql_in_query | 通過 |  |
| test_dcf_new_calculator_matches_legacy_annual_dcf | 通過 |  |
| test_dcf_hand_computed_two_year_example | 通過 |  |
| test_dcf_zero_or_negative_shares_rejected | 通過 |  |
| test_dcf_empty_cash_flows_rejected_not_zero | 通過 |  |
