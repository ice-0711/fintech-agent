# Quota／預算測試紀錄（W03-L）

## 2026-09-28 離線（MOCK）測試 — 已執行

- 環境：macOS、Python 3.14.7、google-genai 2.25.0、langgraph 1.2.12、pytest 9.1.1
- 基於 commit：`69fb3f2`＋本次 W01–W03 組長變更
- 命令：`.venv/bin/python -m pytest -q tests`
- 結果：**52 passed, 1 warning**（warning 為 google-genai 在 Python 3.14 的 `_UnionGenericAlias` DeprecationWarning，非本專案程式）
- 變異檢查：暫時把 `max_calls` 改為 9 → `test_eight_call_cap_counts_failures_and_is_persisted`、`test_retries_share_the_eight_call_cap` 失敗（2 failed, 50 passed），確認測試真的會擋；已改回 8 並重跑通過。

| 驗收項 | 測試 | 結果 |
|---|---|---|
| 8 次上限含失敗 | `test_eight_call_cap_counts_failures_and_is_persisted`、`test_non_retryable_error_counts_and_raises` | 通過（MOCK） |
| 重試共用 8 次上限 | `test_retries_share_the_eight_call_cap`、`test_429_retry_once_then_pause_and_both_sends_counted` | 通過（MOCK） |
| usage 記錄 model/prompt 版本 | `test_usage_records_model_and_prompt_version` | 通過（MOCK） |
| 不啟用付費 fallback | `test_no_fallback_model`；程式無備援 model 路徑 | 通過 |
| 仍六工具 | `test_still_six_tools_and_peer_comparison_is_an_operation` | 通過 |
| 參照股不新增 LLM job | `test_comparison_only_tickers_do_not_create_llm_jobs`、`test_api_rejects_reference_ticker` | 通過 |
| peer_comparison 最多 4 家 | `test_peer_comparison_rejections` | 通過 |
| 未核實 quota 不送出 | `test_unknown_quota_blocks_live_sends`、`test_unknown_quota_sends_nothing` | 通過 |

## 2026-09-28 thinking 修正後重跑 — 已執行

- 變更：改用 `thinking_level`（預設 minimal），thinking 計入 1,500 輸出上限；model 鎖定 `gemini-3.6-flash`。
- 命令：`.venv/bin/python -m pytest -q tests` → **56 passed, 1 warning**。
- 新增：thinking 預設 minimal、model 不支援的等級拒絕啟動、thought signature 原樣回傳、預留不再另加 thinking。

## 2026-09-28 17:27 Live 驗證（組長核准，最多 3 次）— 已執行

- 命令：`.venv/bin/python scripts/live_check.py`（commit `28e9354`）；硬上限 3 次、無重試；本機暫存 DB，未碰 Supabase；工具回傳合成資料（`synthetic_fixture: true`）。
- model：`gemini-3.5-flash-lite`，回傳 model_version 同名；thinking_level minimal（`thoughts_token_count` 為 null）。
- job：`5695361b-f212-4dbe-a50b-b4a9aae4720a`；`calls_used` 3、`tokens_observed` 2,875；今日額度用掉 3/500。

| 次 | 角色 | 內容 | 結果 | prompt / 輸出 / total token | 送出前預留 |
|---|---|---|---|---|---|
| 1 | reviewer | 只回「連線正常」 | 回「連線正常。」，未呼叫工具 | 597 / 4 / 601 | 1,595 |
| 2 | researcher | 查 2330 五日價 | 呼叫 `get_price_window`（參數通過驗證，工具回 ok） | 1,007 / 57 / 1,064 | 1,638 |
| 3 | researcher | 帶回工具結果 | 正確說明資料標示為合成、非真實股價 | 1,181 / 29 / 1,210 | 2,015 |

- **工具往返**：官方 SDK 真實往返成功；`thought_signature` 有原樣帶回（True）。
- **發現 1（已修）**：輸入預估少算。預留中的輸入估計只有 95／138／515，實際 prompt 為 597／1,007／1,181，因為工具宣告本身也計入輸入（約 500–900 token）。已改為把該角色的工具宣告納入預估；以相同內容離線重算，send 1 預估 1,074（實際 597）、send 2 預估 1,683（實際 1,007），恢復保守。新增測試 `test_estimate_counts_tool_declarations`。
- **發現 2（已修）**：`model_usage.prompt_version` 記成 job 的 `v1.2`，事件記的是 adapter 的 `live-check-v1`，不一致。已改為兩處都記 adapter 版本；新增測試 `test_ledger_uses_adapter_prompt_version`。
- 修正後 `.venv/bin/python -m pytest -q tests` → **58 passed**。修正後未再發送 live 請求。

## 待 W04 注意（不在本週範圍）

- 研究員一開始的輸入就約 1,000 token（實際）／1,700（預估），3,000 輸入上限在多輪補查時可能偏緊；預估約高估 1.7 倍，W04 可依累積的 live usage 校準係數，須經組長核准並保持不少算。

## 2026-10-28 換 API key（原專案失去免費層）

- 10/27 22:40 校準第 1 天：原 `.env` key 所屬專案回 403「The Gemini API free tier is not available for this project」。該 job 記為 failed（2 次發送，0 費用），其餘 5 個未執行。
- 10/28 組長在 AI Studio 核對：原 key 不在「Default Gemini Project」（gen-lang-client-0059508299）。組長自行把 `.env` 換成該專案的 key（結尾 ioqw；Claude 未讀取 key 值）。
- 新專案仍為 Free tier；gemini-3.5-flash-lite 上限 RPM 15／TPM 250K／RPD 500，與 `quota-baseline.json` 相同，J=6 不變。測試請求成功。
- 未開通付費，維持 10/23「不換付費」決定。
