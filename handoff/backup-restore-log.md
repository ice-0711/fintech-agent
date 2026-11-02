# 備份與還原演練紀錄（W08-L）

2026-11-02，組長（Claude 執行）。對應 Notion W08-L「監督 DB、Storage 及還原」與 `handoff/deployment-v1.md` 第四節第 10 步。

## 一、為什麼要自己備份

- Supabase 是 Free 方案，Backups 頁面明示「Free Plan does not include project backups」，沒有排程備份可還原。
- 研究 job 只存在組長 Mac 的 `tmp/*.sqlite3`（部署架構見 `handoff/deployment-v1.md` 第二節），Render 與 Supabase 都沒有副本。

## 二、方法

`scripts/backup_reports.py`：

| 指令 | 做什麼 |
|---|---|
| `.venv/bin/python scripts/backup_reports.py export` | 從 Supabase 讀出 `report_versions` 全部列與每份已發布 PDF（只讀，不寫 Supabase），PDF 先比對 hash；`tmp/*.sqlite3` 用 SQLite 線上備份 API 複製並做 `integrity_check`、比對各表筆數；寫 `manifest.json` |
| `.venv/bin/python scripts/backup_reports.py restore <資料夾>` | 不碰 Supabase：用匯出檔重建一份本機 `ReportStore`（SQLite＋本機資料夾），逐項核對 |

還原目標用本機 SQLite，是因為 `ReportStore` 對 SQLite 與 Postgres 跑同一套 SQL（`agents/publication.py`），能證明「從匯出檔可以完整重建報告庫」，又不會動到線上資料。

## 三、結果（2026-11-02 17:12，匯出 `tmp/backups/20261102-171214`，2.1 MB）

匯出內容：`report_versions` 1 列（published 1）、PDF 1 份（`reports/2317/rv-6556af9c-….pdf`，265,590 bytes）、job 資料庫 9 個。

| # | 檢查 | 結果 |
|---|---|---|
| 1 | `report_versions.json` sha256 與 manifest 一致 | PASS |
| 2 | 還原筆數相同 | PASS |
| 3 | 每份報告內容 hash（canonical_hash）與紀錄相符 | PASS |
| 4 | 已發布清單相同 | PASS |
| 5 | 已發布 PDF 讀回 hash 相符 | PASS |
| 6 | 9 個 job 資料庫 integrity_check = ok，sha256 與筆數相同（calib_v1 637 列、dev_v14 312 列、forward_batch1 41 列等） | PASS |
| 7 | 反向測試：把備份中的 PDF 多加 1 byte 再還原 | 正確中止（「PDF 與發布紀錄的 hash 不符」），沒有還原出被改過的 PDF |

## 四、限制與後續

- 這次只有 1 份已發布報告；第二、三批發布後要再跑一次 `export`。
- 備份存在組長 Mac 的 `tmp/backups/`（不進 git，內含報告全文但無金鑰）。Mac 硬碟壞掉就一起不見；組長 11/02 決定：每次匯出後另存一份到 iCloud Drive `fintech-agent-backups/`（首份 20261102-171214 已存，掃描無金鑰字串）。
- 沒有演練「還原回 Supabase」：需要時用 `supabase_migrations/20261028_report_versions_store.sql` 建表，再把 `report_versions.json` 逐列寫回、PDF 上傳回同一 storage key。已發布的 PDF 不可覆寫，所以只能還原到空的專案或空的 bucket。
- Render 本身沒有需要備份的資料（研究不在 Render 跑，報告在 Supabase）。
