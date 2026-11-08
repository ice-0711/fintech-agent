# 給 E 的 W07-E 簡報截圖（2026-11-08）

- 提供：A｜擷取：2026-11-08 22:20 左右（台北）
- Render 畫面：在 A 電腦的瀏覽器開 https://fintech-agent-di0z.onrender.com/research（1440 寬），用頁面擷取（html2canvas，2 倍解析度）存檔；內容就是 Render 當下的頁面，沒有修圖。
- 本機畫面：W07 驗收用的 MOCK 報告，在本機網站或 PDF 渲染。

## 一、可以放正式簡報

| 檔案 | 畫面 | 來源 | 標籤 | 簡報要標註 |
|---|---|---|---|---|
| `01-render-overview-1440.jpg` | 研究工作台首屏（研究入口、軌跡、覆核、報告詳情區） | Render | — | 「Render 網站，研究入口未開放（研究在組長 Mac 執行）」 |
| `02-render-published-list-live-1440.jpg` | 已發布清單：2330、2317 兩份 LIVE | Render | **LIVE** | 只用清單卡片（版本、發布時間、估值狀態、資料品質、PDF 按鈕）；不要放大報告內容，原因見第二節 |
| `02-render-published-list-full-1440.jpg` | 同上，含下方 3 張 FIXTURE 範例卡 | Render | LIVE＋**FIXTURE** | FIXTURE 是介面測試資料，簡報若出現要寫「FIXTURE 範例」 |
| `04-render-replay-case04-1440.jpg` | REPLAY：組長 10/15 真實執行紀錄重播（Agent 軌跡、覆核退件） | Render | **REPLAY** | 「真實執行紀錄重播，不是現場運算」 |
| `06-local-pdf-2454-mock-p1~p3.png` | 研究 PDF 三頁（2454，含季度表、DCF 敏感度、同業比較、來源） | 本機（W07 驗收版 rv-a520d5cc） | **MOCK** | 「MOCK 測試報告：模型決策為預錄腳本，數字為真實快照工具輸出，不是研究結論」 |
| `design/w07/c-figures/fig7-2-report-2454-*.png`（W07 已交） | 報告詳情與財務表格（季度、DCF、同業） | 本機 | **MOCK** | 同上 |

## 二、暫時不要用（檔名開頭 `x-`）

| 檔案 | 問題 |
|---|---|
| `x-03-render-report-2330-live-v1-DO-NOT-USE.jpg` | Render 上的 LIVE 報告詳情：3 條主張都顯示「無來源」，估值用的是 2026-09-30 收盤 2,480 元 |
| `x-05-render-pdf-23xx-live-v1-*-DO-NOT-USE.png` | 同一份 LIVE 報告的 PDF：來源段有「無法解析」 |

原因是 A 的程式錯誤，不是 Agent 或資料錯：前瞻（LIVE）研究用的是前瞻快照（例如 `data/forward/financial-snapshots-2026-11-06.json`），但報告的資料區塊是用 30 案凍結快照算的，所以找不到前瞻來源片段，收盤價也停在 9/30（前瞻快照 11/06 收盤是 2,135 元）。

- 已修正：分支 `codex/A-forward-snapshot-report`（`research_ui/report_data.py` 依 `snap-fwd{n}-{sha}` 找回當時的快照檔）。
- 已發布的版本不能改；修正合併後需組長重新建立並核准第 2 版，A 再補拍 LIVE 報告詳情與 PDF。

## 三、標籤說明

| 標籤 | 意思 | 能不能當研究結果 |
|---|---|---|
| LIVE | Gemini 真的跑、組長核准發布的版本 | 可以，但要寫版本 ID 與資料截止 |
| REPLAY | 組長保存的真實執行紀錄重播，網站不呼叫模型 | 只能當「系統運作過程」展示 |
| MOCK | 模型決策是預錄腳本，數字來自真實快照工具 | 不能，只能當介面與 PDF 版面展示 |
| FIXTURE | 介面測試範例，不是 Agent 產出 | 不能 |
