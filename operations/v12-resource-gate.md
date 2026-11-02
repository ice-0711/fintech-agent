# V1.2 資源閘門（W08-L）

2026-11-02，組長（Claude 實測與整理）。對應 Notion W08-L 驗收清單：核對後台真實規格、研究和 PDF 重工作限一份、有實測或清楚未執行、純讀 0 LLM、圖不增加 worker 重工作。

## 一、後台真實規格（2026-11-02 讀自後台，詳見 `handoff/quota-baseline.json`）

| 資源 | 方案 | 上限 | 目前用量 |
|---|---|---|---|
| Render web service `fintech-agent` | Free | 512 MB RAM；Metrics 頁標示 CPU 上限 0.15；閒置休眠，冷啟動約 50 秒 | 2GB（1c-2g，US$25／月）未開通 |
| Supabase DB | Free | 0.5 GB／專案 | fintech-agent 25.64 MB、fintech-agent-test 25.07 MB（約 5%） |
| Supabase Storage | Free | 1 GB | 約 0.27 MB（1 份 PDF） |
| Supabase Egress | Free | 5 GB／月 | 0.00 GB |
| Supabase 備份 | Free | **無排程備份** | 改用 `scripts/backup_reports.py`（見 `handoff/backup-restore-log.md`） |
| Gemini | 免費層 `gemini-3.5-flash-lite` | RPM 15、RPD 500、J=6 | 只在組長 Mac 使用 |

## 二、重工作限一份

| 重工作 | 在哪裡 | 如何限制 | 證據 |
|---|---|---|---|
| 研究（LLM） | 組長 Mac | Render 不設 `GEMINI_API_KEY`、`RESEARCH_API_TOKEN`；job API 無 token 回 401；每日 J=6、每 job ≤ 8 次發送 | 11/02 實測 401；Render 環境變數清單無 Gemini 相關變數 |
| PDF 發布 | Render | gunicorn `--workers 1`（同步 worker，一次只處理一個請求），發布在請求內同步完成 | 11/02 發布 2317 一份：31 秒，成功，Events 無記憶體不足重啟 |
| 舊網站 PDF（`main.py`） | Render | `ENABLE_PDF_ON_RENDER` 未設，Render 上預設關閉 | `main.py` 第 457 行 |

代價：發布那 31 秒內，網站其他請求要排隊。發布只在組長操作時發生，可接受。

## 三、實測（2026-11-02，從台北對 Render Ohio）

| 項目 | 結果 |
|---|---|
| 發布 1 份 PDF（Render 512 MB） | 31 秒，成功；PDF 265,590 bytes，hash 與紀錄一致 |
| 同一份 PDF 在組長 Mac 產生 | 峰值 RSS 約 442 MB（macOS `time -l`，含 pandas／matplotlib；只作參考，不等於 Render 上的數字） |
| Render 記憶體圖 | **看不到**：Free 方案不提供 application metrics（需付費方案） |
| `/reports` 公開清單 ×5 | 2.45–4.26 秒（第一次 4.26） |
| 公開 PDF 下載 ×3 | 2.20–2.99 秒 |
| `/api/ui/published` | 3.88 秒 |
| `/api/ui/reports/<rv>` | 5.10 秒 |
| `/`、`/research` | 0.32–0.75 秒 |

## 四、純讀 0 LLM

公開閱讀路徑（`/reports`、`/reports/<rv>.pdf`、`/api/ui/published`、`/api/ui/reports/<rv>`）只讀 `report_versions` 與 Storage，程式裡沒有模型呼叫；而且 Render 根本沒有 Gemini 金鑰。結構上保證 0 LLM。

## 五、TTL 與重複抓取：發現一個會隨報告數變慢的問題

公開清單沒有任何快取（程式中沒有 TTL），每次請求都重新查 Supabase。而 `ReportStore.published()` 先查一次清單，再對每份報告各查一次，每次查詢都新開一條 TLS 連線（`_Postgres.rows`）。從 Render（美國 Ohio）連到測試專案（歐洲 eu-west-1），每次約 1 秒以上。

- 現在只有 1 份報告：清單 2.5 秒。
- 9 份前瞻報告全部發布後：估計約 10 次連線，清單可能要 10 秒以上（推估，未實測）。

**已修正（組長 11/02 核准）**：`ReportStore.published_versions()` 改成一次查詢取回全部已發布版本，並快取 60 秒；同一程序發布成功時立即清除。`/reports` 與 `/api/ui/published` 共用。別的程序（例如組長 Mac）發布的報告最多 60 秒後出現。測試 `test_published_list_is_cached_60s_and_cleared_by_own_publish`。不影響凍結的實驗輸入（`agents/publication.py`、`research_ui/` 不在第二段凍結清單）。

## 六、容量 80% 閘門（B 的 CR，11/02 原則核准）

B 在 `data/storage-and-safety-w08.md` 第六節提的門檻：Storage 800 MB、DB 400 MB，剛好是 Free 方案上限的 80%，可以照用。依目前每份 PDF 約 0.27 MB，9 份前瞻報告約 2.4 MB，離門檻很遠；這項防護可以排在第二批之後實作，不影響本週部署。

## 七、F06 2D 關聯圖

10/22 已決定延後到後續版本，W08 不驗收；網站沒有 2D 圖，也就不增加 worker 重工作。紀錄為「未達，依決定延後」。

## 八、未執行與待決

| 項目 | 狀態 |
|---|---|
| Render 上的實際記憶體峰值 | 未能量測（Free 無 metrics）；以「發布成功、無重啟」為證 |
| 讀 4–5 份報告的資源測試 | 未執行：目前只有 1 份已發布，第二批發布後補測 |
| 公開清單 TTL 快取 | 11/02 完成 |
| 2GB 升級 | 待組長決定；目前證據顯示 512 MB 可發布 1 份 |
| 容量 80% 閘門實作 | 原則核准，排第二批之後 |
