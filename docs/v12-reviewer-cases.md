# W05-C Reviewer 三個例子（v12-reviewer-cases）

- 任務 ID：W05-C｜版本：v2（2026-10-31）｜狀態：**草稿，待 D 核對、組長核准**
- 三個例子都只用**開發案例**或**合成驗算例**，不涉及保留案例。
- 每例附「來源／測試標籤」，寫明它是 live、規則離線測試或合成例。本稿不引用任何檢出率或成功率。

## 證據等級說明

| 標籤 | 意思 |
|---|---|
| D 草稿＋B 交叉評分 | D 撰寫的模擬草稿，以覆核規則離線比對；B 於 2026-10-22 重現並交叉評分（有條件通過），組長 10/29 合併 PR #10。**不是模型輸出，尚未正式驗收** |
| live trace | 真實模型執行的 job，附 job_id |
| 合成驗算例 | D 自編的數字（synthetic），只驗證計算或規則，不是真實公司資料 |

---

## 例一：EPS 缺值（關鍵財報在 cutoff 之後才公告）

- **案例**：CASE-18（開發案例，類別「缺少資料」，題型「關鍵證據在 cutoff 之後」）；2454，cutoff 2026-07-20 17:00（B `evaluation/dev-cases.json`）。
- **情境**：截至 cutoff，聯發科尚未公告 2026Q2 財報，所以 2026Q2 的 EPS 在當時是缺值。

| 草稿 | 內容 | 覆核結果 | 說明 |
|---|---|---|---|
| CASE-18-good | 寫明「截至 cutoff（2026-07-20）聯發科尚未公告 2026Q2 財報，無可用數字」 | insufficient | 不補造數字，說明不足與下一確認訊號；這是預期的有效結果 |
| CASE-18-flawed | 寫出 2026Q2 EPS，引用一則 cutoff 之後才可得的來源 | revise，critical 指向 c1 | 規則判定引用來源的可得時間晚於 cutoff（前視） |

- **退件與停止**：flawed 版被退回，要求改用 cutoff 前已可得的來源；若仍找不到，就以 insufficient 停止，不補數字。
- **一個修正紀錄**：good 版原本在限制欄寫出了該來源的公告時間，B 指出這是 cutoff 之後才會知道的資訊，D 於 10/23、10/28 兩度修正文字（B `docs/B-review-W06-D-redo.md` 第二節第 1 點；D `README-redo.md` 修訂紀錄）。這說明「說明不足」的文字本身也不能洩漏 cutoff 之後的資訊。
- **來源／測試標籤**：D 草稿＋B 交叉評分（`evaluation/d-drafts/W06-D-redo/redo/dev-drafts-v2-results.json`）。

## 例二：累計混用（單季 EPS 當成 TTM EPS）

- **案例**：CASE-22（開發案例，類別「數字口徑」，題型「單季 EPS 當 TTM EPS」）；2330，cutoff 2026-08-12 17:00。官方原文同一段落並列單季 EPS 與 1–6 月累計 EPS，誘導誤用（B `evaluation/dev-cases.json`）。

| 草稿或執行 | 內容 | 覆核結果 | 說明 |
|---|---|---|---|
| CASE-22-good（D 草稿） | 單季與 TTM 分開寫，並註明單季值不是 TTM；TTM 列出 2025Q3 至 2026Q2 連續四季 | pass | B 確認 TTM 四季皆已對 MOPS 原文 |
| CASE-22-flawed（D 草稿） | 把單季 EPS 寫成 TTM EPS，期間只有一季 | revise，critical 指向 c1 | 規則判定 TTM 不是連續四個單季 |
| live dual，job e9045bbd（2026-10-31） | 草稿口徑正確，但 TTM 期間寫在 period 欄 | 第一次：模型 pass、規則 revise，最終 revise；第二次：模型 pass、規則 insufficient，最終 insufficient，預算用完停止 | 組長事後判定為**誤擋**，10/31 修正規則（見 W04 case-walkthrough-v1.md） |
| live dual 重跑，job 0dd723ce（2026-10-31，新規則） | 單季、累計、TTM 分開，TTM 期間 2025Q3–2026Q2 | 模型 pass、規則 pass，最終 pass（通過覆核） | 沒有補查；通過覆核不等於正確，正確性待 D 評分 |

- **退件與停止**：flawed 版被退回，要求用 get_financial_snapshot 確認連續四個單季；不足則 TTM EPS 標 null。live 執行顯示，補查 1 輪後 8 次模型發送用完，系統停止而不發布。
- **來源／測試標籤**：前兩列為 D 草稿＋B 交叉評分；第三列為 live trace（組長 `agent/calib-v1-day4.json`），屬修正前規則；第四列為修正後重跑的 live trace（組長 `agent/calib-v1-dual-rerun-2.json`）。修正前後是不同規則下的結果，不直接比較。

## 例三：參照角色（把 2330 算進 2454 的同業平均）

- **規則**：2454 的同業平均只算 2379、3034；2330 是產業參照，主體 2454 也不計入（B fact sheet 第七節第 3 點）。草稿若把 2330 放進同業平均，覆核規則 peer_includes_2330 列為 critical，要求以 calculate_metrics 的 peer_comparison 重算（組長 `agents/review_checks.py`）。
- **驗算**：D 以合成數字驗證：2379 的 P/E 設為 20、3034 設為 10、2330 設為 50；正確的同業平均是 (20＋10)÷2＝15.0，若誤含 2330 會變成 26.67。B 的程式結果為 15.0，與手算一致（D `evaluation/d-drafts/W02-D/W03-D/v12-financial-test-results.md` 第 7 項）。D 另寫了測試：同業平均含 2330 時必須出現 peer_includes_2330，只含 2379、3034 時不出現（D `evaluation/d-drafts/W02-D/W04-D/test_reviewer_v12.py`）。
- **退件與停止**：判 revise，要求移除 2330 後重算；修正後重新覆核。
- **來源／測試標籤**：合成驗算例＋D 草稿測試（未驗收）。**目前沒有這一題的 live trace**，repo 的 `tests/` 中也沒有對應的正式測試；需要時請 D 或組長補。

---

## 共通的退件與停止規則

- 退件：判 revise，且補查輪少於 2、剩餘模型發送至少 2 次時，退回 Researcher。
- 停止：判 pass、判 insufficient，或預算用完（每 job 8 次模型發送含重試、10 次工具、2 補查輪、180 秒）。
- 任何情況都不補造數字，也不跳過覆核去發布。

（組長 `handoff/state-machine-v1.md`。）

## 待補

| 缺什麼 | 提供人 |
|---|---|
| 三例的正式驗收 | D、組長 |
| 例三的 live trace 或 repo 正式測試 | D、組長 |
