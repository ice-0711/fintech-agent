acceptance-v5　E01至E10 驗收矩陣（初稿，已補 2026-10-08 至 10-09 本機實測與 repo 核對）

任務ID：W01-D
負責人：組員D
驗收人：B 交叉評分，組長核准結論
狀態：草稿，尚未經 B 與組長驗收
資料來源：fintech-agent 專題執行手冊 V1.2 第06章「必過工程驗收」

說明
1. 本表只整理手冊第06章已寫明的 E01 至 E10，不新增需求。
2. 「測試方式」欄標示 mock（模擬）或 live（真實執行）。標「待確認」的是D的初步判斷，手冊沒有明寫，需與B和組長確認。
3. 「證據」欄目前全部是待填，因為還沒有任何測試實際執行。沒有執行就不能寫已通過。
4. mock 結果和 live 結果必須分開記錄，不能把模擬當成實測。

------------------------------------------------------------
E01　三個固定示範案例真的執行
輸入：2330、2317、2454 各一個案例
預期狀態：有可用配額時真的執行；工具路徑會隨證據不同而改變；至少一次覆核要求補查後修正；至少一次因證據不足而停止
測試方式：live（手冊明寫 Replay 只證明回放，不能當 live）
分母：3 個示範案例
證據：三個示範案例的 live 執行 尚未執行（0/3）。
已有的相關紀錄：handoff/quota-test-log.md 記載 2026-09-28 17:27 經組長核准的 1 次 live 連線驗證（3 次模型呼叫、合成資料 synthetic_fixture: true、只查 2330 五日價），那是連線驗證，不能當成 E01 通過。
前提：需要組長確認實際可用配額

E02　預算上限由程式阻擋
輸入：用 mock 故意超過 8 次模型發送、10 次工具呼叫、2 輪補查
預期狀態：超過上限的那一次被程式阻擋，不會繼續執行
測試方式：mock（手冊明寫以 mock 驗證邊界並有 log）
分母：3 種上限各測一次
證據：三種上限都有 mock 測試（tests/test_budget_tools.py），已讀過測試內容：
1. 8 次模型發送：test_eight_call_cap_counts_failures_and_is_persisted（失敗也計入、並保存）。
2. 10 次工具呼叫：test_tool_limits。get_price_window 2 次後第 3 次被擋；read_evidence 連續 8 次後第 9 次被擋，reason 為 tool_limit。2+8=10 次後再呼叫被擋，與手冊一致。get_price_window 第 3 次被擋是另一條規則（疑似單一工具上限），細節待核對。
3. 2 輪補查：test_supplement_rounds_and_active_time。第 1、2 輪可以，第 3 輪被擋。同一測試另外驗證活動時間：179 秒可以，再加 2 秒被擋且 job_status 為 timed_out（手冊 E02 沒寫此項，為額外保護）。
全部離線測試：2026-10-08 本機 ~/fintech-venv/bin/python -m pytest -q tests，111 passed in 29.72s。
性質：mock，不是 live。
結論（D 初判，待 B 與組長確認）：三種上限的 mock 邊界測試皆存在且通過。

E03　重複送件與中斷重啟
輸入：同一任務重複送 20 次；worker 中途中斷後重啟；模糊的網路結果
預期狀態：只產生 1 個有效 job；中斷重啟不重設預算、不重複發布；模糊結果先存成未確定狀態，不宣稱 exactly-once 模型計費
測試方式：待確認（建議先 mock，授權測試環境再做 live）
分母：待確認
證據：已讀過 tests/test_jobs_queue.py 的測試內容，目前是部分覆蓋：
1. 重複送件：test_duplicate_create_returns_same_job 同一請求送 2 次，第 2 次不建立新 job，兩次 job_id 相同。手冊要求 20 次，現有測試只送 2 次，次數不足（D 判斷，待確認是否補 20 次的測試）。另有 test_only_one_active_job、test_api_create_is_idempotent_and_status_readable，內容尚未讀。
2. 中斷重啟：test_job_survives_process_restart 建立 job 後關閉並重開資料庫，job 仍在、狀態為 queued、事件只有 job_created。只證明排隊中的 job 不會遺失。
3. 另有 test_expired_lease_is_recovered_and_stale_worker_is_fenced、test_heartbeat_keeps_lease（worker 租約相關），內容尚未讀。
4. 尚未找到的：重啟後預算不重設、不重複發布、模糊網路結果存成未確定狀態。
全部離線測試：111 passed in 29.72s（mock）。
結論：部分有測試，不能寫通過。

E04　安全阻擋
輸入：未知工具、未授權來源ID、假引用、資料內的 prompt injection、未授權建立 job、未授權發布
預期狀態：全部阻擋；模型沒有任意網路、檔案或 shell 工具
測試方式：待確認（目前找到的相關測試都是 mock）
分母：6 種攻擊各至少一筆
證據：已用測試名稱與關鍵字（inject、forged、fake、unknown_source、not_authorized、publish）搜尋 tests/ 全部測試檔，結果如下（只看名稱與關鍵字，多數測試內容尚未逐行讀）：
1. 未知工具：有。test_unregistered_tool_returns_fixed_no_data、test_reviewer_tool_escalation_is_refused_by_dispatch、test_reviewer_cannot_search_or_fetch_prices。
2. 未授權來源ID：測試中未找到。
3. 假引用：測試中未找到（test_evidence_missing_or_unreferenced 看起來是顯示缺來源，不是阻擋假引用，待確認）。
4. 資料內的 prompt injection：測試中未找到（test_query_filter、test_no_url_path_or_sql 擋的是惡意查詢字串，是另一種防護）。
5. 未授權建立 job：有。test_unauthorized_requests_rejected、test_api_is_closed_when_no_token_configured、test_entry_closed_when_mock_disabled。
6. 未授權發布：部分相關。有 test_unpublished_report_never_leaves_server（未發布報告不外流），但沒找到「未授權者不能發布」的測試。
另有「模型沒有任意網路、檔案、shell 工具」相關：test_no_url_path_or_sql、test_still_six_tools_and_peer_comparison_is_an_operation。
統計：6 種攻擊中，有對應測試 2、部分相關 1、測試中未找到 3。
說明：「測試中未找到」不等於系統沒有防護，可能程式有擋但沒有測試，需向B確認。
全部離線測試：111 passed in 29.72s（mock）。
結論：目前不能寫通過。

E05　公開報告品質
輸入：所有要公開的報告
預期狀態：每份公開報告引用 100% 可解析，且沒有未解決的 critical issue；不通過就只顯示研究不足或未發布，不勉強湊報告
測試方式：live
分母：公開報告數
證據：尚未執行（live，0 份已檢查）。
repo 現況：只看到 mock/UI 層的相關測試，例如 test_report_detail_marks_claim_kinds_and_unsourced（報告頁標示主張類型與無來源）、test_evidence_missing_or_unreferenced、test_unpublished_report_never_leaves_server（未發布報告不外流）。這些不等於「每份公開報告引用 100% 可解析」的檢查。
分母「公開報告數」目前不確定，待與B、組長確認哪些報告算公開。

E06　網站與 PDF 一致
輸入：同一份報告的網站版與 PDF 版；桌機 1440x900 與手機 390x844；PDF 至少三份
預期狀態：來源快照、文字、數字、版本一致；中文不缺字、不切頁重疊、來源可點
測試方式：live，人工加自動截圖檢查
分母：PDF 份數（至少 3）
證據：尚未執行（live，0/3 份 PDF 已比對）。
repo 現況：PROJECT_STATUS.md（最後更新 2026-05-30，內容可能已過時）寫公開網站版預設略過 PDF 產生，PDF 只在本機版 report_builder.py 產出。桌機 1440x900 與手機 390x844 的截圖檢查尚未做。

E07　負載測試
輸入：預熱的 2GB 環境，10 位唯讀訪客持續 5 分鐘，同時 1 個研究 job
預期狀態：無 OOM、無 HTTP 5xx；唯讀 API p95 目標小於 2 秒；RSS 峰值目標小於 1.5GB
測試方式：live
分母：5 分鐘測試期間的全部請求數
證據：尚未執行（live）。
需向組長確認：PROJECT_STATUS.md 與 render.yaml 顯示公開網站是 Render Free（PROJECT_STATUS.md 寫 512MB RAM），但手冊 E07 要求預熱的 2GB 環境。實際用哪個環境測，請組長確認。
備註：未達標就要修正或標示限制，不能說 2GB 必然足夠

E08　純讀與故障狀態
輸入：開啟已發布頁面與 PDF；關閉 Gemini；模擬資料庫或 worker 故障
預期狀態：純讀 0 次 LLM；關閉 Gemini 後仍可讀舊報告；新研究顯示不可用而不是空白；資料庫或 worker 故障有清楚狀態
測試方式：待確認
分母：待確認
證據：部分有 mock 測試，live 尚未執行。
測試名稱顯示有對應：test_reading_pages_never_starts_analysis、test_read_only_ui_has_no_model_code、test_page_renders_without_secrets_or_sync_analysis（純讀不啟動分析、純讀頁面沒有模型呼叫程式）；test_each_status_screen_reaches_its_state 涵蓋 succeeded、insufficient_evidence、paused_quota、failed、timed_out 五種狀態畫面；test_status_is_read_from_db_by_another_process。
以上只看名稱，內容尚未逐行讀。
尚未找到：「關閉 Gemini 後仍可讀舊報告」「資料庫故障畫面」的明確測試，待向B確認。
全部離線測試：111 passed in 29.72s（mock）。

E09　建置、測試與還原
輸入：建置、既有測試、新增的 Agent 與 DB 測試、憑證掃描、rollback 與備份還原演練
預期狀態：實際通過；憑證無外洩；有 rollback 與備份還原演練紀錄
測試方式：live
分母：待確認
證據：部分已做。
1. 既有與新增測試：2026-10-08 本機 ~/fintech-venv/bin/python -m pytest -q tests，111 passed in 29.72s（離線 mock）。
2. 憑證：2026-10-09 檢查 .env 沒有被 git 追蹤（git ls-files .env 結果為 0），.gitignore 有 .env 與 .env.*。這只是初步檢查，不是完整的憑證掃描（尚未掃描 git 歷史與全部檔案）。
3. 建置：尚未執行。
4. rollback 與備份還原演練：尚未找到紀錄，待向B確認。
5. Supabase migration 與資料表相關項目：尚未執行。
結論：不能寫通過。目前 repo 最新 commit 為 4f67d15（Merge pull request #2，W04-A）。

E10　正式實驗
輸入：20 個保留案例 x 3 種模式（Workflow、Single、Dual），共 60 run
預期狀態：完整記錄與評分；失敗的 run 也保留；證據支持率 90% 只是改善目標，真實結果照報
測試方式：live
分母：60 run
證據：尚未執行（0/60 run）。依手冊只能在 W10、W11 執行，目前不做。
備註：只能在 W10、W11 執行，不得用保留案例的答案調整 prompt

------------------------------------------------------------
待確認事項（交給B或組長）
1. E01 實際可用的配額，由組長確認。（quota-test-log 記載 9/28 當天 live 額度用掉 3/500，三個示範案例的 live 還沒跑。）
2. E03、E04、E08 哪些先用 mock、哪些要 live，與B討論後定案。
3. E03、E04、E08、E09 的分母，與B討論後定案。
4. 本檔 E01 到 E10 之外，N01 到 N08 的對應表會放在 v12-acceptance.md，尚未完成。

交付紀錄（填寫用）
版本：v5 草稿
實際工時：待填
驗收人確認日期：待填
