# A｜W07 交接：線上研究 PDF、預覽／下載／歷史版本

- 分支：`codex/W07-A-online-pdf`｜日期 2026-10-26｜驗收紀錄：`reports/v12-online-pdf-check.md`
- 測試：`pytest -q tests` → 261 passed（新增 `tests/test_online_pdf.py` 10 項）

## 動到組長檔案的地方（請組長審）

| 檔案 | 改了什麼 | 為什麼 |
|---|---|---|
| `agents/publication.py` | `build_report_json` 多兩欄：`run_label`（事件含 mock 即 MOCK）、`data`（A 的 `build_report_data`，失敗時記錄原因、不擋版本）；`render_pdf` 在有 `data` 時交給 A 的 `render_report_pdf`，10 頁／5 MB 檢查保留 | F05 表格要凍結在核准 JSON 裡，網頁與 PDF 才會是同一份內容 |
| `agents/api.py` | `get_reports()` 的 Storage 改由 `storage_from_env()` 決定（有三個 Supabase 變數就用 Supabase，否則同原本本機資料夾） | W07-A 步驟 2 |

`tests/test_publication.py` 6 項原樣通過。`tests/test_review_risk.py` 原本「組長登入也只能拿 409」的 W05 測試改成新流程（沒帶版本與 hash → 409）。

## 新路由（A）

| 路由 | 誰能用 | 說明 |
|---|---|---|
| `POST /api/ui/jobs/<id>/report` | 登入的組長 | 把 MOCK job 凍結成 draft 版本（不公開），回傳版本與 hash |
| `POST /api/ui/jobs/<id>/approve` | 登入的組長 | 帶 `report_version_id` 與看過的 `report_hash` → 核准 → 發布 |
| `GET /api/ui/reports/<rv>/download` | 所有人（只限已發布） | PDF 下載（從 Storage 讀回並驗 hash） |
| `GET /api/ui/published`、`/api/ui/reports/<rv>` | 所有人 | 現在包含真實已發布版本（標 MOCK／LIVE）＋原 FIXTURE；詳情有季度、DCF、同業、歷史版本 |

預覽用組長原有的 `/reports/<rv>.pdf`（inline）。

## 部署要設的環境變數（Render，伺服器端）

`SUPABASE_URL`、`SUPABASE_SERVICE_KEY`、`REPORT_STORAGE_BUCKET`（私有 bucket）。沒設就是本機資料夾，重新部署會遺失 PDF。版本資料庫（SQLite）同樣會遺失，需組長決定存放方式。

## 重現驗收

```
python scripts/w07_acceptance_pdfs.py          # 產 3 份 PDF 到 reports/v12-online-pdf/
python scripts/w07_pdf_check.py                # 版面與內容檢查表
```
