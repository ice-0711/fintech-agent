# W07-A｜線上研究 PDF 驗收紀錄（layout report）

- 任務 ID：W07-A｜日期 2026-10-26｜負責：A（陳柏臣）｜驗收人：組長（**尚未驗收**）
- 分支：`codex/W07-A-online-pdf`（含 `codex/A-fixture-mops-text` 的 a80e436，見第 6 節）
- 依據：手冊第 04 章 F05、W07-A 步驟 1–4；組長 10/21、10/22 核定（`handoff/decisions-2026-10.md`）

## 1. 這次做了什麼

| 步驟 | 做法 | 程式 |
|---|---|---|
| 1. 同一份核准 JSON 產 PDF | 報告版本建立時，把季度表、DCF 假設與敏感度、資料品質、2454 同業比較、價格窗、來源（含 hash 核對）用 B 的工具算好，**凍結進報告 JSON 的 `data` 欄**；網頁與 PDF 都只讀這一份。PDF 用 fpdf2（沿用 `report_builder.ReportPDF` 與內嵌思源黑體），圖表沿用 `chart_builder` 的股價圖與 DCF 瀑布圖，畫在暫存資料夾，嵌入後即刪，不留在 `output/`。 | `research_ui/report_data.py`、`research_ui/report_pdf.py`；組長 `agents/publication.py` 加接點 |
| 2. 存 Storage、接網站 | 發布走組長的 `ReportStore`：核准（比對組長看過的 hash）→ 產 PDF → 寫入 Storage（不可覆寫）→ 讀回比對 hash。網站新增預覽、下載（attachment）、同一 job 的已發布歷史版本。Storage 設定 `SUPABASE_URL`、`SUPABASE_SERVICE_KEY`、`REPORT_STORAGE_BUCKET` 時改用 Supabase（私有 bucket，金鑰只在伺服器）。 | `research_ui/__init__.py`、`research_ui/storage_supabase.py`；組長 `agents/api.py` 一行切換 |
| 3. 測三份 PDF | 2330、2317、2454 各一份，見第 2–3 節 | `scripts/w07_acceptance_pdfs.py`、`scripts/w07_pdf_check.py` |
| 4. F06 2D | 組長 10/22 核定**延後**，本週不畫 | `ui/v12-graph-draft/README.md` |

## 2. 三份驗收 PDF

產生方式：MOCK `revise_then_pass`（模型決策為預錄腳本、工具結果為 B 快照真實輸出；**PDF 首頁標示「MOCK 測試報告：不是研究結論」**），資料截止 2026-09-30 17:30（台北，與 B 同業快照相同）。每份都經過 建立版本 → 核准 hash → 發布 → 從 Storage 讀回並驗 hash；資料夾內的 PDF 是讀回的驗收副本，**不是永久檔**。

| 股票 | 版本 | 報告 hash（前 16） | PDF hash（前 16） | Storage key |
|---|---|---|---|---|
| 2330 | `rv-b0062cc2-0f9f-4d09-ace2-f4fe9997bbf9` | 36e86bc4dbc67da6 | 5071400a0f76654d | reports/2330/rv-b0062cc2-….pdf |
| 2317 | `rv-8e567646-9803-49d1-9399-d396c14bf029` | e3b3d50fc885234d | 8b4cd30871e66367 | reports/2317/rv-8e567646-….pdf |
| 2454 | `rv-393f3b6f-6002-4f97-8cde-e3f68306af77` | d9c6f14f5c7eeebe | 7b2928eb8afeb687 | reports/2454/rv-393f3b6f-….pdf |

檔案：`reports/v12-online-pdf/`（PDF、核准 JSON、`manifest.json`、每頁縮圖 `pages/`）。

## 3. 版面與內容檢查（`python scripts/w07_pdf_check.py` 輸出）

| 股票 | 頁數 | 大小 | 內嵌字型 | 連結 | 圖 | JSON 關鍵項目在 PDF 內 | PDF hash | 結果 |
|---|---|---|---|---|---|---|---|---|
| 2330 | 3 | 398 KB | NotoSansCJKTC（子集） | 1 | 2 | 18/18 | 相符 | 通過 |
| 2317 | 2 | 234 KB | NotoSansCJKTC（子集） | 1 | 1 | 17/17 | 相符 | 通過 |
| 2454 | 3 | 393 KB | NotoSansCJKTC（子集） | 1 | 2 | 22/22 | 相符 | 通過 |

「關鍵項目」= 每一條主張、每一條限制、估值狀態、資料品質風險、免責聲明、每季營收、DCF 每股、每個來源 ID、每家同業。全部在 PDF 文字中找得到 → 沒有被截斷的關鍵風險。上限：≤ 10 頁、≤ 5 MB（超過時 `render_report_pdf` 直接拒絕，測試 `test_pdf_over_page_limit_is_refused`）。

F05 必要內容對照（以 2454 為例）：

| F05 項目 | PDF 位置 |
|---|---|
| 研究問題／cutoff | 第 1 頁表頭（台北時間） |
| 主張／反證 | 「主張（事實／推論／未知）」、「反向證據與矛盾」（本 MOCK 沒有反證，該段不出現；網頁顯示「無」） |
| 季度資料 | 5 季表（營收、營業利益、淨利、EPS 與來源、FCF、可得時間）＋ TTM |
| 同業比較（2454） | 2454／2379／3034／2330（產業參照，不入平均）＋同業平均與排除項 |
| DCF 與敏感度 | WACC 9%、g 3%、5 年持平；拆解數字；WACC ±1% × g ±0.5% 表；DCF 瀑布圖 |
| 資料品質風險 | 第 1 頁「估值狀態與資料品質」＋兩條固定註腳 |
| 未知 | 「未知事項」 |
| 來源 | 來源 ID、可得時間、sha256 是否相符、摘錄 ≤ 200 字、可點的 MOPS 原始連結 |
| 版本及方法限制 | 報告版本／hash／核准人與時間；「方法與限制」5 條固定說明＋方法版本 |
| 不經 LLM 改寫 | `report_pdf.py` 只排版 JSON，不呼叫模型；`test_public_reads_make_no_llm_calls` |

逐頁目視（`reports/v12-online-pdf/pages/`）：中文無缺字、表格不超出版面、圖表置中、頁尾頁碼正確。2317 估值顯示「無法判定：TTM FCF ≤ 0，5 年持平情境不適用」，不出現負的 DCF。

## 4. 網站與手機

本機以 `RESEARCH_UI_MOCK=1` 加上述版本庫啟動 `web_app.py`，用 Chromium（Playwright）測：

| 檢查 | 1440 寬 | 390 寬（iPhone 13 模擬） |
|---|---|---|
| 已發布清單出現 3 份真實版本（標 MOCK）＋FIXTURE 範例（標 FIXTURE） | ✓ | ✓ |
| 報告詳情顯示同一份 JSON 的季度表、DCF、同業表、歷史版本 | ✓ | ✓（表格在框內左右捲動） |
| 「下載 PDF」觸發下載，檔名 `2454-v1-rv-….pdf`，402,395 bytes，檔頭 `%PDF-`，與驗收副本同大小 | ✓ | ✓ |
| `/reports/<rv>.pdf` 預覽：200、`application/pdf`、inline | ✓ | — |
| 頁面錯誤、橫向捲動 | 無 | 無 |
| 不存在的版本下載 → 404 | ✓ | ✓ |

截圖：`design/w07/W07-published-list-{1440,390}.png`、`design/w07/W07-report-2454-{1440,390}.png`。

**限制**：手機測試是桌面 Chromium 的手機模擬，不是實機 iOS Safari／Android Chrome；請組長在部署後用手機實測一次下載。

## 5. 安全與發布規則（測試：`tests/test_online_pdf.py`，10 項）

- 草稿版本不出現在公開清單、詳情、下載（404）；訪客核准 403。
- 組長核准必須帶「看過的 hash」；hash 不符 409，不發布。
- 同一 job 第 2 版發布後，第 1 版 PDF 仍可下載且內容不變（write-once）；歷史版本只列已發布。
- 公開讀取（清單、詳情、下載）0 次 LLM。
- Supabase adapter 不可覆寫；沒有三個環境變數時回到本機資料夾。

## 6. 尚未完成／需要別人

| 項目 | 狀態 | 需要誰 |
|---|---|---|
| Supabase Storage 實測 | adapter 只用假 client 測過；**未連真實專案** | 組長建立測試專案與私有 bucket，在 Render 設 `SUPABASE_URL`、`SUPABASE_SERVICE_KEY`、`REPORT_STORAGE_BUCKET` |
| 「公開下載不用本機」 | 程式已支援；**在設好 Supabase 前，Render 上仍是本機資料夾，重新部署會遺失** | 同上 |
| 報告版本資料庫 | `ReportStore` 仍是 SQLite；Render 重新部署也會遺失版本紀錄 | 組長決定（Supabase table 或 Render disk） |
| LIVE（真實模型）報告 | 研究入口仍只開 MOCK（組長 10/05 決定）；目前三份都是 MOCK 標示 | 組長決定何時開 LIVE |
| 實機手機 | 只有模擬 | 組長部署後實測 |
| 分支依賴 | 本分支含 a80e436（FIXTURE 改 MOPS 原文）；若 `codex/A-fixture-mops-text` 先合併，這個 commit 會自動略過 | 組長合併順序 |
