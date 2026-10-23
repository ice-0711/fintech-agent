# Notion 更新內容（2026-10-23）

## 一、計畫變更紀錄（貼到「08 執行規範與參考資料」或新建「變更紀錄」頁）

**2026-10-23 組長核定：固定流程（workflow）模式提前**
- 原排程：W09 前完成（三模式 runner 由 D 於 W09 確認）。
- 變更：提前到 W07 第一天（10/26）由組長實作，因 W06-D「10 開發案 × 3 模式校準」需要三種模式。
- 校準執行：10/26 起每日最多 6 個 job（J=6），10 案 × 3 模式 = 30 筆，約 5 個工作天完成；完成後由組長匯出 `evaluation/d-drafts/dev-runs.jsonl`，D 評分並簽 v1。
- 影響：W06-D 的「簽 v1」順延至三模式校準完成；不影響保留集隔離與 W10–W11 正式實驗時程。

**其他核定（詳見 GitHub `handoff/decisions-2026-10.md`）**
| 日期 | 事項 | 決定 |
|---|---|---|
| 10/21 | WACC／g | 9%／3%（全專案統一） |
| 10/21 | 股數、BVPS 口徑 | 流通在外股數；歸屬母公司權益 ÷ 流通股數 |
| 10/21 | 淨負債缺值 | 不補 0，DCF 顯示「無法判定」 |
| 10/21 | 登入方式 | 單一組長密碼登入（最簡單） |
| 10/22 | F06 2D 關聯圖 | **延後**，轉後續版本；N06 不驗收 |
| 10/22 | 2317 FCF 正常化 | 不做 |
| 10/22 | 股價可得時間 | 全專案統一 17:30 |
| 10/23 | model | 維持 gemini-3.5-flash-lite |
| 10/23 | 凍結 | 案例／資料／評分規則 10/23 凍結；prompt 與 Agent 程式 10/26 live 再驗證後、W09 前鎖定 |

## 二、任務狀態（84 項任務資料庫）

依 GitHub 實際交付物（2026-10-23 檢查）：

| 任務 | 建議狀態 | 交付紀錄（版本／成果連結） |
|---|---|---|
| W01-L～W05-L | 已完成 | GitHub main；`handoff/`、`agents/`、`agent/` |
| W06-L | 已完成（F06 延後、model 定案、兩段凍結） | `handoff/W06-gate-v12.md`、`handoff/state-machine-v1.md` |
| W01-A～W06-A | 待驗收 | `design/`、`ui/`、`research_ui/`（W06 1 個測試待更新範例數字） |
| W01-B～W06-B | 待驗收 | `data/`、`fixtures/`、`evaluation/`、`docs/B-W01-W06-檔案說明.md` |
| W07-B | 待驗收（提前完成） | `research/forward-batch-1-sources.json` 等 |
| W01-D～W05-D | 待驗收（草稿區） | `evaluation/d-drafts/` |
| W06-D | 進行中 | 規約與評分規則已交；dev-runs 已有 18 筆 dual live（組長匯出）；待三模式 30 筆與 B 交叉評分 |
| W01-C～W06-C | 待確認 | GitHub 無檔案，請 C 回報存放位置 |
| W01-E～W06-E | 待確認 | GitHub 無檔案（含 W06 期中簡報），請 E 回報存放位置 |

## 三、W06-L 交付紀錄（貼到 W06-L 任務頁）

版本：main（commit 80f3c15、a7afabb）｜成果：`handoff/W06-gate-v12.md`、`handoff/state-machine-v1.md`、`agent/dev-v14-batch1~3.json`、`evaluation/d-drafts/dev-runs.jsonl`｜測試：251 passed（1 項為 A 的範例待更新）｜live：v1.5 開發集 18 次（dual），系統無錯誤、token 預估未低估、無錯誤數字通過、無越權工具；尚無一案覆核通過，Reviewer 最後回合問題已修，10/26 live 驗證｜決定：F06 延後、model 維持 flash-lite、兩段凍結｜未完成：三模式校準（workflow 模式 10/26 實作）、Supabase 測試專案（組長）｜驗收人：A、D
