# W07-L 報告版本與發布：狀態測試（v1.2）

2026-10-28，組長。對應手冊 W07-L 驗收與 F05 狀態：draft → 人工核准 → PDF 寫入版本化 Storage key 並核對 hash → published；產檔失敗則 pdf_failed，可重試。

## 一、存放位置（組長 2026-10-28 決定）

| 內容 | 位置 | 說明 |
|---|---|---|
| 報告版本紀錄 | Supabase Postgres `public.report_versions` | migration `supabase_migrations/20261028_report_versions_store.sql`（rollback 同名 `_rollback`）。欄位與本機 SQLite 相同，`ReportStore` 執行同一套 SQL。RLS 開啟、無 policy，公開 API 角色讀不到 |
| PDF | Supabase Storage 私有 bucket `reports` | key 為 `reports/<ticker>/<report_version_id>.pdf`，寫入後讀回比對 hash |
| 本機與測試 | SQLite＋本機資料夾 | 沒設 `REPORT_DB_URL`／`REPORT_SUPABASE_*` 時使用，離線測試不連 Supabase |

目前接的是 **Supabase 測試專案** `fintech-agent-test`，正式專案不動。連線一律走 session pooler，TLS 以 `certs/supabase-prod-ca-2021.crt` 驗證。

## 二、Render 環境變數（伺服器端，值不進 repo）

| 變數 | 內容 |
|---|---|
| `REPORT_DB_URL` | 測試專案 session pooler 連線字串（`postgresql://postgres.<ref>:<密碼>@aws-0-eu-west-1.pooler.supabase.com:5432/postgres`） |
| `REPORT_SUPABASE_URL` | `https://dclxwuhfllkeshaqwjih.supabase.co` |
| `REPORT_SUPABASE_SERVICE_KEY` | 測試專案的 secret key（`sb_secret_…`） |
| `REPORT_STORAGE_BUCKET` | `reports` |

用 `REPORT_` 開頭，是因為 Render 上的 `SUPABASE_URL` 是舊網站使用的正式專案。`research_ui/storage_supabase.py` 會先讀 `REPORT_SUPABASE_*`，沒有才讀 A 原本的 `SUPABASE_URL`／`SUPABASE_SERVICE_KEY`。

## 三、測試結果

### 離線（`pytest -q tests`，SQLite＋本機資料夾）

269 passed。`tests/test_publication.py` 涵蓋：未核准不可發布／下載、hash 不符拒絕核准、舊版不可核准、內容被竄改拒絕發布、產檔失敗 → pdf_failed → 重試成功、已發布不可覆寫、核准需組長登入（token 不行）。

### Supabase 測試專案實跑（`scripts/rehearse_publication.py`，MOCK job，不呼叫模型）

| # | 檢查 | 結果 |
|---|---|---|
| 1 | 建立版本：status=draft，存進 Supabase Postgres | PASS |
| 2 | 同內容再建立 → 回傳同一版本（不重複） | PASS |
| 3 | 未核准不在公開清單 | PASS |
| 4 | hash 不符拒絕核准 | PASS |
| 5 | 未核准拒絕發布 | PASS |
| 6 | 核准（帶正確 hash）→ approved | PASS |
| 7 | 發布：PDF 上傳私有 bucket、hash 讀回一致 → published | PASS |
| 8 | 已發布出現在公開清單 | PASS |
| 9 | 模擬重新部署（全新 ReportStore，記憶體與本機磁碟都不用）後仍可下載，PDF hash 與紀錄一致 | PASS |
| 10 | 已發布版本不可重新發布／覆寫 | PASS |

10/10 通過。PDF 107,483 bytes（< 5 MB）。演練結束後已刪除演練用的版本列與 PDF，測試專案不留假資料。

### Render 線上（2026-10-28 20:51，commit 4208ee6）

設好四個 `REPORT_*` 變數後重新部署：`/`、`/reports`、`/api/ui/published`、`/admin/login` 都回 200。`/reports` 會實際查詢 Supabase 測試資料庫，可證明 Render 連得上。第一次部署 `/reports` 回 500，原因是 Render 裝到不相容的 `scramp`（`pg8000` 的相依套件），已在 `requirements.txt` 固定為 `scramp==1.4.17` 後修好。

## 四、尚未完成

- **Render 上的組長登入**：還沒設 `ADMIN_PASSWORD`、`FLASK_SECRET_KEY`，線上核准要等 W08 設定。
- **Render 部署驗收（W08）**：Render 目前依 `requirements.txt` 建置（已加入 `pg8000`）；Agent 執行所需套件在 `requirements-agent.txt`，W08 部署時再一起切換。手機實測下載也排在部署後。
- **job 紀錄仍在 SQLite**：Render 重新部署會遺失 job（報告版本與 PDF 不受影響）。Supabase job store 排在後續處理。
- **正式專案**：W08 部署驗收通過後，才決定是否把 migration 套用到正式專案。
