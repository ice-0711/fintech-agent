# W08-D 安全與故障注入測試

- 任務 ID:W08-D|負責:D(吳維彬)|日期:2026-11-07(補交,期限原為 11/06)
- 驗收人:B 交叉評分,組長核准結論(**尚未驗收**)
- 實際工時:約 1 小時(D 自己估計)
- 基準:origin/main 40d058b(第一次跑)與 8e2cb17(同日組長更新後重跑,以此為準)
- 環境:D 的電腦,Python 3.10.12、pytest 9.1.1,離線,不連網,不碰正式 Supabase / Gemini / Render。**全部是 mock 與本機 SQLite,不是上線環境測試。**

## 一、做法

1. 抓 origin/main 最新版,照 handoff/agent-test-commands.md 跑全部離線測試。
2. 依任務要求(429、timeout、DB 暫失、worker 中斷、未授權端點、假引用、重複 20 請求),找出現有測試對應哪一項。
3. 現有測試只重複 2 次的項目,新增 tests/test_w08d_repeat20.py(組長 11/08 合併時移入 tests/，全套測試會一起跑) 實測 20 次。

## 二、實際命令與結果

| 命令 | 結果 |
|---|---|
| python3 -m pytest tests(改動前) | 413 passed in 35.67s |
| python3 -m pytest tests/test_w08d_repeat20.py -v(此檔先複製到 tests/) | 2 passed in 0.09s |
| python3 -m pytest tests(40d058b,加入新測試後) | 415 passed in 32.18s |
| python3 -m pytest tests(8e2cb17,加入新測試後) | **417 passed in 33.20s**(比 40d058b 多的 2 項是組長新增,不是我加的) |

各檔(8e2cb17 重跑,數字與 40d058b 相同):test_provider_mock 15、test_audit_fixes 21、test_tool_fixtures 41、test_research_graph 29、test_jobs_queue 20、test_w08_safety 41、test_budget_tools 30、test_w08d_repeat20 2(皆 passed)。

## 三、要求對照

| 要求 | 對應測試 | 結果 | 備註 |
|---|---|---|---|
| 429 | test_provider_mock::test_429_retry_once_then_pause_and_both_sends_counted;test_retries_share_the_eight_call_cap | 通過 | MOCK |
| timeout | test_audit_fixes::test_client_timeout_is_counted_and_retried_once;test_tool_fixtures::test_timeout_becomes_tool_error;test_research_graph::test_simulated_tool_timeout_counts_active_time_and_job_continues | 通過 | MOCK |
| worker 中斷 | test_jobs_queue::test_expired_lease_is_recovered_and_stale_worker_is_fenced;test_heartbeat_keeps_lease | 通過 | 假時鐘模擬,不是真的殺 process |
| 未授權端點 | test_jobs_queue::test_unauthorized_requests_rejected;test_api_is_closed_when_no_token_configured | 通過 | 缺 token、錯 token 皆 401 |
| 假引用 | test_w08_safety::test_read_evidence_bad_ids_refused_before_tool_runs;test_other_case_evidence_id_is_not_readable_in_this_job;test_holdout_style_id_is_not_readable_from_a_dev_job | 通過 | |
| 外部文字不當指令 | test_w08_safety::test_injection_text_cannot_reach_tools_as_arguments;test_tools_ignore_instructions_inside_sources | 通過 | |
| 重複 20 請求(有授權) | evaluation/d-drafts/W08-D/test_w08d_repeat20.py::test_20_identical_authorized_requests_create_one_job | 通過 | 第 1 次 202,後 19 次 200,job_id 只有 1 個,資料表只有 1 筆 |
| 重複 20 請求(未授權) | evaluation/d-drafts/W08-D/test_w08d_repeat20.py::test_20_unauthorized_requests_all_401_and_create_nothing | 通過 | 20 次皆 401,沒有建立 job |
| DB 暫失 | test_audit_fixes::test_crashing_tool_returns_fixed_error(工具拋出 "db down",回固定錯誤 tool_error,不當機) | 通過(僅限 mock 的工具故障) | 真實 Supabase 版 JobStore 的資料庫暫失:**未執行**。目前沒有授權的測試資料庫,不對正式庫注入故障 |

## 四、E02/E03/E04/E08/E09 對照與缺口

編號與內容依 evaluation/d-drafts/W01-D/acceptance-v5.md(來源:專題手冊第 06 章)。本次沒有出現失敗的測試,所以沒有新增可重現的缺陷;下表是「有測試的」與「缺口」。缺口不是已發現的錯誤。

| 編號 | 項目 | 現有測試(皆 mock,通過) | 缺口(本次未執行) |
|---|---|---|---|
| E02 | 預算上限由程式阻擋 | test_budget_tools:test_eight_call_cap_counts_failures_and_is_persisted、test_tool_limits、test_supplement_rounds_and_active_time | 無 |
| E03 | 重複送件與中斷重啟 | 20 次重複請求(本次新增,2 項);test_job_survives_process_restart;test_expired_lease_is_recovered_and_stale_worker_is_fenced | 「模糊網路結果存成未確定狀態」「不重複發布」:本次沒找到對應測試 |
| E04 | 安全阻擋 | test_w08_safety(41 項:未知工具、假引用與他案/保留案 evidence id、來源文字不當指令);未授權建立 job 20 次皆 401 | 「未授權發布」:本次依測試名稱搜尋,沒找到專門測試(只有未發布報告不外流的 test_unpublished_report_never_leaves_server) |
| E08 | 純讀與故障狀態 | test_research_ui:test_reading_pages_never_starts_analysis、test_read_only_ui_has_no_model_code、test_page_renders_without_secrets_or_sync_analysis;test_audit_fixes::test_crashing_tool_returns_fixed_error | 「關閉 Gemini 後仍可讀舊報告」「資料庫故障畫面」:本次沒找到測試;真實 DB 暫失:未執行 |
| E09 | 建置、測試與還原 | 全部離線測試 417 passed | 建置、憑證掃描、rollback:D 本次未執行。備份還原演練紀錄見 handoff/backup-restore-log.md(組長 W08-L,D 沒有重跑) |

責任人:E03、E08 缺口與真實 DB 暫失需要組長提供授權測試資料庫後才能測;其餘缺口請 B 或組長決定是否補測。

## 五、限制

- 離線 mock 結果只能證明程式邏輯,不能證明上線環境行為。
- 20 次重複請求是循序呼叫(Flask test client),不是 20 個並行連線。

## 六、未完成與原因

| 項目 | 原因 | 提供人 |
|---|---|---|
| 真實 DB 暫失注入 | 無授權測試資料庫 | 組長 |
| 並行 20 請求 | 本次只做循序 | D 可在後續補 |

## 七、組長補註（2026-11-08，合併時）

- 新測試已移到 `tests/test_w08d_repeat20.py`，全套 417 項通過（含這 2 項）。
- 第四節列為缺口、但其實已有測試的：
  - E03「不重複發布」：`tests/test_publication.py::test_publish_renders_real_pdf_and_never_overwrites`（已發布不可再發布、Storage 不可覆寫）。
  - E04「未授權發布」：`tests/test_publication.py::test_api_approval_needs_the_logged_in_lead_not_a_token`（核准需組長登入，token 不行）；`tests/test_jobs_queue.py::test_admin_login_closed_without_password`。
  - E08「沒有 Gemini 也能讀」：Render 上本來就沒有 Gemini 金鑰，11/02、11/06 兩份 LIVE 報告都在此條件下公開閱讀與下載（`handoff/deployment-v1.md` 第四節）。
  - E09「還原」：`handoff/backup-restore-log.md`（11/02、11/06 兩次匯出還原核對通過）；rollback 程序見 `handoff/deployment-v1.md` 第五節。
- 真實資料庫暫失：Supabase 測試專案的金鑰只在組長端，不外發；此項列為未執行，寫進限制。
