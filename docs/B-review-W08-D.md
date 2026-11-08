# B 核對：D 的 W08-D（PR #27）

- 核對人：組員 B｜日期：2026-11-07｜對象：`evaluation/fault-and-security-w08.md`、`evaluation/v12-load-graph-check.md`、`evaluation/d-drafts/W08-D/test_w08d_repeat20.py`（PR #27，91df3eb）
- 結論：**通過，建議合併前補 3 處文字**。D 列的測試都存在，B 在 Windows 重跑 417 項全過；引用 A 的效能數字和原始檔一致；沒有把 mock 寫成上線結果。另外，第四節列的「缺口」裡有 3 項其實已有測試。

## 一、逐項核對

| 項目 | B 核對方式 | 結果 |
|---|---|---|
| 第三節 23 個測試名稱 | 在 PR #27 版本的 `tests/` 逐一搜尋函式名稱 | ✅ 23 個都存在，檔名與 D 寫的一致 |
| 新增 20 次重複請求測試 | 讀程式：第 1 次 202、後 19 次 200，job_id 1 個、資料表 1 筆；未授權 20 次皆 401、0 筆 | ✅ 邏輯與文件一致 |
| 417 passed | B 2026-11-08 在 Windows（使用者電腦，.venv）重跑：main 8e2cb17 `python -m pytest -q tests` **415 passed**；D 新增的 `test_w08d_repeat20.py` 暫時複製到 tests 執行 **2 passed**（跑完刪除，未上傳） | ✅ 415＋2＝417，與 D 一致 |
| 效能數字（第二節） | 對照 `performance/v12-read-only.json` 與 `design/performance-w08.md` | ✅ 9,293 筆、p95 14.8 ms、發布期間 2,428 ms、5xx 0、RSS 479／502／293 MB 全部相符 |
| F06 抽核未執行 | F06 已延後（組長 10/22、11/06 關閉） | ✅ 照實記「未執行」是對的 |

## 二、第四節「缺口」需要更正的 3 項（已有測試）

| 編號 | D 寫的缺口 | 實際有的測試 |
|---|---|---|
| E03 | 不重複發布 | `tests/test_research_graph.py::test_finished_job_is_not_rerun_or_republished`；`tests/test_publication.py::test_publish_renders_real_pdf_and_never_overwrites` |
| E04 | 未授權發布 | `tests/test_research_graph.py::test_reviewer_cannot_publish`；`tests/test_online_pdf.py::test_draft_is_not_public_until_the_lead_approves_the_seen_hash`；`tests/test_review_risk.py::test_logged_in_lead_needs_a_version_and_hash_before_publishing` |
| E08 | 關閉 Gemini 後仍可讀舊報告 | `tests/test_online_pdf.py::test_public_reads_make_no_llm_calls`（公開閱讀 0 次模型呼叫）；`tests/test_research_ui.py::test_read_only_ui_has_no_model_code` |

以上都是 mock／本機測試，不是上線環境。

## 三、確實沒有測試的（照 D 寫的維持「未執行」）

- E03「模糊網路結果存成未確定狀態」：B 在 `tests/`、`agents/`、`research_ui/` 也沒找到。
- E08「資料庫故障畫面」與真實 Supabase 暫失：需要組長提供授權測試資料庫。
- 並行 20 請求：本次只測循序。