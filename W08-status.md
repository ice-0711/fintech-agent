# W08 中期狀態（W08-status）

- 任務 ID：W08-C｜整理人：C｜版本：第 2 版（2026-11-14；第 1 版 11/11 經 PR #39 合併）
- 範圍：W08（2026-11-02–11-06）各人交付在 main 的情況、八件成果的證據狀態、核心凍結與未完成項。內容截至 2026-11-14 main（commit 36758df）。
- 判定方式：只依 main 上的檔案與各檔自己標示的驗收狀態，不用完成百分比。正式文字與限制段落見 `docs/v12-limitations-midterm.md`（論文用）與 `report/limitations-v1.docx`。
- W08-C 本身逾期：原期限 11/06，實際 11/11 交件。

## 一、W08 各人交付（手冊 `16_六人84項任務.csv`）

| 任務 | 必交產物 | 在 main | 檔案自己標示的驗收狀態 | 備註 |
|---|---|---|---|---|
| W08-L 組長 | `handoff/deployment-v1.md`、`handoff/backup-restore-log.md`、`research/forward-batch-2.json`、`operations/v12-resource-gate.md` | ✅ | 驗收人：A 與 D 技術交叉檢查、組長定案 | 部署第 1–7、10 步完成；第 8 步部分（Free 看不到記憶體圖）；第 9 步未執行；第 11 步 F06 依決定延後（`deployment-v1.md` 第四節） |
| W08-A | `design/performance-w08.md`、UI 修正、`ui/v12-graph-check.md`、`performance/v12-read-only.json` | ✅ | 「驗收人：組長（尚未驗收）」 | 本機容器測試，不是 Render；提出 CR-W08-A1～A3 |
| W08-B | `data/storage-and-safety-w08.md`、`research/forward-batch-2-sources.json`、`data/v12-capacity-and-graph-audit.md` | ✅ | B 自查：80% 停止線 🟡（原則採用、程式未實作），其餘 ✅（`docs/B-W01-W09-acceptance.md`） | 驗收人：D、組長 |
| W08-C | `report/limitations-v1.docx`、`W08-status.md`、`docs/v12-limitations-midterm.md` | ✅（PR #39，11/13 合併） | B 11/14 核對技術事實，5 處已依意見修正（第 2 版） | 驗收人：B（技術事實）、組長（文字） |
| W08-D | `evaluation/fault-and-security-w08.md`、`evaluation/v12-load-graph-check.md` | ✅（PR #27，11/07 補交） | 檔頭「尚未驗收」；B 11/07 核對通過（`docs/B-review-W08-D.md`）；組長 11/08 合併時補註 | 全部為離線 mock；真實 DB 暫失未執行 |
| W08-E | `slides/deck-v7.pptx`、`artifact-index-w08.md`、`slides/v12-graph-and-limits.pptx` | 部分：`artifact-index-w08.md` 與 `deck-W08-E-integrated-v1.pdf`（PR #42，11/13 合併）；兩個指定檔名的 pptx 尚未在 main | — | 簡報依 `AGENTS.md` 第五節重做後再交，日期由組長與 E 約定（decisions 第 33 節） |

## 二、八件成果的證據狀態

同 `docs/v12-limitations-midterm.md` 第 3.1 節，這裡只列狀態與缺口，證據出處見該節。

| # | 成果 | 狀態 | 主要缺口 |
|---|---|---|---|
| 1 | 網站、三檔入口、季度、同業比較、收藏儀表板 | 核心項目已簽核（N01–N03，11/06） | F06 延後；手機實機未測 |
| 2 | Researcher／Reviewer 閉環 | 已簽核，附限制（N07，11/06） | 第二段尚未鎖定（組長於正式實驗前鎖定） |
| 3 | 來源、動作、版本、預算、停止原因可追溯 | 有證據 | Agent v2 停止原因待正式評估驗證 |
| 4 | 三份研究 PDF | 部分達成：2317、2330 已發布（Agent v1） | 2454 沒有 LIVE 已發布報告（前瞻第 3 批通過覆核、未發布） |
| 5 | 30 案三模式執行與評分紀錄 | 開發集有評分紀錄 | 保留集 60 run 11/16 起 |
| 6 | 論文 20–25 頁 | 進行中（第四章已在 main） | 第五、六章；研究問題兩套寫法待組長定案 |
| 7 | 簡報、講稿、展示與錄影 | 進行中 | E 的簡報重做、W13 錄影 |
| 8 | 版本、設定、測試、來源交接包 | 進行中 | 交接包 W12–W13 |

## 三、核心凍結

| 凍結 | 狀態 |
|---|---|
| 第一段（案例、分組、資料、B 工具、D 評分規則） | 10/25 核准、10/28 D 簽核，cases_digest 98af84030d45（`data-freeze.md` 第七節） |
| 第一段修訂 1（補齊歷史股價） | 11/11 組長決定，cases_digest 不變（`data-freeze.md` 第八節、decisions 第 25 節） |
| 第一段修訂 2（前瞻第 3 批聯發科負債覆寫） | 11/13 組長端修正，cases_digest 不變，請 B 事後複核（`data-freeze.md` 第八節、decisions 第 32 節） |
| 第二段（prompt、Agent 程式、兩支 runner、預算上限；12 個程式檔與 2 個 prompt） | 截至 11/14 尚未鎖定，組長於正式實驗前鎖定；鎖定前正式 runner 拒絕 live（decisions 第 22、38 節；D `evaluation/d-drafts/v12-runner-freeze.md`） |
| W06 介面凍結 | 見 `W06-freeze-minutes.md`；F06 不在凍結範圍（延後） |

## 四、未完成項與提供人

| 項目 | 提供人 | 影響哪項成果 |
|---|---|---|
| 2454 LIVE 已發布報告 | 組長 | 4 |
| 保留集 60 run（11/16–11/25）與 B、D 盲評（W11） | 組長、D、B | 5、6 |
| 前瞻 1、5、20 日報酬 | D | 5、6 |
| Render 實際記憶體峰值、是否升級 2GB | 組長 | 1、4 |
| 容量 80% 停止線實作 | 組長 | 8 |
| 真實資料庫暫失、20 個並行請求測試 | 組長、D | 8 |
| 手機實機測試 | A | 1 |
| CR-W08-A1（舊 `/api/analyze` 無授權）、A2（PDF 峰值）、A3（核准按鈕） | 組長決定 | 1、4 |
| E 的 W08 簡報（重做後交） | E | 7 |
| 第一段修訂 2 的複核 | B | 5 |
| 研究問題兩套寫法定案 | 組長 | 6、7 |

## 五、已結案的核對

- **2330 前瞻第 2 批是否已發布**（11/11 提出）：B 11/14 回覆是清單漏登，已更新 `evaluation/v12-forward-manifest.csv`：fwd2-2330 改為已發布（rv-db6b0e1b…，11/09），fwd1-2317 補記第 2 版 rv-2ed6652e…（11/09）。文稿「2317、2330 已發布」正確。
