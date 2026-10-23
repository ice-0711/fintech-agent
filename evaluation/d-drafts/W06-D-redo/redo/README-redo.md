W06-D 重做草稿（CASE-11、15、18、22、29）說明（草稿，未經 B 驗收）

一、這是什麼
B 在群組請 D 用開發案 CASE-11、15、18、22、29 重做草稿，完成後通知 B 回評。
這裡是 10 份「模擬 Researcher 草稿」（每案一份 good、一份 flawed），不是模型輸出，不是實驗結果。
只用 dev-cases.json（v1.5）與 fixtures/dev 的快照，沒有讀取或使用保留案。

二、檔案
dev_drafts_v2.json：10 份草稿與預期決定（預期是我先寫好，再讓程式比對）。
run_v2.py：離線比對腳本，不連網、不呼叫模型。
reviewer_checks.py：修補版（見第四節）；reviewer_checks_orig.py：修補前的原版。
reviewer_v12.py：驗證輸出格式用。
dev-drafts-v2-results.json：最後一次執行結果。

三、執行結果
修補前（原版 reviewer_checks，與 repo 的 agents/review_checks.py 內容相同）：10 份中 7 份符合預期。
  CASE-15 兩份：程式當掉（TypeError），因為來源的 paragraph 是 null。
  CASE-11 flawed：沒有被抓到（預期 revise，實際 pass）。
修補後：10/10 符合預期（pass 2、revise 4、insufficient 4）。
重現：REPO_SNAP=<含 fixtures/dev 與 evaluation/dev-cases.json 的目錄> python3 run_v2.py

四、修補了什麼（只在 D 草稿的副本，沒有改 repo 的 agents/）
1. paragraph 為 null 時不再當掉，改列為 critical「來源正文不可讀」（rule：unreadable_source）。
2. 來源 basis 為 unspecified（沒註明合併或個體口徑）時，列為 critical（rule：basis_unspecified）。
3. 幾處 ev.get("paragraph", "") 改成 ev.get("paragraph") or ""。

五、限制（請 B 特別看）
1. 預期決定是我自己寫的，修補規則也是看了這 5 案之後才補的，所以 10/10 只能說「這 10 份草稿與我的預期一致」，不能說明 Reviewer 的真實檢出能力。要靠 B 交叉評分與真實 Gemini 執行才算數。
2. agents/review_checks.py 在凍結清單內。上面兩點修補如果要採用，需要組長或 B 決定，並依凍結規則重凍結；我沒有改它。
3. 我沒有確認 research_graph 是否已經在上游攔截 paragraph 為 null 的情況（組長說 CASE-15 已改為回傳 status unreadable），所以不能說 repo 現況一定會當掉。
4. 舊的 W04 草稿（dev_drafts.json）用的案例包含 CASE-07、13、14、20、25，這些在最終分組是保留案。舊草稿的內容是依 B 當時的開發檔手寫的，不是讀保留集，但不應再當開發校準使用，請以本次 v2 為準。舊測試對新快照有 20 項失敗，原因就是案例分組已變。

---
修訂紀錄（2026-10-23，依 B 交叉評分 docs/B-review-W06-D-redo.md）
1. CASE-18-good 的 limitations 原本寫了 ev-dev-18-late 的 available_at（晚於 cutoff），Agent 實際不會知道這個片段，屬於洩漏 cutoff 後資訊。已改為「截至 cutoff 查無 2026Q2 財報公告，無可用數字」。重跑 run_v2.py 仍為 10/10 符合預期。
2. 先前 README 寫「不確定 research_graph 是否擋 paragraph 為 null」。B 查證：snapshot_view 會把 null 正文轉成空字串，管線中不會當掉；repo 現行檢查唯一的缺口是 CASE-11-flawed（basis unspecified）。unreadable_source 規則因此屬選用。
3. 是否採用 basis_unspecified 由組長決定（agents/review_checks.py 在凍結清單內）。D 不修改凍結檔案。
