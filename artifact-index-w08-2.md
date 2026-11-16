# W08-E｜簡報成果與素材索引（更新版）

**任務：** W08-E｜更新資源成本與操作限制頁；2D 來源面板與限制頁  
**版本：** 2026-11-16 交付整理稿，**待組長驗收**  
**依據：** `docs/handbook_V1.2/個人_E_十四週工作包.html`、`W08-status.md`（11/14 版）、`docs/v12-limitations-midterm.md`、A/B/D 來源文件。E 僅負責文書與排版，不自行核定技術成果。

## 一、三項指定交付與檔案狀態

| 工作表指定路徑 | 內容 | 2026-11-16 狀態 |
|---|---|---|
| `slides/deck-v7.pptx` | W08 完整簡報 | Canva 現有 28 頁；已取得使用者提供的 **PDF 預覽** `deck-v7.pptx.pdf`，**尚未取得／確認真正的 PPTX**，不能標記已交付 |
| `artifact-index-w08.md` | 八件成果、素材來源、狀態與交接 | 本索引更新版已備妥；待使用者上傳覆蓋 GitHub 舊版 |
| `slides/v12-graph-and-limits.pptx` | 資源成本、執行限制、2D 來源及未完成事項 | 4 頁可編輯 PPTX 已備妥；待使用者核對、上傳 |

**可編輯 Canva W08：** https://www.canva.com/d/RVEobbJj7h2ZYMA  
**舊版 PDF：** `deck-W08-E-integrated-v1.pdf` 已於 PR #42 合併到 main（依 `W08-status.md`）；不應誤認為這次新版簡報。  
**頁數差異：** 原工作包 16 主頁＋4 備用頁，現 Canva 28 頁；未取得組長核准更改頁數的證據。原工作表要求修第 10 頁、備用第 19 頁；新版頁次不同，應以交付內容對照，不能聲稱已按原頁位完成。

## 二、W08 工作表操作與驗收逐項對照

| 工作表要求 | 對應資料 | 狀態／待確認 |
|---|---|---|
| 第 10 頁資源成本與限制 | `v12-graph-and-limits.pptx` 第 1–2 頁；完整簡報目前第 10 頁為 CASE-22 | 專頁已整理，**尚未整合至完整簡報指定頁位** |
| 備用第 19 頁、2D 來源面板與限制 | `v12-graph-and-limits.pptx` 第 3–4 頁；完整簡報第 19 頁為離線測試 | 專頁已整理，**尚未整合至完整簡報指定頁位** |
| 八件成果索引與連結 | 本檔第三節 | 已整理，仍待組長核對來源及驗收狀態 |
| 已驗證／待實測／受阻明確區分 | 本檔第三至五節及限制專頁 | 已區分；不把待測寫成已完成 |
| 成本實值與估算分開 | 本檔第四節及限制專頁 | 已區分本機實測、方案限制、條件式規劃 |
| 圖表數字、來源一致 | A/B/D 來源及限制專頁 | 文書層面核對；**D 與組長尚未驗收此版本** |
| 失敗結果不得消失 | 本檔第五節 | 已保留缺口與未完成項 |
| 不虛構 2D 關係或 2GB 已升級 | 本檔第四、五節 | 只列兩筆 B 核對關係；2GB 未開通、F06 延後 |

## 三、八件成果及證據狀態

以下為 `W08-status.md` 與 `docs/v12-limitations-midterm.md` 截至 2026-11-14 的紀錄，**非 E 重新驗證**。

| # | 成果 | 依據與狀態 | 未完成／限制 |
|---|---|---|---|
| 1 | 網站、三檔入口、季度、同業比較、收藏儀表板 | 核心項目已簽核；`W08-status.md` | F06 延後、手機實機未測 |
| 2 | Researcher／Reviewer 閉環 | 已簽核並附限制；`handoff/W06-gate-v12.md` | v2 正式成效待評估 |
| 3 | 來源、動作、版本、預算、停止原因可追溯 | 有紀錄；`evaluation/v12-forward-manifest.csv` | 不代表結論正確 |
| 4 | 三份研究 PDF | 2330、2317 LIVE 已發布 | 2454 沒有 LIVE 已發布報告 |
| 5 | 30 案三模式評估 | 開發集有評分紀錄 | 20 個保留案例 × 3 模式＝60 run，正式評分待完成；9 份前瞻不能替代 |
| 6 | 20–25 頁論文 | 第四章草稿已提交 | 第五、六章及研究問題定案待完成 |
| 7 | 簡報、講稿、展示、錄影 | W08 簡報重整中 | 28 頁與原 20 頁規格差異、講稿與 W13 錄影 |
| 8 | 版本、設定、測試、來源交接包 | 有既有紀錄；`handoff/`、`data-freeze.md` | 完整交接安排 W12–W13 |

## 四、資源成本與操作限制：不同性質不得混寫

| 類別 | 內容 | 性質／來源 |
|---|---|---|
| Render Free | 512 MB RAM、閒置休眠 | 實際方案；`docs/v12-limitations-midterm.md` |
| Render 2 GB | US$25／月，記憶體不足時才考慮 | **條件式規劃，未開通** |
| PDF 記憶體 | 約 468–479 MB | **A 本機量測**，非 Render 峰值；`design/performance-w08.md` |
| Render 峰值 | Free 方案無可用記憶體圖 | **待實測** |
| Supabase Free | DB 0.5 GB、Storage 1 GB、月流量 5 GB | 方案配額，不代表安全機制已實作 |
| 80% 停止線 | DB 400 MB、Storage 800 MB、流量 4 GB | **原則採用，尚未寫入發布流程**；`data/v12-capacity-and-graph-audit.md` |
| 單次研究上限 | 8 次模型發送、10 次工具呼叫、最多 2 輪補查、180 秒主動時間 | 規格限制；非成效指標 |
| 離線故障安全測試 | 417 項通過 | D 的 W08 本機離線 mock；非 Render、真實 DB 或正式評估；`evaluation/fault-and-security-w08.md` |

## 五、2D 關係來源與待實測

**F06 2D 圖已延後；網站及 PDF 沒有正式上線的 2D 圖。** B 已核對的關係僅可作來源資料表：

| ID | 關係 | 核對證據 | 狀態 |
|---|---|---|---|
| REL-01 | 2454 聯發科 → 2330 台積電：晶圓代工供應 | 聯發科 114 年報 p.74；TWSE 2026-05-29 上傳 | B 核對，僅資料表 |
| REL-02 | 2379 瑞昱 → 2330 台積電：晶圓代工供應 | 瑞昱 114 年報 p.94；TWSE 2026-05-27 上傳 | B 核對，僅資料表 |

來源：`data/v12-capacity-and-graph-audit.md`、`ui/v12-graph-check.md`。**3034 → 2330 尚無年報證據，不得新增。**

**仍待測／受阻：** Render 實際記憶體峰值（組長）；真實 Supabase DB 及 20 並行請求（組長、D）；手機實機（A）；容量 80% 停止線（組長）；2454 LIVE 發布（組長）；保留集正式評分（D、B、組長）；F06 2D 上線（已延後）。

## 六、W08 完整簡報素材及來源索引

| 簡報內容 | 原始來源 | 使用限制 |
|---|---|---|
| Render 研究工作台 | `design/w08/e-render/01-render-overview-1440.jpg` | 研究 job 在本機執行 |
| 2330 LIVE 詳情 | `design/w08/e-render/03-render-report-2330-live-v2-1440.jpg` | LIVE 已發布，非正式保留集評分 |
| 2317 LIVE 詳情 | `design/w08/e-render/03-render-report-2317-live-v2-1440.jpg` | LIVE 已發布，DCF 可能無法判定 |
| PDF 展示 | `design/w08/e-render/05-render-pdf-2330-live-v2-p1.png`、`05-render-pdf-2317-live-v2-p1.png` | 已發布 PDF，不代表研究結論正確 |
| REPLAY | `design/w08/e-render/04-render-replay-case04-1440.jpg` | 必須標示重播，非現場運算 |
| 2454 MOCK | `design/w08/e-render/06-local-pdf-2454-mock-p1.png` | 不能稱 LIVE |
| 故障／安全測試 | `evaluation/fault-and-security-w08.md` | 本機離線 mock |
| 2D 來源與容量 | `data/v12-capacity-and-graph-audit.md` | F06 未上線 |
| 成本及研究限制 | `docs/v12-limitations-midterm.md`、`operations/v12-resource-gate.md` | 實測／規格／規劃分開 |

## 七、上傳與驗收提醒

1. 從 Canva **下載真正的 Microsoft PowerPoint (`.pptx`)**，確認不是 `.pptx.pdf`，存成 `slides/deck-v7.pptx`。
2. 上傳四頁獨立限制專頁至 `slides/v12-graph-and-limits.pptx`。
3. 以本檔更新 repo 根目錄 `artifact-index-w08.md`，並確認連結及來源可供組員開啟。
4. 組長需確認 28 頁是否接受、原第 10 頁及備用第 19 頁要求如何對應、研究問題 RQ1–RQ3 最終版本，以及三項產物是否核准。**未取得確認前不得標記驗收通過。**

**交接：** E 文件整理；D 提供核准測試／圖表，A 提供截圖與實測，B 核對來源，組長驗收版本。GitHub PR 合併不等於技術或內容驗收。
