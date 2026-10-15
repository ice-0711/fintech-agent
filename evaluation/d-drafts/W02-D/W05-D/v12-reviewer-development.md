# W05-D Reviewer runner 與補查/風險規則測試（草稿，離線 mock，未驗收）

## 做了什麼
- reviewer_runner.py：Reviewer runner。依草稿內容選用允許工具（read_evidence / get_financial_snapshot / calculate_metrics），記錄 tool_trace，輸出 review（符合 schema）+ 風險等級 + 預算使用。
- 接 B 的 tools_impl：以關鍵字參數直接呼叫，避開 F1（dispatch 以 impl(args) 呼叫造成簽名不符）；呼叫前仍先過 validate_tool_call(role="reviewer")。
- read_evidence 對 dev 案例改讀 fixture（F3：repo 的 read_evidence 只讀 data/financial-snapshots.json，讀不到 dev 證據）。
- 規則：缺 EPS、來源矛盾、CapEx 符號、DCF 參數（WACC<=g、缺值不補 0）、無預算、工具上限 10、資料不足風險映射。
- 測試：test_reviewer_runner.py 12 項；加上 W04-D 共 76 passed。

## 結果（20 份 mock 草稿過 runner）
- 有錯草稿 10 份：10 份都沒有 pass（檢出 10/10）。
- 好草稿 10 份：0 份被誤判 revise（誤報 0/10）。
- 與預期決定不一致：0 份。
- 資料不足（CASE-13、14、26-good）：risk=unverified，不標低風險。
- 有呼叫工具的案例：01、04、07、08、19、25（read_evidence 或 calculate_metrics）；原始紀錄見 reviewer-checks.json。

## 驗收清單自查
- 至少一案 Reviewer 自主選工具：有（CASE-04 選 calculate_metrics 重算 P/E；測試顯示依草稿問題換工具）。但這是規則式 planner，不是 Gemini 自己選，這點不可寫成「模型自主」。
- 自述不是證據：判定一律來自工具回傳或本地重算，tool_trace 留紀錄。
- 無 budget 就 insufficient：有（測試 remaining_calls=0，不呼叫工具、不改原草稿）。
- 資料不足不標低風險；保留預算和原缺值：有（budget.unchecked 列出，原草稿不被修改）。

## 限制（要誠實講）
1. 20 份草稿與預期答案都是 D 自擬，檢出 10/10、誤報 0/10 是「對自己寫的題目」，不能當真模型成績，也不能說雙 Agent 較好。
2. 沒有跑 Gemini；真模型是否自主選對工具、會不會亂用工具，要等 provider 接上後在 10 個 dev 案例另測（不可用 20 個 holdout 調 prompt）。
3. 2317 沒有資料，不能真跑。
4. CASE-26-good 預期仍待 B 確認（allow_insufficient=false）。
5. F1、F3 是 B 端問題，我只是繞過，沒有修；需 B 修後再用 dispatch 測一次。
6. 未放進 repo，未經 B 交叉評分與組長核准。
