v12-runner-freeze.md（D，W09-D）

一、鎖定狀態與版本
1. 第一段凍結（案例、分組、資料、B 的工具、評分規則）：已於 2026-10-25 10:46 完成，build_freeze.py --verify 嚴格核對。
2. 第二段凍結（Researcher、Reviewer prompt 與 Agent 程式）：截至 2026-11-11，data/v12-frozen-manifest.json 顯示 locked: false，尚未鎖定。組長預計 11/13 鎖定（決策第 18 節），鎖定後由 B 執行 build_freeze.py --lock-agent 記錄，之後改用 --verify --strict 全部嚴格核對。
3. 正式 runner 的保護：第二段沒有鎖定，或 --verify --strict 沒通過，formal_runs.py 拒絕 live 執行（test_live_refused_until_stage2_locked 有測試）。
4. 目前版本（來源 handoff/agent-version-changes.md）：researcher-v1.2.4、reviewer-v1.2.2，模型 gemini-3.5-flash-lite，thinking minimal，單次輸入上限 6,000 token、每 job 64,000 token，單次輸出 1,500 token，每 job 最多 8 次模型發送、10 次工具、2 輪補查，180 秒主動時間。正式實驗代號 formal-v2。
5. 待鎖定後填入：repo commit [待填]、prompt hash [待填]、鎖定時間 [待填]。

二、60 run 三模式的輸入與工具
1. 計畫：保留集 20 案 × 3 模式（single、dual、workflow）= 60 run，固定種子 20261116；同一個案例的三個模式連續執行，起始模式輪替；每配額日 6 run（2 案 × 3 模式），共 10 個配額日。run_id 格式為 formal-v2-案例ID-模式。（來源：scripts/formal_runs.py；我沒有打開 evaluation/run-plan.json）
2. 輸入相同：三個模式建 job 時都用同一組 ticker、cutoff_at、source_snapshot_id、focus（案例標題）；案例只載入一次，三個模式共用。模型 ID 會與 handoff/quota-baseline.json 比對，不一致就停止。三個模式共用同一套預算閘門與上限。
3. 工具與流程的差異（這是設計差異，不是輸入差異）：
- single：Researcher 自己選工具，最多 8 次發送，沒有 Reviewer，寫完草稿就結束。
- dual：Researcher 初次研究最多 4 次發送，其餘留給 Reviewer；Reviewer 加上規則檢查。
- workflow：程式固定依序執行搜尋證據、讀前 5 筆來源、財報快照、總經快照、股價 1 日，然後模型不帶工具、只寫一次草稿，沒有覆核，也沒有 calculate_metrics（組長 11/11 確認）。
4. 同一個案例三個模式看到的是同一份快照；差別只在誰決定呼叫哪些工具、有沒有覆核。這個流程差別是實驗要比較的變數，所以寫成設計差異。

三、排程與配額
1. 排程：11/16 到 11/25 每天 19:30（含週末）跑 6 個正式 run，共 10 個配額日（組長決策第 22 節）。
2. 配額日定義：每個配額日上限 J=6 個 job，以太平洋時間的日期計算，台北時間 16:00 重置。J 的公式是 min(6, floor((floor(0.8 × RPD) − 其他保留) / 8))，RPD=500：floor(0.8 × 500)=400，400 ÷ 8 = 50，取 min(6, 50)=6，也就是額度算出來最多 50 個 job，專案規定的每日上限是 6 個（來源：handoff/quota-baseline.json）。
3. 發送次數：每個 job 最多 8 次發送，一天最多 48 次，遠低於每日 500 次上限。
4. 其他用途（組長 11/11 回覆）：
- 11/16 到 11/25 這段期間不安排其他 Gemini 用途，6 個正式 run 會用滿每天的 J。
- 前瞻第 3 批：11/13 跑 3 個 job，不在正式評估期間。
- 前瞻 1、5、20 日觀察：只讀價格，0 次 LLM。
- 展示：網站只放已發布報告和 REPLAY，0 次 LLM，Render 上沒有 Gemini 金鑰。
- 重跑：正式評估期間不重跑，要重跑就發新的實驗版本。
5. 額度用完時：status 是 paused_quota 的 run 不寫紀錄，同一個 run_id 下一個配額日先跑。

四、失敗輸出與九份前瞻觀察
1. 正式 run 的失敗紀錄規則見 runner-smoke.md 第五段：成功、insufficient_evidence、failed、runner_error 都寫一列進 runs-v2.jsonl，有 run_id；paused_quota 不寫紀錄，同一個 run_id 下一個配額日先跑。
2. 九份前瞻觀察（3 批 × 2330、2317、2454）都在清單裡，失敗、資料不足、未凍結都保留，不只挑成功的（來源：evaluation/v12-forward-manifest.csv、research/forward-manifest-9.json，B 整理）：
- 已研究 6 份，全部是 v1（researcher-v1.2.2、reviewer-v1.2.1）：2 份 succeeded（fwd1-2317、fwd2-2330），4 份 insufficient_evidence（fwd1-2330、fwd1-2454、fwd2-2317、fwd2-2454）。已發布的只有 fwd1-2317。
- 第 3 批 3 份（fwd3-2330、2317、2454）狀態是 pending_not_frozen，預定 11/13 21:00 截止後由組長凍結，使用 v2（researcher-v1.2.4）。
- 第 1 批原訂 10/30 21:00 後執行，實際 10/31 19:08，晚約 22 小時；第 2 批實際 11/06 21:39，晚約 40 分鐘。清單都有記錄，沒有重抓覆蓋。
- 方向一律為 none（前瞻不計方向命中）；1、5、20 日報酬由 scripts/forward_eval.py 依實際價格計算，清單不填。
3. 版本不混用：前瞻第 1、2 批是 v1，第 3 批是 v2。兩個版本的輸入上限（3,000／40,000 與 6,000／64,000 token）和覆核規則都不同，結果差異可能來自版本而不是模型表現，所以報告中逐份標示版本，不放在同一張表比較。

五、保留題隔離與已知接觸紀錄
1. 我（D）的接觸紀錄：2026-10-19 確認檔案時讀過封存檔的檔頭與 CASE-02 標題欄位（約 600 字元），已記在 evaluation/d-drafts/protocol-v1.md 第五節與 W06 凍結報告骨架。10/19 之後我沒有刻意再打開保留集的檔案，但沒有留下紀錄可以完整證明；我電腦上 test-cases-sealed.json 最近一次存取時間是 11/10 16:35，兩份副本只差約 1.5 毫秒，推測是系統自動掃描，無法確定，請 B 核對。本週（W09）我沒有打開 evaluation/test-cases-sealed.json 和 evaluation/run-plan.json；只執行 tests/test_formal_runs.py，由測試程式自己載入保留集，終端只顯示通過或失敗。
2. CASE-13：scripts/dev_traces.py 預設曾包含 CASE-13。B 的稽核（evaluation/source-audit-final.md 第一節第 3 點）結論是，10/15 以前出現的「CASE-13」（2317，缺 CapEx）是已廢除的舊開發草稿，與保留集 CASE-13 不是同一個案例，保留集未被污染；組長在決策第 15 節採用此結論。這是 B 與組長的判斷，我沒有自行判斷。
3. 組長端的揭露（決策第 15、17 節）：組長 11/07 讀到稽核文件裡一行保留集 CASE-13 的情境描述，讀到前 Agent v2 已完成且只用開發集驗證，之後不據此調整任何 prompt、規則或程式；data/v12-finance-fact-sheet.md 第 128、132 行有兩個保留案例的題型層級描述，屬第一段凍結不修改，以揭露處理。
4. 修改依據：就我經手的部分，本週沒有用保留案的內容或輸出調整任何 prompt、工具或規則。researcher-v1.2.4（11/10）的修改依據是開發集 CASE-15、18 的 v2 dual 評分（決策第 23 節）。
5. 正式 run 的草稿與覆核存在 tmp/formal_v2.sqlite3，runs-v2.jsonl 只有狀態與預算；評分用匿名匯出由組長在 60 run 跑完後執行（scripts/export_for_scoring.py）。

六、驗收對照與未完成事項
驗收對照（工作包 4 條）：
1. 參數／來源相同：見第二段。三個模式輸入、模型、預算上限相同，只有流程設計不同。
2. 排程納入所有用途配額：見第三段，依組長 11/11 回覆。
3. 失敗輸出也有 run_id：見第四段與 runner-smoke.md 第五段。例外是 paused_quota（還沒真的跑，不寫紀錄）。
4. 無資料洩漏、不同版本不混分：見第五段與第四段第 3 點。我的接觸紀錄有一處無法確認，已標請 B 核對。

未完成事項：
1. 第二段（prompt 與 Agent 程式）尚未鎖定：預計 11/13 由組長鎖定，鎖定後補第一段第 5 點的 repo commit、prompt hash、鎖定時間。提供人：組長、B。
2. 11/11、11/12 的 single、workflow、dual 重跑結果：見 runner-smoke.md，等組長結果檔上 main。
3. 盲評檔欄位需求（例如「停止原因與執行紀錄是否一致」這欄在盲評時做不了）：11/16 前告知組長。
4. 保留集接觸紀錄第 1 點的不確定部分：請 B 核對。
5. run-plan.json 我沒有打開，只依組長說明和 formal_runs.py 確認排程設計；「可以照用」是我 11/09 的回覆，沒有自己逐案檢查。

簽核：B 交叉評分 [待填]；組長核准 [待填]
D 實際工時：2小時（runner-smoke.md 與 v12-runner-freeze.md 兩份合計，我自己記錄）。
