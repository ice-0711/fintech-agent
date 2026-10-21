# W06-A｜收藏儀表板驗收（F03）

- 任務 ID：W06-A｜日期 2026-10-21｜驗收人：組長｜測試協助：D
- 範圍：手冊第 04 章 F03（收藏、已發布清單、估值狀態、資料品質風險、更新時間）

## 1. 已發布清單讀什麼

| 欄位 | 來源 |
|---|---|
| 代號、公司、版本、發布狀態、資料截止、發布時間、PDF 狀態 | `ui/v12-dashboard-fixture.json`（**FIXTURE**；W07 改讀組長的 report_versions） |
| 財報期、來源更新時間、快照過期 | 伺服器用 B 的工具即時算（`get_financial_snapshot`） |
| 估值狀態 | `research_ui/risk.py` 的 ±15% 規則＋`calculate_metrics(dcf_scenario)` |
| 資料品質風險 | `research_ui/risk.py` 的既定檢查 |

伺服器只回 `publication_status == "published"`；草稿版本 `rv-fixture-2454-0003-draft` 不會出現在清單、報告 API 或頁面原始碼（`test_unpublished_report_never_leaves_server`）。

## 2. 純讀實測（四、五檔切換不自動重算）

headless 瀏覽器在 1440×900 依序操作：切換 2330→2317→2454→2330→2454、三次收藏、從選單加 2379 與 3034（共 5 檔）、勾選與取消「只看收藏」、排序新→舊與舊→新、開啟三份報告。全程記錄瀏覽器發出的每個請求：

```
GET /research
GET /static/research.css
GET /static/research.js
GET /api/ui/published
GET /api/ui/comparison/2454
GET /api/ui/replays
GET /api/ui/reports/rv-fixture-2454-0002
GET /api/ui/reports/rv-fixture-2330-0002
GET /api/ui/reports/rv-fixture-2317-0002
```

**沒有任何 POST**：沒有建立 job、沒有呼叫 `/api/analyze`、沒有寫入資料庫。研究頁模組也沒有 import 模型或預算程式（`test_read_only_ui_has_no_model_code`），所以模型呼叫次數為 0。原始紀錄在 `design/w06/screenshot-run-2026-10-21.json`。

## 3. 截圖

| 檔案 | 寬度 | 內容 |
|---|---|---|
| `design/w06/W06-dashboard-360-full.png` | 360 | 收藏 3 檔、三張已發布卡片（含長公司名）、比較卡片 |
| `design/w06/W06-dashboard-390-full.png` | 390 | 同上 |
| `design/w06/W06-dashboard-1440x900.png` | 1440 | 桌機版 |
| `design/w06/W06-favorites-empty-filter-390x844.png` | 390 | 只收藏 3034 並勾「只看收藏」→ 空狀態「收藏中的股票還沒有已發布研究」 |
| `design/w06/W06-readonly-clickthrough-1440x900.png` | 1440 | 純讀操作後的畫面 |

橫向溢出全部 0 px。

## 4. 驗收自查

| 驗收項 | 結果 | 證據 |
|---|---|---|
| 手機無重疊 | ✓ | 360、390 截圖 |
| 未核准不公開 | ✓ | 測試＋草稿內容不在任何回應 |
| 四五檔切換不自動重算 | ✓ | §2 請求紀錄只有 GET |
| 重整收藏仍在；只存代號、最多 5 檔 | ✓ | `test_favourites_are_codes_only_and_capped`；截圖以預存收藏載入 |
| 缺資料不顯示為低風險 | ✓ | 沒有執行任何檢查時顯示「未評估」；關鍵項缺值為「高」（`tests/test_review_risk.py`） |
| 「低」不暗示股價安全 | ✓ 文字固定在每張卡片與報告 | 待 B、D 核對用語 |

## 5. 已知限制

- 清單的發布資料仍是 FIXTURE，等 W07 report_versions。
- 收藏只存在這個瀏覽器，換裝置或清除瀏覽器資料就會消失（手冊規格）。
