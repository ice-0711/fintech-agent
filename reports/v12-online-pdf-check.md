# W07-A｜線上研究 PDF 驗收紀錄（layout report）

- 任務 ID：W07-A｜日期 2026-10-26；**2026-10-29 依 B 稽核修正（第 0 節），三份 PDF 重新產生**｜負責：A（陳柏臣）｜驗收人：組長（**尚未驗收**）
- 分支：`codex/W07-A-online-pdf`（含 `codex/A-fixture-mops-text` 的 a80e436，見第 6 節）
- 依據：手冊第 04 章 F05、W07-A 步驟 1–4；組長 10/21、10/22 核定（`handoff/decisions-2026-10.md`）

## 0. 2026-10-29 修正（B 的 W07 稽核，`evidence-audit-w07.md` 第七節）

| B 指出的問題 | 修正 | 程式 |
|---|---|---|
| 問題 1（fail）：c2「近四季 EPS 合計（TTM）」3 份都引用 2026Q2 公告片段，但片段沒有 TTM；2317 c1「單季 EPS 4.27」引用的公告是 1–6 月累計（EPS 7.84），沒有 4.27 | MOCK 腳本改為引用財報快照 `snapshot_id`（如 `snap-2317-2026Q2`）。c1 只有在公告原文真的寫了該 EPS 時才同時引用公告（2330 27.25、2454 15.28 有；2317 沒有，只引用快照）。c2 只引用快照，並加限制「TTM 由財報快照工具以連續四個單季加總；公告原文只有單季或累計數字」 | `research_ui/mock_jobs.py` |
| 同上：快照 ID 要能被讀者核對 | 報告 JSON 的來源清單把 `snap-*` 解析為「財報快照（工具結果）」：可得時間、原始財報檔 ID、sha256，以及工具在資料截止時的數值（單季 EPS、TTM EPS 與期間、單季營收、TTM FCF）。網站來源抽屜與 PDF 來源段都顯示，標示「工具結果，不是公告片段」 | `research_ui/report_data.py`（report-data-v1.1）、`report_pdf.py`、`__init__.py`、`research.js` |
| 問題 2（warn）：基準日收盤價只在圖上 | PDF 估值段新增「基準收盤價：2026-09-30 收盤 X 元（未還原；交易日 17:30 起可得）」；網站估值說明同步顯示 | `report_pdf.py`、`research.js` |

新增測試 4 項（`tests/test_online_pdf.py`）：3 檔每一條事實主張的每個數字，都必須出現在它引用的來源文字中（同 B 的檢查方法）；2317 c1 只能引用 `snap-2317-2026Q2`；PDF 印出基準收盤價。`pytest -q tests` → 281 passed。

**請組長注意**：B 也問到 Reviewer 的確定性規則（`agents/review_checks.py`）沒有攔下這類引用錯誤，原 3 份 MOCK 都是 pass。這是組長的檔案，A 沒有修改。

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
| 2330 | `rv-d407e7cc-cf7c-4c8a-a210-9d3452d75454` | f46a0c5f35c7579e | 585953fcf537426b | reports/2330/rv-d407e7cc-….pdf |
| 2317 | `rv-915bb95c-9fbd-435b-8fdd-5e83188e24d7` | b8be13bc34f0ab35 | ddb9599b22859456 | reports/2317/rv-915bb95c-….pdf |
| 2454 | `rv-d1fafb87-7647-443c-9804-ccf57a32dda1` | 0b614a2ab361568a | a7eee608b596b976 | reports/2454/rv-d1fafb87-….pdf |

10/26 的舊版本（rv-b0062cc2、rv-8e567646、rv-393f3b6f）已被取代，留在 git 歷史；B 的 `data/v12-report-audit.csv` W7A 列指向舊檔，需 B 以新檔重核。

檔案：`reports/v12-online-pdf/`（PDF、核准 JSON、`manifest.json`、每頁縮圖 `pages/`）。

## 3. 版面與內容檢查（`python scripts/w07_pdf_check.py` 輸出）

| 股票 | 頁數 | 大小 | 內嵌字型 | 連結 | 圖 | JSON 關鍵項目在 PDF 內 | PDF hash | 結果 |
|---|---|---|---|---|---|---|---|---|
| 2330 | 3 | 401 KB | NotoSansCJKTC（子集） | 1 | 2 | 19/19 | 相符 | 通過 |
| 2317 | 3 | 238 KB | NotoSansCJKTC（子集） | 1 | 1 | 18/18 | 相符 | 通過 |
| 2454 | 3 | 397 KB | NotoSansCJKTC（子集） | 1 | 2 | 23/23 | 相符 | 通過 |

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
| 「下載 PDF」觸發下載，檔名 `2454-v1-rv-….pdf`，406,022 bytes，檔頭 `%PDF-`，與驗收副本同大小 | ✓ | ✓ |
| `/reports/<rv>.pdf` 預覽：200、`application/pdf`、inline | ✓ | — |
| 頁面錯誤、橫向捲動 | 無 | 無 |
| 不存在的版本下載 → 404 | ✓ | ✓ |

截圖：`design/w07/W07-published-list-{1440,390}.png`、`design/w07/W07-report-2454-{1440,390}.png`、`design/w07/W07-source-snapshot-2317-390.png`（財報快照來源抽屜）。

**限制**：手機測試是桌面 Chromium 的手機模擬，不是實機 iOS Safari／Android Chrome；請組長在部署後用手機實測一次下載。

## 5. 安全與發布規則（測試：`tests/test_online_pdf.py`，14 項）

- 草稿版本不出現在公開清單、詳情、下載（404）；訪客核准 403。
- 組長核准必須帶「看過的 hash」；hash 不符 409，不發布。
- 同一 job 第 2 版發布後，第 1 版 PDF 仍可下載且內容不變（write-once）；歷史版本只列已發布。
- 公開讀取（清單、詳情、下載）0 次 LLM。
- Supabase adapter 不可覆寫；沒有三個環境變數時回到本機資料夾。

## 6. 尚未完成／需要別人

| 項目 | 狀態 | 需要誰 |
|---|---|---|
| Supabase Storage／版本資料庫 | 組長 10/28 已在 W07-L 接上 Supabase 測試專案的 Postgres 與私有 Storage（commit 64be502、7ce57a4，變數改名為 `REPORT_SUPABASE_*`）。A 沒有另外連線重測 | 組長（已處理，A 只記錄） |
| LIVE（真實模型）報告 | 研究入口仍只開 MOCK（組長 10/05 決定）；目前三份都是 MOCK 標示 | 組長決定何時開 LIVE |
| 實機手機 | 只有模擬 | 組長部署後實測 |
| 10/29 新版重核 | 三份 PDF 版本 ID 已換新；`data/v12-report-audit.csv` 的 W7A 列需以新檔重跑 | B |
| Reviewer 確定性規則 | 是否檢查「事實數字須出現在引用來源或工具結果」 | 組長（`agents/review_checks.py`） |
