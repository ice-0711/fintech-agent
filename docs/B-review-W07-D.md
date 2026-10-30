# B 交叉評分：W07-D 初版（PR #11）

- 評分人：組員 B｜日期：2026-10-31
- 基準：`origin/main` dfbc481（PR #11 已於 44dfcb5 合併）
- 範圍：`evaluation/e2e-w07.md`、`evaluation/v12-pdf-forward-check.md`、`scripts/forward_eval.py`、`tests/test_forward_eval.py`、`evaluation/forward-signals-batch1.json`
- 結論：**通過（初版）**，需更新 4 處過時敘述、補 2 項輸入，並請組長核定 1 項規則（方向訊號從哪裡來）

---

## 一、B 重跑結果

| 項目 | 結果 |
|---|---|
| `tests/test_forward_eval.py` | 29 項全數通過（B 在 dfbc481 獨立重跑） |
| entry／D1／D5／D20 規則 | 與 `research/forward-batch-1-sources.json` 的 `price_basis` 一致：cutoff 10/30 21:00 → entry 11/02 開盤；D1 11/02、D5 11/06、D20 11/27 收盤（11 月無國定假日） |
| 收盤可得 17:30 | 與組長 10/22 核定一致 |
| 未還原價格、除權息只標記 | 與 B 的資料契約一致 |
| `zero_return` 不計入分子分母 | 與組長 10/29 核定一致 |
| 輸出路徑防護、不 import agents | 程式碼確認無誤 |

## 二、e2e-w07.md 需要更新（已過時）

| 位置 | 目前寫法 | 應改為 | 依據 |
|---|---|---|---|
| 第三節 E01 | 只有 CASE-01、CASE-08 兩案 live | 已有 6 案 live：day1 CASE-01／08、day2 CASE-04／11、day3 CASE-15／19（gemini-3.5-flash-lite，各三模式）。day2 CASE-04 dual 有 1 輪補查（`supplement_rounds=1`），但結果仍為 `insufficient_evidence`（stop_reason `researcher_insufficient`），**仍沒有「補查後修正成功」的 live 例子** | `agent/calib-v1-day2.json`、`agent/calib-v1-day3.json`（commit 7d5169f、1bd16a2） |
| 第三節 E05 | 未確認 A 的分支 `codex/W07-A-claim-refs` 是否合併 | 已合併（PR #9，1cae159）。B 已核對新報告 2317-rv-915bb95c、2330-rv-d407e7cc、2454-rv-d1fafb87：引用全部 `resolved=true`、證據 `hash_match=true`；EPS、TTM、營收、FCF、P/E、P/B、DCF 差距、同業平均 23.23／6.29／13.63% 與 B 事實表一致。仍是 MOCK（`model_id=null`） | B 10/31 核對 |
| 第四節「方向」列、程式第 199 行註解 | 「規約未定，待組長登記」 | 「組長 2026-10-29 核定：零報酬不計入方向命中率分子與分母，另列筆數」 | `handoff/decisions-2026-10.md` 第八節 |
| 第六節「前瞻批次 1」 | 10/30 21:00 才凍結 | 前瞻輸入 B 已備齊（證據 7 筆、總經 7 筆、2379／2454 第三季公告與對帳）；快照產生與是否納入 Q3 待組長決定 | `data/manual/forward/` |

## 三、B 提供的輸入口徑（回應第六節「B 提供口徑」）

**交易日曆**
- 來源：FinMind `TaiwanStockTradingDate`，欄位 `date`。
- 範圍：2026-10-30 起至少到 2026-12-31（第 3 批 D20 在 12 月）。
- FinMind 只有已發生的交易日；未來日期以證交所公告的年度休市日核對。11 月無休市日。
- 檔案放 `evaluation/forward/`，不要放 `data/forward/`。

**價格**
- 來源：FinMind `TaiwanStockPrice`（**未還原**，不要用 `TaiwanStockPriceAdj`）。
- 欄位：`date`、`stock_id`、`open`、`close`、`Trading_Volume`；runner 已能直接讀這些欄名。
- 範圍：三檔研究主體 2330、2317、2454。2379、3034 只做比較，不進前瞻評估。

**除權息（`--actions`）**
- 2330：第二季現金股利 7.0 元，除息日 2026-12-10。只在第 3 批（cutoff 11/13）的 D20 窗口內。
- 2454：上半年現金股利每股 24.5 元，除息交易日 2027-01-05（MOPS 第14款，2026-10-30 17:08:16）。不在三批任何觀察窗內（第 3 批 D20 預期 12/11）。
- 2317：目前沒有。

## 四、程式小建議（不影響 29 項測試，可選）

1. **除息日剛好是 entry 當天時不必標記。** 第 192 行 `entry_date <= d` 會把這種情況標成 `corporate_action_in_window`。但 entry 用的是當天開盤價，已經是除息後的價格，報酬不受影響。可改成 `entry_date < d`，或保留現狀，在文件註明這是保守標記。
2. **日曆只有過去日期時，NA 原因會被歸錯。** 如果日曆只匯出到 as_of 當天，還沒到的 D20 會記成 `window_beyond_calendar`，而不是 `immature`。建議日曆含已公告的未來交易日；或在文件說明這兩種 NA 在 as_of 之前的意思相同。

## 五、請組長核定（新）

**前瞻方向訊號 `direction` 從報告的哪個欄位來？**
- 目前 A 的報告 JSON 沒有 `direction` 欄位，只有估值狀態 `valuation.status`（above_model／near_model／below_model／undeterminable）。
- 估值狀態是「股價相對模型值」，不是漲跌預測。若直接對應成 up／down，會變成用 DCF 做漲跌預測，與「非獲利保證、不做預測」的定位衝突。
- B 建議兩案擇一：
  - (a) 報告新增由 Researcher 明示、Reviewer 覆核的 `direction` 欄位。
  - (b) 第 1 批全部記 `none`，只展示 1／5／20 日路徑，不算命中率。
- 決定前，`forward-signals-batch1.json` 的 direction 維持 null。