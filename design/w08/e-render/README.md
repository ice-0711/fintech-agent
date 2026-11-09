# 給 E 的 W07-E 簡報截圖

- 提供：A｜第一批擷取 2026-11-08 22:20、第二批（LIVE 第 2 版）2026-11-09 17:45（台北）
- Render 畫面：在 A 電腦的瀏覽器開 https://fintech-agent-di0z.onrender.com/research（1440 寬），用頁面擷取（html2canvas，2 倍解析度）存檔；內容就是 Render 當下的頁面，沒有修圖。
- Render PDF：從 Render 下載的原檔，逐頁轉成圖片（110 dpi）。
- 本機畫面：W07 驗收用的 MOCK 報告，在本機網站或 PDF 渲染。
- 首頁 `/` 自 11/09 起直接跳到 `/research`（決策紀錄第 21 節），以下 Render 畫面本來就是 `/research`，不受影響。

## 一、可以放正式簡報

| 檔案 | 畫面 | 來源 | 標籤 | 簡報要標註 |
|---|---|---|---|---|
| `01-render-overview-1440.jpg` | 研究工作台首屏（研究入口、軌跡、覆核、報告詳情區） | Render | — | 「Render 網站；研究入口不對外開放（研究在組長 Mac 執行）」 |
| `03-render-report-2330-live-v2-1440.jpg` | 2330 LIVE 報告詳情第 2 版（rv-db6b0e1b，資料截止 11/06 21:00）：主張與可點開的來源、估值狀態與基準收盤價（11/06 收盤 2,135 元）、資料品質、季度表、DCF 敏感度、歷史版本 | Render | **LIVE** | 寫版本 ID 與資料截止；「通過覆核不等於正確」 |
| `03-render-report-2317-live-v2-1440.jpg` | 2317 LIVE 報告詳情第 2 版（rv-2ed6652e，資料截止 10/30 21:00）：估值「無法判定（TTM FCF ≤ 0）」、10/30 收盤 245.5 元、季度表 | Render | **LIVE** | 同上；c3 是「未知」主張，本來就沒有來源 |
| `05-render-pdf-2330-live-v2-p1~p3.png` | 上面 2330 第 2 版的 PDF 三頁 | Render | **LIVE** | 同上 |
| `05-render-pdf-2317-live-v2-p1~p3.png` | 上面 2317 第 2 版的 PDF 三頁 | Render | **LIVE** | 同上 |
| `04-render-replay-case04-1440.jpg` | REPLAY：組長 10/15 真實執行紀錄重播（Agent 軌跡、覆核退件） | Render | **REPLAY** | 「真實執行紀錄重播，不是現場運算」 |
| `06-local-pdf-2454-mock-p1~p3.png` | 2454 研究 PDF 三頁（含同業比較；Render 目前沒有 LIVE 的 2454） | 本機（W07 驗收版 rv-a520d5cc） | **MOCK** | 「MOCK 測試報告：模型決策為預錄腳本，數字為真實快照工具輸出，不是研究結論」 |
| `design/w07/c-figures/fig7-2-report-2454-*.png`（W07 已交） | 2454 報告詳情與財務表格（季度、DCF、同業） | 本機 | **MOCK** | 同上 |

## 二、待補拍

| 檔案 | 狀態 |
|---|---|
| `02-render-published-list-live-1440.jpg`、`02-render-published-list-full-1440.jpg` | 11/08 擷取，卡片是 LIVE **第 1 版**。A 已改成清單只列每份研究的最新版（PR `codex/A-latest-version-list`），上線後補拍。在那之前若要用，請寫「11/08 畫面，之後已發布第 2 版」 |

11/08 的 LIVE 第 1 版截圖（主張顯示「無來源」、收盤價停在 9/30）已刪除，不要再用。原因與修正見 `ui/v12-risk-state-cases.md` 第 5 節與 `tests/test_forward_report.py`。第 1 版照規則留在網站的歷史版本裡，網頁會標「舊版」並連到第 2 版。

## 三、標籤說明

| 標籤 | 意思 | 能不能當研究結果 |
|---|---|---|
| LIVE | Gemini 真的跑、組長核准發布的版本 | 可以，但要寫版本 ID 與資料截止 |
| REPLAY | 組長保存的真實執行紀錄重播，網站不呼叫模型 | 只能當「系統運作過程」展示 |
| MOCK | 模型決策是預錄腳本，數字來自真實快照工具 | 不能，只能當介面與 PDF 版面展示 |
| FIXTURE | 介面測試範例，不是 Agent 產出 | 不能 |
