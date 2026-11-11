runner-smoke.md（D，W09-D）

一、範圍
這份文件記錄正式實驗（保留集 20 案 × 3 模式 = 60 run）開跑前，用開發案做的最後 smoke 檢查。只用開發案 10 案（CASE-01、04、08、11、15、18、19、22、26、29），沒有開啟或使用保留集的答案。

二、版本
正式實驗用 v2：researcher-v1.2.4（11/10 起；11/10 前為 v1.2.3）、reviewer-v1.2.2，模型 gemini-3.5-flash-lite，單次輸入上限 6,000 token、每 job 上限 64,000 token，每 job 最多 8 次模型發送、10 次工具、2 輪補查。（來源：handoff/agent-version-changes.md）

三、開發案 smoke 現況
(a) v2 dual：evaluation/d-drafts/dev-runs-calib-v2.jsonl 共 13 筆，全部是 dual、live，其中 8 筆 succeeded、5 筆 insufficient_evidence。CASE-15、19、26 各有原版和 11/08 重跑兩筆，評分用重跑的。commit：CASE-01、04、08 原版是 d53c9f0；CASE-11、15、18、19、22、26 原版是 50ce430；CASE-29 和 11/08 的三筆重跑是 92a150f。這批屬 researcher-v1.2.3，我的 v2 dual 評分（PR #37）也屬此版本。
(b) single、workflow（組長端自檢，不需 D 評分，我也沒有補跑）：
- 11/9 single 6 案（CASE-01、04、08、11、15、18），researcher-v1.2.3，commit eb0deab，agent/calib-v2-modes-day1.json：5 筆 succeeded、1 筆 insufficient_evidence（CASE-18）。
- 11/10 single 4 案（CASE-19、22、26、29）和 workflow 2 案（CASE-01、04），researcher-v1.2.4，commit 09cfe9d，agent/calib-v2-modes-day2-single.json、agent/calib-v2-modes-day2-workflow.json：single 3 筆 succeeded、1 筆 insufficient_evidence（CASE-26）；workflow 2 筆 succeeded。
- 11/11 workflow 6 案、11/12 workflow 2 案和 dual 重跑 CASE-15、18：依組長 11/11 說明排程中（每晚 19:30），結果檔尚未在 main，我沒有看到。
(c) 版本差別：researcher-v1.2.3 到 v1.2.4（組長 11/10 決定，決策第 23 節）只加了一句要求，回 insufficient 時填 1 到 3 個 next_signals，其他不變。所以同一個模式的 smoke 分成兩個 prompt 版本，不混在一起看。smoke 只看有沒有程式錯誤與狀態，不評分。
(d) 對照 workflow 的設計：固定流程是搜尋證據、讀前 5 筆來源、財報快照、總經快照、股價 1 日，然後模型不帶工具、只寫一次草稿，沒有覆核，也沒有 calculate_metrics（組長 11/11 確認，程式在 agents/research_graph.py 的 workflow_node）。這是設計差異，不是缺漏。

四、保留題隔離與洩漏檢查
我讀了 scripts/formal_runs.py 和 tests/test_formal_runs.py（沒有打開 evaluation/test-cases-sealed.json 和 evaluation/run-plan.json），核對結果如下：
1. 載入保留案時只取 case_id、ticker、cutoff_at、source_snapshot_id、variant、title 這 6 個執行欄位，不讀 expected 開頭的欄位、allow_insufficient 等答案欄位。測試 test_holdout_loader_keeps_execution_fields_only 有檢查。
2. 寫進 evaluation/formal/runs-v2.jsonl 的每一列只有 metadata（run_id、狀態、停止原因、預算、版本、commit），沒有草稿、覆核或主張。測試 test_rows_carry_no_draft_or_review 有檢查。草稿與覆核存在 tmp/formal_v2.sqlite3，評分用匿名匯出另外處理。
3. 第二段沒有鎖定，或 build_freeze.py --verify --strict 沒通過時，runner 拒絕執行 live。測試 test_live_refused_until_stage2_locked 有檢查。
限制：我只跑了 tests/test_formal_runs.py（4 個測試，全部通過；指令 .venv/bin/python -m pytest -q --tb=no tests/test_formal_runs.py，main commit 9e08651，Python 3.10.12，pytest 9.1.1），沒有跑全部測試，也沒有執行 formal_runs.py（--live 未執行）。測試只輸出通過或失敗，沒有顯示保留案內容。

五、失敗處理與重跑規則
1. 正式 run 的 run_id 是固定格式 formal-v2-案例ID-模式（例如 formal-v2-CASE-xx-dual），先在 run-plan 裡排好，執行前就存在。
2. 不管成功或失敗，每個執行過的 run 都寫一列進 runs-v2.jsonl：succeeded、insufficient_evidence、failed，以及 runner 自己出錯時的 runner_error（停止原因記錯誤類型），都有 run_id。
3. paused_quota（配額日用完、這個 run 還沒真的跑）不寫紀錄，下一個配額日用同一個 run_id 先跑。
4. 已經有紀錄的 run_id 不會自動重跑。要重跑必須發新的實驗版本，舊紀錄保留，不覆蓋。
5. runner 出錯時只記錄，不會悄悄重試。
（來源：scripts/formal_runs.py 的 make_plan、main、row_for；我沒有執行過 live。）

六、未完成事項
1. 11/11、11/12 的 single、workflow、dual 重跑結果：等組長結果檔上 main 再補進第三段。
2. 全部測試（B 回報 436 passed）不是我跑的，我只跑了 tests/test_formal_runs.py。
3. 匿名匯出程式已在 main（scripts/export_for_scoring.py），60 run 跑完後由組長執行，我未執行、未檢查輸出。盲評檔的欄位需求 11/16 前告知組長。

實際工時：2小時（runner-smoke.md 與 v12-runner-freeze.md 兩份合計，我自己記錄）。
