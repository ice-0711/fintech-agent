# W08-D 安全與故障注入測試

- 任務 ID:W08-D|負責:D(吳維彬)|日期:2026-11-07(補交,期限原為 11/06)
- 驗收人:B 交叉評分,組長核准結論(**尚未驗收**)
- 實際工時:約 1 小時(D 自己估計)
- 基準:origin/main 40d058b(第一次跑)與 8e2cb17(同日組長更新後重跑,以此為準)
- 環境:D 的電腦,Python 3.10.12、pytest 9.1.1,離線,不連網,不碰正式 Supabase / Gemini / Render。**全部是 mock 與本機 SQLite,不是上線環境測試。**

## 一、做法

1. 抓 origin/main 最新版,照 handoff/agent-test-commands.md 跑全部離線測試。
2. 依任務要求(429、timeout、DB 暫失、worker 中斷、未授權端點、假引用、重複 20 請求),找出現有測試對應哪一項。
3. 現有測試只重複 2 次的項目,新增 evaluation/d-drafts/W08-D/test_w08d_repeat20.py(複製到 tests/ 資料夾後才能執行,因為要用 tests/conftest.py) 實測 20 次。

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
| DB 暫失 | 無 | **未執行** | 現有程式沒有 Supabase 版 JobStore 的失敗注入測試;本次沒有授權的測試資料庫,不對正式庫注入故障 |

## 四、缺陷清單

- 本次測試沒有出現失敗的測試,所以沒有新增可重現的缺陷。
- 缺口(不是已發現的錯誤):
  1. DB 暫失沒有測(原因見上)。責任人:組長(提供測試專案與 Supabase 版 JobStore 後才能測)。
  2. worker 中斷是假時鐘模擬,沒有真的結束 process。
  3. 全部是 mock,不能當成 Render 上線結果。
- 任務書寫的缺陷編號 E02/E03/E04/E08/E09,我在 repo 找不到定義,所以沒有對號入座。【請組長或 B 告知編號對應,再補】

## 五、限制

- 離線 mock 結果只能證明程式邏輯,不能證明上線環境行為。
- 20 次重複請求是循序呼叫(Flask test client),不是 20 個並行連線。

## 六、未完成與原因

| 項目 | 原因 | 提供人 |
|---|---|---|
| DB 暫失注入 | 無授權測試資料庫 | 組長 |
| 並行 20 請求 | 本次只做循序 | D 可在後續補 |
