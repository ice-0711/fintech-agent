# W06-A｜三條研究路徑走查與手機檢查（QA v1）

- 任務 ID：W06-A（10/19–10/23）｜驗收人：組長｜日期 2026-10-21
- 分支：`codex/W05-A-review-risk`（W05、W06 同一分支）
- 環境：本機 `web_app.py`＋`RESEARCH_UI_MOCK=1`；headless Chromium；截圖紀錄 `design/w06/screenshot-run-2026-10-21.json`
- **標籤**：MOCK＝預錄模型決策＋B 的真實工具；FIXTURE＝介面測試報告文字；REPLAY＝組長保存的真實 Gemini 執行紀錄。三者都不是現場 LIVE，也都沒有發布。

## 1. 三條路徑（研究入口 → 報告）

| 路徑 | 怎麼走 | 看到什麼 | 結果 |
|---|---|---|---|
| A. 覆核退件後通過 | 選 2454、情境 revise_then_pass、送出 → 狀態每 2 秒更新 → 覆核面板 | v1 的 c2 把單季 EPS 寫成 TTM（測試案例）→ 第 1 輪 critical 退回 → 補查 `get_financial_snapshot` → v2 改為 60.69 元 → 第 2 輪通過 → 「研究完成・待人工核准」；核准按鈕回 403 | ✓ |
| B. 資料不足停止 | REPLAY `researcher-v12-traces:CASE-13`（2317，真實 Gemini 紀錄）；MOCK insufficient_evidence 亦可 | Researcher 呼叫工具後判定 insufficient，停止原因 `researcher_insufficient`，覆核面板說明為何沒有模型覆核 | ✓ |
| C. 讀已發布研究 | 收藏與已發布研究 → 開啟報告 → 點來源 ID | 主張分事實／推論／未知；估值狀態與資料品質風險；來源抽屜顯示原文、可得時間、sha256 相符 | ✓ |

## 2. 長文、錯誤與中斷恢復

| 情況 | 處理 | 證據 |
|---|---|---|
| 長公司名（2317 FIXTURE 用全名＋英文） | 卡片標題換行，不撐破版面 | `design/w06/W06-dashboard-360-full.png` |
| 長主張、長問題原因 | 文字斷行；手機上問題表改為逐列堆疊 | `S03-review-revise-trace-390x844.png` |
| 輪詢時網路斷線 | 保留最後一次讀到的狀態，顯示「連線中斷，N 秒後重試，第 n 次」，2→4→8…秒退避（上限 30 秒），恢復後顯示「已重新連線」 | `W06-connection-lost-1440x900.png`、`-390x844.png`（模擬斷網） |
| worker 中途中斷（lease 60 秒過期） | 從檢查點接手，事件 `lease_recovered`，畫面說明預算延續不歸零 | `test_worker_interruption_resumes_without_resetting_budget`；`W06-connection-lost-390x844.png` 上方提示 |
| 重新整理頁面 | 網址帶 `?job=`／`?replay=`／`?report=`，重整後回到同一個 job | `W06-after-reload-same-job-1440x900.png`；`test_job_survives_restart` |
| 找不到 job、伺服器回非 JSON、清單讀取失敗 | 紅框錯誤訊息，說明原因 | 既有 W02–W03 測試 |

**本週修掉的 bug**：MOCK job 在 lease 過期後會卡在 running（`pump()` 沒有把過期的 lease 交回 `claim_next`）。已修，並加測試。

## 3. S01–S06 初版截圖（`design/screenshots/S01-S06-v1/`）

| 編號 | 手冊定義 | 1440×900 | 390×844 | 標籤 |
|---|---|---|---|---|
| S01 | 網站研究入口 | S01-entry-1440x900.png | S01-entry-390x844.png | MOCK |
| S02 | 執行狀態／預算 | S02-status-budget-running-1440x900.png | S02-status-budget-running-390x844.png | MOCK（執行中） |
| S03 | 補查軌跡 | S03-review-revise-trace-1440x900.png | S03-review-revise-trace-390x844.png | MOCK（測試案例） |
| S04 | 來源版本與主張 | S04-claims-source-drawer-1440x900.png | S04-claims-source-drawer-390x844.png | FIXTURE 報告＋B 真實快照片段 |
| S05 | 資料不足狀態 | S05-insufficient-replay-1440x900.png | S05-insufficient-replay-390x844.png | **REPLAY**（10/15 真實 Gemini 紀錄） |
| S06 | 手機 PDF 預覽與下載 | S06-report-pdf-pending-1440x900.png | S06-mobile-report-pdf-pending-390x844.png | **PDF 尚未提供（W07）**：目前只能截報告頁與「線上 PDF 尚未提供」狀態，W07 補真正的 PDF 畫面 |

全部 20 張截圖橫向溢出 0 px（截圖紀錄 JSON）。

## 4. 驗收自查

| 驗收項 | 結果 |
|---|---|
| 390×844 與 1440×900 無重疊 | ✓（逐張目視＋溢出 0 px） |
| 過期／回放明確 | ✓ REPLAY 有獨立提示框、紀錄日期、commit；快照過期有「快照過期」標籤（目前資料都未過期，規則見 `ui/v12-risk-state-cases.md`） |
| 重新載入不丟 job | ✓ |

## 5. 未完成／需要誰

- S06 真正的 PDF 預覽 → W07（組長 Storage＋A 預覽）。
- 真實 LIVE job 畫面 → 需要組長決定授權方式並讓研究工作台呼叫正式 API。
- CR-A04／A05（見 `design/review-states.md`）。
