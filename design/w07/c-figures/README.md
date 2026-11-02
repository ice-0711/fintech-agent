# 給 C 的 W07 圖 7-1、7-2（1440 寬，2x 解析度）

- 日期：2026-11-02｜提供：A｜用途：`docs/v12-website-report-section.md`、`report/system-cases-v1.docx` 圖 7-1、7-2
- 畫面版本：main（含 W07-A 引用修正與 peer_snapshot_version）；瀏覽器寬 1440、Asia/Taipei 時區

## 檔案

| 圖 | 檔案 | 內容 |
|---|---|---|
| 7-1（建議） | `fig7-1-published-list-real-1440.png` | 已發布清單，只截到 3 份真實發布版本：2454 `rv-a520d5cc`、2317 `rv-915bb95c`、2330 `rv-d407e7cc` |
| 7-1（完整） | `fig7-1-published-list-full-1440.png` | 同上加下方 3 張 FIXTURE 範例卡（標 FIXTURE） |
| 7-2（建議上半） | `fig7-2-report-2454-top-1440.png` | 2454 報告詳情：版本、cutoff、快照、PDF 預覽／下載、估值狀態（含基準收盤價）、資料品質 |
| 7-2（建議下半） | `fig7-2-report-2454-tables-1440.png` | 同一份報告的季度資料、DCF 假設與敏感度、同業比較（含同業快照版本註明） |
| 7-2（完整） | `fig7-2-report-2454-full-1440.png` | 報告詳情整段（長圖） |

## 圖說建議

- 圖 7-1：研究工作台的已發布研究清單（2026-11-02 擷取）。三份皆為經人工核准後發布的 MOCK 驗收版本：模型決策為預錄腳本、數字為真實快照工具輸出，不是正式研究結論。
- 圖 7-2：2454 聯發科報告詳情（版本 rv-a520d5cc，資料截止 2026-09-30 17:30）。網頁與 PDF 由同一份核准 JSON 產生；同業數字來自同業快照 v1.8-w06，與主快照 fin-snap:v1.6-tw-market 為不同檔案。

## 這些畫面怎麼來的（給論文方法說明用）

- 畫面是本機執行 `web_app.py` 擷取，不是 Render 線上站。報告資料用 `scripts/w07_demo_store.py` 載入 `reports/v12-online-pdf/` 的三份驗收版本：版本 ID、核准 JSON、報告 hash、PDF 與 PDF hash 都和 B 核對過的檔案相同，沒有重新計算。
- 畫面中的「發布時間」是驗收腳本當時的發布時間（2330、2317：10/29 00:02；2454：10/31 13:13）。
- 三份都標 MOCK（model_id = null），論文不能把它們寫成正式研究結果；LIVE 版本產生後會再提供新截圖。
