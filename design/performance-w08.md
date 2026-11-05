# W08-A｜效能與公開唯讀使用測試

- 任務 ID：W08-A｜日期 2026-11-05｜負責：A（陳柏臣）｜驗收人：組長（**尚未驗收**）
- 分支：`codex/W08-A-load-cache`（從 main `7d5256f` 開出）
- 原始值：`performance/v12-read-only.json`（摘要＋每秒 RSS）、`performance/v12-read-only-requests.csv`（9,469 筆請求：訪客 9,293、job 170、組長 6）、`performance/v12-click-check.json`、`performance/w08-round-trips.json`、`performance/w08-pdf-memory.jsonl`、修正前的對照 `performance/w08-run1-one-publish-before-memory-fix.*`

## 0. 五點重述

| 項目 | 內容 |
|---|---|
| 目標 | 10 位唯讀訪客＋1 個 job 連續 5 分鐘，量 p95、RSS、5xx；確認切三檔、連點不會重抓財報或呼叫模型；修非同步狀態與 PDF 下載問題；F06 依決定關閉 |
| 既有狀態 | W07 線上 PDF 已在 Render Free（512 MB、1 個 gunicorn sync worker）上線；組長 11/02 加了 60 秒已發布清單快取；F06 10/22 決定延後 |
| 輸入 | `web_app.py`、`render.yaml`、`agents/publication.py`、`research_ui/`、`handoff/deployment-v1.md`、`operations/v12-resource-gate.md`、`handoff/decisions-2026-10.md` 第 11–12 節 |
| 交付 | 本文件、UI 修正、`ui/v12-graph-check.md`、`performance/v12-read-only.json` |
| 驗收人 | 組長 |

## 1. 測試環境（照實寫，不是 Render）

| 項目 | 設定 |
|---|---|
| 伺服器 | 本機雲端容器（2 核、8 GB），`gunicorn … --workers 1 --timeout 120`，與 `render.yaml` 相同的 1 個 sync worker |
| 程式入口 | `scripts/w08_counted_wsgi.py`：就是 `web_app:app`，只多包了計數器（模型請求、舊首頁全份財報抓取、對外連線、報告庫查詢、Storage 讀取），被包的函式照常執行 |
| 報告資料 | `scripts/w07_demo_store.py` 原樣載入 B 核過的 3 份驗收版本（本機 SQLite＋本機 Storage）；**不是** Supabase |
| 訪客 | `scripts/w08_load_test.py`：10 個執行緒，照網頁行為開 `/research`（HTML、CSS、JS＋3 個啟動讀取）、開報告、來源抽屜、公開清單、PDF 預覽與下載；動作間隔 0.5–2 秒；20% 的動作是「連點」：三份報告各連開 4–5 次 |
| 1 個 job | MOCK `revise_then_pass`（模型決策為預錄腳本、工具為真實快照），每 2 秒輪詢一次，跑完就開下一個；5 分鐘共 19 個，全部 succeeded |
| 組長發布 | 第 100 秒、第 200 秒各登入一次、核准並發布一份（PDF 在請求內產生，同 Render） |

**限制**：本機到資料庫是本機檔案，Render 到 Supabase（歐洲）每次查詢約 1 秒。所以本機的毫秒數**不能**當成 Render 的等待時間；Render 上的等待主要取決於「每次閱讀要連幾次 Supabase」，這點另外量（第 3 節）。Render Free 也看不到記憶體圖，所以 RSS 是本機同一份程式的數字。

## 2. 5 分鐘結果（最終版，`performance/v12-read-only.json`）

### 2.1 延遲與錯誤（訪客請求）

| 範圍 | 筆數 | p50 | p95 | 最大 | 5xx | 連線錯誤 |
|---|---|---|---|---|---|---|
| 全部訪客請求（約 31 次／秒） | 9,293 | 3.2 ms | **14.8 ms** | 2,437 ms | **0** | 0 |
| 發布 PDF 以外的時間 | 9,268 | — | 14.5 ms | — | 0 | 0 |
| 發布 PDF 的 2 段期間（各約 2.4 秒） | 25 | — | **2,428 ms** | 2,437 ms | 0 | 0 |

| 端點 | 筆數 | p50 | p95 | p99 | 最大 | 4xx | 5xx |
|---|---|---|---|---|---|---|---|
| `GET /research` | 443 | 2.5 | 7.0 | 22.5 | 50.0 | 0 | 0 |
| `GET /api/ui/published` | 443 | 12.9 | 18.7 | 83.6 | 108.3 | 0 | 0 |
| `GET /api/ui/comparison/2454` | 443 | 15.7 | 22.8 | 88.4 | 106.7 | 0 | 0 |
| `GET /api/ui/reports/<rv>` | 5,566 | 3.1 | 6.2 | 14.9 | 2,437.1 | 0 | 0 |
| `GET /api/ui/evidence/<id>` | 293 | 3.7 | 7.4 | 106.6 | 2,106.3 | 0 | 0 |
| `GET /api/ui/reports/<rv>.pdf`（預覽） | 279 | 3.4 | 6.0 | 368.0 | 2,322.5 | 0 | 0 |
| `GET /api/ui/reports/<rv>/download` | 269 | 3.4 | 7.4 | 26.4 | 1,077.3 | 0 | 0 |
| `GET /reports`（公開清單） | 228 | 2.7 | 4.4 | 16.6 | 2,099.5 | 0 | 0 |
| `GET /api/ui/jobs/<id>`（job 輪詢） | 151 | 13.5 | 23.3 | 555.1 | 1,697.1 | 0 | 0 |
| `POST …/approve`（產生並發布 PDF） | 2 | 2,383.8 | — | — | 2,446.8 | 0 | 0 |

（單位 ms。各端點最大值都落在發布 PDF 的那 2 秒：1 個 sync worker 在產 PDF 時，其他請求排隊。Render 上發布一份約 31 秒，那段時間網頁會等，所以第 5 節加了「伺服器回應較慢」提示與自動重試。）

### 2.2 RSS（gunicorn master＋worker，每秒取樣，共 307 筆）

| 時點 | worker | 合計 |
|---|---|---|
| 啟動後閒置 | 231 MB | 254 MB |
| 10 位訪客＋job，第 0–100 秒 | 233 MB | 256 MB |
| 第 1 次發布 PDF 的峰值（第 102 秒） | 453 MB | 476 MB |
| 第 1 次發布後 | **286 MB** | 309 MB |
| 第 2 次發布 PDF 的峰值（第 201 秒） | **479 MB** | **502 MB** |
| 第 2 次發布後到結束 | **293 MB** | 316 MB |

### 2.3 模型請求、重抓財報、對外連線（伺服器計數器，前後相減）

| 計數 | 5 分鐘負載 | 瀏覽器連點檢查 |
|---|---|---|
| Gemini 模型請求（`generate_content`） | **0** | **0** |
| 建立 Gemini client／Adapter | 0 | 0 |
| 舊首頁的全份財報抓取（`download_financial_report`） | **0** | **0** |
| 對外網路連線（FinMind、Supabase、Gemini…） | **0** | **0** |

## 3. 找到的問題與修正

### 3.1 發布 PDF 後記憶體不還，第 2 份就會超過 Render 的 512 MB（已修）

| 情況 | 第 1 份 | 第 2 份 | 第 3 份 | 第 4 份 |
|---|---|---|---|---|
| 修正前：產完後的 RSS（`w08_pdf_memory.py --no-release`） | 467 MB | **513 MB** | 621 MB | 660 MB |
| 修正後：產完後的 RSS | 261 MB | 268 MB | 270 MB | 274 MB |
| 修正後：每份的峰值 | 468 MB | 473 MB | 473 MB | 473 MB |

5 分鐘負載的修正前對照（`w08-run1-…`）：發布 1 份後 worker 從 233 MB 升到 453 MB 並一直停在那裡；修正後回到 286 MB。

- 原因：fpdf2 解析 16 MB 的中文字型兩次（一般、粗體）加上 300 dpi 圖表，產完後 Python 釋放的記憶體留在行程裡，沒有還給作業系統。
- 修正：`research_ui/report_pdf.py` 產完 PDF 後 `gc.collect()`＋glibc `malloc_trim(0)`（`release_memory()`，失敗時也會執行）。PDF 內容不變。
- 剩下的風險：**每份 PDF 的峰值仍約 470–480 MB**，離 512 MB 很近。要再降需要動到共用的 `valuation_agent/chart_builder.py`（圖表固定 300 dpi）或字型處理，屬組長決定（CR-W08-A2）。

### 3.2 每次開報告、下載 PDF 都重連資料庫（已修）

Render 上每次查詢 Supabase 是一條新的 TLS 連線（約 1 秒，組長 11/02 實測）。逐端點計算查詢次數（`performance/w08-round-trips.json`）：

| 端點 | 修正前：查詢／Storage（每次） | 修正後：第一次 | 修正後：60 秒內再開 |
|---|---|---|---|
| 開報告 `/api/ui/reports/<rv>` | 1／0 | 0／0 | 0／0 |
| 來源抽屜 `/api/ui/evidence/<id>` | 1／0 | 0／0 | 0／0 |
| 下載 `/api/ui/reports/<rv>/download` | **3／1** | 0／1 | 0／0 |
| 網頁的預覽連結（改用 `/api/ui/reports/<rv>.pdf`） | 1／1（原 `/reports/<rv>.pdf`） | 0／0 | 0／0 |

5 分鐘負載合計：修正前 294 次查詢、284 次 Storage 讀取；修正後 22 次、5 次。

- 已發布版本不可覆寫，所以開報告、來源、PDF 都先查組長的 60 秒已發布清單快取，找不到才查資料庫。
- PDF 也是不可變、且有 hash：每次從 Storage 讀回都比對 hash，最多保留 8 份、24 MB 在記憶體；另加 `ETag`，瀏覽器重複點同一份會拿到 304。
- 代價：組長在別台電腦發布或刪除版本，網站最多 60 秒後才反映（與組長的清單快取相同）。
- 組長的 `/reports/<rv>.pdf` 沒有改（仍 1 次查詢＋1 次 Storage）；網頁按鈕改連 A 的新路由，內容相同。

### 3.3 伺服器忙或剛喚醒時，網頁看起來當掉（已修）

Render Free 閒置後冷啟動約 50 秒、發布 PDF 約 31 秒，這段時間請求會一直等。原本網頁沒有逾時也沒有提示。

- 每個讀取 25 秒逾時；超過 5 秒右上角顯示「伺服器回應較慢（剛喚醒或正在產生 PDF），請稍候…」（`design/w08/W08-slow-server-1440.png`）。
- 已發布清單、同業比較讀取失敗（無回應或 5xx）時自動重試（5、10、20、40 秒），並有「立即重試」按鈕（`design/w08/W08-retry-after-503-1440.png`）；報告開啟失敗也有「重試」。
- 組長的核准發布按鈕給 180 秒，不會因產 PDF 太久被誤判失敗。
- 實測：瀏覽器擋住 `/api/ui/published` 6.5 秒時出現提示，放行後恢復「系統待命」；比較面板先回 503 時顯示錯誤與重試，按「立即重試」後正常顯示。

### 3.4 同業財報期不同的註明（組長 11/02 請 A 核對網站）

組長改了同業平均規則（不同財報期的同業也計入，`peer_stats.period_note`）。網頁的比較面板與報告詳情現在都會在 `period_note` 有值時顯示「同業財報期不同，各列財報期見上表」。目前主快照三家同業都是 2026Q2，所以畫面上不會出現；前瞻快照（3034 有 Q3）時才會出現。

## 4. 切三檔與連點（`performance/v12-click-check.json`，Chromium 1440×900 與 390×844）

| 檢查 | 1440 | 390 |
|---|---|---|
| 開啟 `/research` 的請求 | 6 個 GET（頁面、CSS、JS、已發布清單、比較、回放清單） | 同左 |
| 研究標的 2330／2317／2454 連切 5 輪（15 次點擊） | **0 個請求** | **0 個請求** |
| 三份已發布報告各連開 5 次（15 次點擊） | 15 個 `GET /api/ui/reports/<rv>`，沒有 POST、沒有 `/api/analyze` | 同左 |
| 下載 PDF 2 次 | 兩次都成功，411,006 bytes，檔頭 `%PDF-` | 同左 |
| 「下載 PDF」按鈕、來源抽屜被其他元素蓋住 | 沒有 | 沒有 |
| 頁面 JS 錯誤 | 0 | 0 |
| 伺服器模型請求／全份財報抓取／對外連線 | 0／0／0 | 0／0／0 |

研究工作台的閱讀不會重抓財報，也不呼叫模型：網頁只讀已核准的報告 JSON、B 的快照檔與 PDF。

**舊首頁 `/` 不在此列**：首頁按「分析」會 `POST /api/analyze`，每次都重新向 FinMind 抓 5 年財報並寫回 Supabase，沒有快取也沒有授權（切換輸入框不會觸發，只有按下送出才會）。這是既有功能，手冊說「既有同步入口須納入相同授權／配額政策，保留相容性由組長和 A 確認，不默默刪除」，所以本週**沒有改**，列為 CR-W08-A1 請組長決定。本機環境連不到 FinMind，也沒有實測它。

## 5. 驗收項逐項

| 驗收項 | 結果 |
|---|---|
| 有 p95／RSS／5xx 原始值 | ✅ 每筆請求在 `performance/v12-read-only-requests.csv`，每秒 RSS 在 `v12-read-only.json` 的 `rss_mb.series`；p95 14.8 ms、5xx 0、RSS 峰值 502 MB（合計）／479 MB（worker） |
| 不能只說順暢 | ✅ 第 2–4 節都是實測數字；同時寫明本機與 Render 的差異 |
| 讀頁／PDF 模型請求增量為 0 | ✅ 負載與連點檢查都是 0（伺服器計數器） |
| 11/06 關閉未完成圖範圍；0 LLM；PDF／來源不被圖遮住 | ✅ 見 `ui/v12-graph-check.md` |

## 6. CR 建議（未自行實作）

| 編號 | 內容 | 給誰 |
|---|---|---|
| CR-W08-A1 | 舊首頁 `/api/analyze` 每次重抓 FinMind 全份財報、無授權：建議加組長登入或每檔每日快取 | 組長 |
| CR-W08-A2 | 每份 PDF 峰值約 470–480 MB，接近 512 MB：可改 PDF 圖表為 150 dpi（約可省 130 MB，需動 `chart_builder.py`），或維持 11/02 決定「出現 pdf_failed 再升級 2 GB」 | 組長 |
| CR-W08-A3 | 網站沒有核准 LIVE 報告的按鈕（`handoff/deployment-v1.md` 第六節），目前用 API 呼叫：可在研究工作台加「組長：待核准版本」清單，沿用 W07 的兩步核准 | 組長 |

## 7. 重現指令

```
python scripts/w07_demo_store.py DIR
RESEARCH_UI_MOCK=1 RESEARCH_UI_MOCK_DB=DIR/ui.sqlite3 REPORT_DB_PATH=DIR/reports.sqlite3 REPORT_STORAGE_DIR=DIR/storage \
  ADMIN_PASSWORD=… FLASK_SECRET_KEY=… W08_COUNTS=DIR/counts.json \
  gunicorn scripts.w08_counted_wsgi:app --workers 1 --timeout 120 -b 127.0.0.1:5094 --pid DIR/g.pid
W08_ADMIN_PASSWORD=… python scripts/w08_load_test.py --base http://127.0.0.1:5094 --server-pid $(cat DIR/g.pid) \
  --counts DIR/counts.json --out performance/v12-read-only.json --raw performance/v12-read-only-requests.csv \
  --duration 300 --readers 10 --publish-at 100 200
python scripts/w08_click_check.py --base … --counts … --out performance/v12-click-check.json --shots design/w08
python scripts/w08_round_trips.py --base … --counts … --rv RV --ref EV
python scripts/w08_pdf_memory.py --renders 4 [--no-release]
python -m pytest -q tests        # 395 passed
```
