# 校準 v1 交叉評分（B）

- 評分人：組員 B｜日期：2026-11-05｜對照：D 的 `evaluation/d-drafts/calib-v1-scores-D.txt`（PR #22，main 23d5ea3）
- 範圍：組長指定的 30 列（10 案 × 3 模式；dual 用新規則 10 列，single CASE-01 用 10/28 那筆）
- 資料：`agent/calib-v1-day1～5.json`、`agent/calib-v1-dual-rerun-1.json`、`-2.json`、`fixtures/dev/case_fixtures.json`、凍結的 `data/financial-snapshots.json`
- **獨立性聲明**：B 手上沒有匿名評分包（S01–S30 對應表），B 開始核對前已看過 D 的標籤，所以這不是盲評。B 的做法是不看 D 的理由，直接從 trace 逐列重核數字與來源，再對照 D 的標籤。若組長要求盲評，請提供匿名包，B 重做。

---

## 一、結論

- **30 列中，B 與 D 的計分標籤全部一致**（supported／unsupported／不計分／NA）。
- B 用程式逐一核對 30 列草稿中的 **53 個事實數值**：52 個與案例證據原文或凍結快照相符；剩下 1 個（CASE-08 single 的 2,255,894,000,000 元）人工核對正確，程式沒認出來的原因見第四節。
- 有 **2 處計分建議修正**（第三節第 1、2 點），以及 **3 處應記入備註、與 S30 同類的「摘要說了沒發生的事」**（第三節第 3–5 點）。

---

## 二、S 編號對應（B 依案例與主張內容推定，請 D 確認）

| S | 案例 | 模式 | job | D | B |
|---|---|---|---|---|---|
| S01 | CASE-04 | workflow | fe9c0a0c | c1–c3 supported | 同意 |
| S02 | CASE-26 | workflow | 52bd0586 | c1–c3 supported | 同意 |
| S03 | CASE-04 | single | ca56d65a | c1、c2 supported；c3 不計分 | 同意 |
| S04 | CASE-22 | dual | 0dd723ce | c1–c3 supported | **c3 應不計分**（見三-1） |
| S05 | CASE-22 | workflow | 771b5eda | c1–c3 supported | 同意 |
| S06 | CASE-08 | dual | d8884abc | c1 supported；選證據不足合理 | 同意 |
| S07 | CASE-01 | single | 981c0e65 | c1、c2 supported；c3 不計分 | 同意 |
| S08 | CASE-11 | single | c31d12d3 | c1 supported | 同意 |
| S09 | CASE-01 | workflow | 2754d649 | c1、c2 supported | 同意 |
| S10 | CASE-19 | workflow | 55ae291b | 不符合預期行為 | 同意（組長 11/03 裁決） |
| S11 | CASE-29 | single 或 dual | a6ec16a8／e5ca79fe | 不計分 | 同意 |
| S12 | CASE-08 | single | 5587a174 | c1、c2 supported；c3 不計分 | 同意；c3 量級錯誤確認（見三-6） |
| S13 | CASE-22 | single | b592c572 | c1–c3 supported | 同意 |
| S14、S20、S24 | CASE-18 | 三模式 | 4e0956d8、de1d50cf、587905fa | 不計分 | 同意（S14 或 S20 的「無法再呼叫工具」見三-5） |
| S15 | CASE-19 | dual | 69f824c0 | 不符合預期行為 | 同意 |
| S16、S18 | CASE-15 | dual、workflow | bf36dc58、33d1ab99 | 不計分 | 同意（dual「快照被截斷」見三-4） |
| S17 | CASE-26 | single | 173860b7 | 不計分 | 同意計分，**備註需補**（見三-3） |
| S19 | CASE-29 | single 或 dual | | 不計分 | 同意 |
| S21 | CASE-19 | single | 932a7a1a | c1、c2 supported | 同意（見三-7） |
| S22 | CASE-11 | dual | 9fc9e029 | c1 supported | 同意 |
| S23 | CASE-11 | workflow | 046c841c | c1、c2 supported | 同意 |
| S25 | CASE-29 | workflow | 6f5296a8 | NA | 同意 |
| S26 | CASE-01 | dual | 91c25cc4 | c1–c3 supported | 同意 |
| S27 | CASE-26 | dual | cae08337 | c1–c3 supported | 同意，**備註需補**（見三-3） |
| S28 | CASE-15 | single | 186de31a | c1 supported | 同意（1,521.83／228.68／243.35 與凍結快照相同） |
| S29 | CASE-08 | workflow | b0817216 | c1、c3 supported | 同意 |
| S30 | CASE-04 | dual | 85c6b6c1 | 摘要 unsupported | 同意：trace 只有 search_evidence（no_data）與 get_financial_snapshot，沒有呼叫 get_price_window |

---

## 三、需要修正或補備註的地方

1. **S04 c3（CASE-22 dual）應記不計分**：這一條的 kind 是 `inference`（內容是「TTM 86.28，單季不可當 TTM」）。D 在其他題對推論一律記「不計分」，這題記了 supported，前後不一致。數字本身正確。
2. **S13 若其實是 dual**：如果 D 手上的對應和 B 推定的相反（S04 是 single、S13 是 dual），就改 S13 的 c3。請 D 依匿名包確認。
3. **CASE-26 的「逾時」（S17、S27）是沒發生的事**：
   - single（173860b7）的主張與摘要都說「read_evidence 逾時」，但 trace 只有 search_evidence 與 get_financial_snapshot，**從頭到尾沒有呼叫 read_evidence**。
   - dual（cae08337）的摘要說「未呼叫 read_evidence 因逾時」。Researcher 確實沒呼叫，但原因不是逾時：Reviewer 後來呼叫 read_evidence 是回 no_data（引用編號錯），也沒有逾時。
   - 和 S30 是同一類問題。c1 是 unknown、不計分，但兩題都應在備註記「摘要／主張描述了未發生的工具事件」，與組長 10/24「此案未觸發逾時」一致。
4. **CASE-15 dual（bf36dc58）「財務快照資料遭截斷」**：trace 中 get_financial_snapshot 回 ok，只有一個 context_digested 事件（系統壓縮舊工具結果），不是資料被截斷。屬不精確敘述，建議備註記下；c1 是 unknown，不影響計分。
5. **CASE-18 single（4e0956d8）「無法再呼叫工具」**：預算只用了模型 4／8 次、工具 2／10 次，並不是不能再呼叫。屬不精確敘述，建議備註記下；不影響計分（unknown、選證據不足符合 allow_insufficient=True）。
6. **S12 c3 的量級錯誤確認**：官方是 2,525,894,433 千元 ＝ 25,258.94 億元；二手摘要是「2 兆 2,558.94 億元」＝ 22,558.94 億元。草稿寫「2,525 億與 2,255 億」，兩個都小了 10 倍。c3 是推論、不計分，但備註應寫清楚是「量級錯誤 10 倍」。
7. **S21（CASE-19 single）同意 supported**：c1「USD 40.0 Billion (synthetic)」逐字出自案例證據，c2 的 NTD 7,065.6 億也相符；草稿把兩個數字分開列、沒有換算或相除，沒有產生假精確值。案例證據本身標了 synthetic，是這個案例故意放的擾動，引用它不算把合成數字當成真實公司事實。

---

## 四、B 自己的更正：中文金額函式沒處理空格（交組長）

- CASE-08 的二手摘要寫「2 兆 2,558.94 億元」（數字和單位之間有空格）。組長依 CR-W08 實作的 `chinese_amounts()` 不接受空格，回傳空清單，所以覆核規則會把正確的 2,255,894,000,000 元判成「來源不支持」。
- **B 11/02 說「開發集 10 案的證據沒有中文單位金額」是錯的**：當時的掃描用的是同一個不接受空格的寫法，漏掉了 CASE-08。目前校準結果不受影響，因為 CASE-08 single 不經覆核，dual 的 c2 是 unknown、沒有數值，但保留集可能有同樣寫法。
- 修正方式（只改一行，在 `[兆億萬仟千佰百]+` 前後允許空白）：
  ```python
  CN_AMOUNT_RE = re.compile(r"(?:\d[\d,]*(?:\.\d+)?\s*[兆億萬仟千佰百]+\s*)+(?:\d[\d,]*(?:\.\d+)?)?")
  ```
  B 已驗證：「2 兆 2,558.94 億元」→ 2,255,894,000,000；「5,118 億 5,700 萬元」→ 511,857,000,000；原本 7 個測試例子的結果不變；「EPS 29.43 元，增加 50.9%」、「2026 年 6 月」仍不會被誤抓。副作用是「2,525,894,433 千元」會多一個換算成元的候選值，換算本身正確，不會放過錯的數字。
- 建議測試補一例：`chinese_amounts("2 兆 2,558.94 億元") == [2255894000000.0]`。屬第二段，W09 鎖定前處理；並請更正 decisions 第 11 節「開發集沒有中文單位金額」那句。

---

## 五、B 的抽查（組長 11/03 指定 S01–S08、S26）

S01–S08、S26 的所有事實數值，B 都已逐一對過案例證據與凍結快照，全部相符：27.25、86.28、49.33、2,480、CPI 332.568、FEDFUNDS 3.63、25,258.94、948.03、599.74、−723.39、1,270,380,250、860,310,695、67.72%、766,602,651、60.34%、2,525,894,433、4.27。