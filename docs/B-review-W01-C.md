# B 核對：W01-C 三份初稿（財務口徑與 F01／F02／F04／F06 技術敘述）

- 核對人：組員 B｜日期：2026-10-31
- 對象：`origin/main` dfbc481 中 C 上傳的三份檔案。C 說的檔名對應如下：

| repo 內檔名 | C 說的檔名 |
|---|---|
| `gemini-code-1793374244448.md` | `docs/motivation-v1.md` |
| `gemini-code-1793374235372.md` | `docs/v12-motivation.md` |
| `gemini-code-1793374240016.md` | `W01-meeting.md` |

- 依據：`data-contract.md`、`agents/budget.py`、`agents/review_contract.py`、`handoff/v12-scope-quota.md`、`handoff/decisions-2026-10.md`、`handoff/W06-gate-v12.md`、`docs/CR-W05-holdout.md`
- 結論：表格第 2、3 項財務口徑 **通過**。F06 與「60 runs」需修正，另有 3 處文字修正。

---

## 一、W01-meeting.md 表格核對結果（可直接填入「核對結果」與「修正意見」欄）

| 核對項目 | 結果 | 修正意見與依據 |
|---|---|---|
| 2. 期間口徑與 TTM 規則 | ✅ 通過 | 與 `data-contract.md` 一致：四種口徑分開；YTD 轉單季需同年同口徑且有前期；`instant` 不可跨期相加；連續 4 個單季才算 TTM，且 EPS 都須經原文驗證，否則回 null，不以單季 × 4 推估。建議補半句「不以單季乘 4 推估」 |
| 3. 估值、財務指標與同業規則 | ✅ 通過（建議補 2 處） | 公式與門檻都正確。建議：(1) P/E 也是「非正分母標 NA、不算負 P/E」，目前只寫在 P/B；(2) DCF 補「TTM FCF 為負時不計算（例：2317）」。同業：2454 的同業平均只算 2379、3034，2330 為產業參照（`data-contract.md` 第 121 行；組長 10/21 核定） |
| 4. Agent 工具與預算（組長／D 核） | 程式值相符，供組長參考 | `agents/budget.py`：每個 job 最多 8 次模型發送（含重試）、10 次工具呼叫、2 輪補查、180 秒主動時間。`agents/review_contract.py`：Reviewer 只能用 4 個工具（read_evidence、get_financial_snapshot、get_macro_snapshot、calculate_metrics），需要查價或搜尋時退回 Researcher。「同時 1 job」請組長確認 |

## 二、F01／F02／F04／F06 技術敘述

| 項目 | 結果 | 說明 |
|---|---|---|
| F01 季度與 TTM | ✅ | 同上第 2 項 |
| F02 同業比較 | ✅ | `peer_comparison` 在 `calculate_metrics` 內、最多 4 家；採同日股價、明示各自財報期；2379／3034 不另建 LLM 任務 |
| F04 資料品質 | ✅ | 欄位（期間、available_at、幣別、單位、statement_basis、來源、快照、hash）與「未知公告以 captured_at 判定、兩者皆無視為不可得」都正確。風險分級不代表股價風險，正確 |
| **F06 小型 2D 圖** | ❌ **需修正** | 三份文件都還寫「條件式開發，11/06（W06 凍結）前未完成則轉後續版本」。兩個問題：(1) 組長 **2026-10-22 已決定 F06 延後**、轉後續版本、N06 不驗收，成果不得寫「關係圖已上線」（`handoff/W06-gate-v12.md` 第 4 節）；(2) 11/06 是 `v12-scope-quota.md` 的完成期限，**不是 W06 凍結**；W06 第一段凍結是 10/25 |

建議文字（W01-meeting 決議三、v12-motivation 表格 F06 列）：
> F06 小型 2D 圖為條件式項目（≤20 點／30 線、須有核准來源）。組長已於 2026-10-22 依第 04 章閘門決定延後，轉後續版本；N06 不驗收，成果不得宣稱關係圖已上線。目前經年報原文核對的關係僅 2 條（2454→2330、2379→2330）。

## 三、其他須修正處

| 檔案 | 原文 | 修正 | 依據 |
|---|---|---|---|
| 三份都有 | 「30 案：10 開發、20 保留，三模式 60 runs」 | 「30 案（10 開發、20 保留）；正式測試為 20 保留案 × 3 模式 = 60 runs」。原寫法容易被讀成 30 案共 60 runs | `docs/CR-W05-holdout.md`（W10、60 run） |
| W01-meeting.md 決議三 | 「確認 고정 30 案」 | 「確認固定 30 案」（混入韓文字） | — |
| motivation-v1.md 第二節第一段 | 「3034 Novatek 聯詠」 | 「3034 聯詠」，與其他檔一致 | `data-contract.md` 第 121 行 |
| 三份都有 | 檔名是 `gemini-code-*.md`，放在根目錄 | 請 C 改名搬到正確位置（指令見第四節） | — |

## 四、給 C 的改名指令（C 自己在 repo 根目錄執行）

```
git pull
git mv gemini-code-1793374244448.md docs/motivation-v1.md
git mv gemini-code-1793374235372.md docs/v12-motivation.md
git mv gemini-code-1793374240016.md W01-meeting.md
git commit -m "C W01: 初稿改名歸位（依 B 核對）"
git push
```
`W01-meeting.md` 要放根目錄或 `docs/`，依 C 原本的規劃決定。