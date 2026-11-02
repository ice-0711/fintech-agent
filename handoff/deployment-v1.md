# 部署紀錄 v1（W08-L）

2026-11-02，組長。對應 Notion W08-L「部署驗收與資源防護」。本檔是部署計畫與檢查表，**尚未部署**；各項結果在執行後填入，未做的寫「未執行」。

## 一、目前線上狀態（2026-11-02 實測，未登入、只讀）

| 項目 | 結果 |
|---|---|
| 網址 | https://fintech-agent-di0z.onrender.com （服務名 `fintech-agent`） |
| 方案 | `render.yaml` 寫 `plan: free`（512MB RAM）；2GB **未開通、未付費** |
| 啟動 | `gunicorn web_app:app --workers 1 --timeout 120`，Build 只裝 `requirements.txt` |
| `/` | 200 |
| `/reports`（公開已發布清單） | 200，`{"ok": true, "reports": []}`，目前沒有任何已發布報告 |
| `/admin/login` | 200，頁面顯示「伺服器尚未設定 ADMIN_PASSWORD，無法登入」 |
| `POST /api/research/jobs`（無 token） | 401，拒絕 |
| 線上跑的 commit | 未確認（需看 Render 後台 Events）；W07 的 `/reports`、`/admin` 已在線上，至少是 10/28 之後的版本 |

## 二、部署架構（待組長核准）

依現有程式，建議分成兩邊，不在 Render 上跑研究：

| 工作 | 在哪裡 | 理由 |
|---|---|---|
| 研究 job（Gemini、Researcher/Reviewer） | 組長 Mac，`tmp/` 下的 SQLite | Render 沒有 worker，也沒裝 `google-genai`、`langgraph`（`requirements-agent.txt`）；Render 重啟會清掉本機 SQLite，job 不能放那裡 |
| 建立報告版本 | 組長 Mac，寫入 Supabase `report_versions` | `create_version` 要讀 job，job 在 Mac；版本存 Supabase 後，Render 讀得到同一筆 |
| 組長登入、核准、發布 PDF | Render | 核准與發布只讀寫 `report_versions` 和 Storage，不碰 job、不呼叫模型 |
| 公開閱讀已發布報告與 PDF | Render | 只讀，0 次 LLM 呼叫 |

這樣 `research_jobs` 不必搬到 Supabase（W02 的遷移缺口不影響部署），代價是研究只能在組長 Mac 上跑。Render 上**不設** `GEMINI_API_KEY`、`RESEARCH_API_TOKEN`，job API 一律拒絕（已實測 401）。

我已確認：拿掉 `google-genai`、`langgraph`、`pytest` 後 `web_app` 仍可匯入（30 條路由），所以 Render 不必改 Build。

## 三、Render 環境變數

值只在 Render 後台與組長 Mac 的 `.env` 填寫，不進 repo、不貼聊天。

| 變數 | 用途 | Render | 誰設 |
|---|---|---|---|
| `ADMIN_PASSWORD` | 組長登入（核准與發布需登入） | **必填，目前未設** | 組長 |
| `FLASK_SECRET_KEY` | 登入 session 簽章；不設則每次重啟隨機產生，登入會失效 | **必填** | 組長（隨機長字串） |
| `REPORT_DB_URL` | 報告版本 `report_versions`（Supabase Postgres，session pooler） | 必填 | 組長 |
| `REPORT_SUPABASE_URL`、`REPORT_SUPABASE_SERVICE_KEY` | 報告 PDF 私有 Storage | 必填 | 組長 |
| `REPORT_STORAGE_BUCKET` | `reports` | 必填 | 組長 |
| `SUPABASE_URL`、`SUPABASE_KEY` | 舊網站功能（正式專案） | 已設，不動 | — |
| `ENABLE_PDF_ON_RENDER` | 只管**舊網站** `main.py` 的 PDF；V1.2 發布 PDF 不受它控制 | 512MB：不設；2GB：可設 `1` | 組長 |
| `FINMIND_TOKEN` | 舊網站查詢；非必填 | 視需要 | 組長 |
| `GEMINI_API_KEY`、`GEMINI_MODEL`、`RESEARCH_API_TOKEN` | 研究 job | **不設**（研究只在 Mac 跑） | — |
| `RENDER` | Render 自動提供，用來開啟 secure cookie | 自動 | — |

**組長 Mac 的 `.env` 也要補**：`REPORT_DB_URL`、`REPORT_SUPABASE_URL`、`REPORT_SUPABASE_SERVICE_KEY`、`REPORT_STORAGE_BUCKET`，值與 Render 相同。2026-11-02 檢查（只看有無）：Mac 上這四個都還沒有，只有演練用的 `SUPABASE_TEST_*`；沒補的話，Mac 建立的報告版本會寫進本機 SQLite，Render 讀不到。

**待組長決定**：報告目前接 Supabase **測試專案**（10/28 決定，正式專案不動）。正式展示要沿用測試專案，還是在正式專案建 `report_versions` 與 `reports` bucket（需跑 `supabase_migrations/20261028_report_versions_store.sql`）。

## 四、部署步驟與驗收（W08-L 驗收清單）

| # | 步驟 | 驗收 | 結果 |
|---|---|---|---|
| 1 | 組長確認 Render 方案（2GB 規格、月費）並核准 | 後台截圖：方案、RAM、月費 | 11/02 查得：Free 512MB；2GB（1c-2g）US$25／月。建議先在 Free 實測發布 PDF 的記憶體，爆了再升級（待組長決定） |
| 2 | 組長確認 Supabase 方案與用量（DB、Storage） | 後台讀數填入 `handoff/quota-baseline.json` | 11/02 完成：Free，DB 各約 25 MB／0.5 GB，Storage 0／1 GB；**Free 不含排程備份** |
| 3 | Render 設定第三節的必填變數 | `/admin/login` 不再顯示「尚未設定」 | 11/02 完成：`REPORT_*` 4 個 10/28 已設，組長新增 `ADMIN_PASSWORD`、`FLASK_SECRET_KEY`；重新部署後登入頁正常 |
| 4 | 部署 `main` 最新 commit | Render Events 的 commit 與 `git rev-parse --short HEAD` 一致 | 11/02 後台顯示 Live `46e383c`（Auto-Deploy On Commit） |
| 5 | 冒煙測試：`/`、`/reports`、登入、登出 | 全部 200；登入後 cookie 有 Secure | 未執行 |
| 6 | 端到端：Mac 跑一份研究 → 建版本 → Render 核准 → 發布 → 公開下載 PDF | PDF hash 與版本紀錄一致；未核准的不出現在 `/reports` | 未執行 |
| 7 | 重工作限一份：發布 PDF 時不同時跑其他 PDF | gunicorn 1 worker；記錄發布期間 RSS 峰值 | 未執行 |
| 8 | 量 RSS（閒置、讀 4–5 份報告、發布 PDF） | 數字記入 `operations/v12-resource-gate.md` | 未執行 |
| 9 | 純讀 0 LLM | 讀報告期間 Gemini 用量不變（Render 根本沒有 key） | 未執行 |
| 10 | 備份與還原：`report_versions` 匯出 → 測試專案還原 → hash 比對 | 記入 `handoff/backup-restore-log.md` | 未執行 |
| 11 | F06 2D 關聯圖 | 10/22 已決定延後；記「未達，轉後續版本」，圖不增加 worker 重工作 | 未達（依決定） |

## 五、回滾

- **Render**：後台 Events 選上一個成功的 deploy →「Rollback」。部署前先記下目前線上 commit（第四節第 4 步）。
- **資料庫**：`report_versions` 有 rollback SQL（`supabase_migrations/20261028_report_versions_store_rollback.sql`），只在測試專案演練過；已發布版本不可覆寫，回滾程式不會改動已發布的 PDF。
- **研究 job**：在 Mac 的 `tmp/*.sqlite3`，部署與回滾都不影響；需另外備份這些檔案。

## 六、已知限制與未達項

- 2GB 尚未核准：若維持 512MB，PDF 發布需實測 RSS，超過就只在 Mac 產 PDF、Render 只提供下載。
- 研究只能在組長 Mac 跑；Mac 關機時不能新建研究，但網站閱讀與下載不受影響。
- 報告存放的 Supabase 專案（測試或正式）待決定。
- 部署後的線上 commit、RSS、備份還原都尚未實測。
