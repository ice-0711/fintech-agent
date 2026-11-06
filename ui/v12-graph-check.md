# W08-A｜F06 2D 關聯圖：定稿檢查（關閉本版範圍）

- 任務 ID：W08-A 第 4 步｜日期 2026-11-05｜驗收人：組長
- 結論：**F06 在 V1.2 不上線，11/06 依手冊關閉未完成的圖範圍，轉後續版本。** 網站與 PDF 都沒有 2D 圖。

## 1. 依據

| 來源 | 內容 |
|---|---|
| `handoff/decisions-2026-10.md` 第五節（10/22） | F06 2D 關聯圖**延後**，轉後續版本；N06 不驗收 |
| `handoff/deployment-v1.md` 第四節第 11 步（11/02） | F06「未達，依決定延後」，圖不增加 worker 重工作 |
| `operations/v12-resource-gate.md` 第七節（11/02） | 網站沒有 2D 圖，也就不增加 worker 重工作 |
| A 工作包 W08 第 4 步 | 「在 F06 已核准時」才做點選來源、搜尋／縮放／重設、20 點 30 線、手機列表 → F06 未核准，本步只做關閉檢查 |

B 已產出 `graph-approved.json`（graph-v1，10/25）與 11/05 的 2D 分類字典 `data/v12-graph-dictionary.md`；本版**沒有讀取或渲染**它們，也沒有改任何正式案例。

## 2. 驗收項逐項（11/05 實測）

| 驗收項 | 結果 | 證據 |
|---|---|---|
| 11/06 關閉未完成圖範圍 | ✅ 關閉，本文件即紀錄；`ui/v12-graph-draft/README.md` 同樣寫延後 | — |
| 0 LLM | ✅ 純讀路徑模型請求 0 次 | `performance/v12-read-only.json`、`performance/v12-click-check.json` 的 server_counters |
| PDF／來源不被圖遮住 | ✅ 沒有圖；另以瀏覽器確認「下載 PDF」按鈕與來源抽屜中心點的最上層元素就是它自己（未被任何東西蓋住），1440 與 390 都是 | `performance/v12-click-check.json` 的 `pdf_button_uncovered`、`source_drawer_uncovered`；截圖 `design/w08/W08-report-drawer-{1440,390}.png` |
| 20 點 30 線上限、點選來源、搜尋／縮放／重設、手機列表 | 不適用（F06 未核准） | — |
| 純讀資源 | 見 `design/performance-w08.md`：沒有圖時的讀取資源即為基準 | — |

## 3. 若後續版本重新開啟 F06

沿用 `ui/v12-graph-draft/README.md` 第三節：只讀 `graph-approved.json`、沒有來源的關係不畫線、每條線可點開來源、圖上標版本與核准時間；PDF 以表格為主。開工前需組長以 CR 重新核准範圍。
