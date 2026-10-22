# B 交叉評分：D 的 W06 重做草稿（CASE-11、15、18、22、29）

- 評分人：B　日期：2026-10-22
- 對象：ice-0711/fintech-agent PR #1（commit 1337184，草稿，未合併）
- 方法：B 於雲端重現 `run_v2.py`；另以 repo 現行 `agents/review_checks.py`、並依 `agents/snapshot.py` 的 `snapshot_view()`（paragraph 為 null 時改為空字串）模擬實際管線再跑一次；草稿內容逐則對照 dev-cases v1.5、開發快照與 B 的 MOPS 對帳（250／250）。
- 不涉及保留案。

## 一、重現結果

| 草稿 | D 預期 | D 修補版 | repo 現行（模擬管線） | B 判定 |
|---|---|---|---|---|
| CASE-11-good | pass | pass | pass | ✅ 同意 |
| CASE-11-flawed | revise | revise | **pass（漏抓）** | ✅ 同意預期；repo 有缺口 |
| CASE-15-good | insufficient | insufficient | insufficient | ✅ |
| CASE-15-flawed | revise | revise | revise | ✅ |
| CASE-18-good | insufficient | insufficient | insufficient | ⚠️ 決定同意，文字需改（見二-1） |
| CASE-18-flawed | revise | revise | revise | ✅ |
| CASE-22-good | pass | pass | pass | ✅ |
| CASE-22-flawed | revise | revise | revise | ✅ |
| CASE-29-good | insufficient | insufficient | insufficient | ✅ |
| CASE-29-flawed | revise | revise | revise | ✅ |

D 修補版 10／10 可重現。repo 現行在實際管線中 9／10：CASE-15 **不會當掉**（snapshot_view 已把 null 正文改為空字串），唯一缺口是 CASE-11-flawed。

## 二、內容意見

1. **CASE-18-good 洩漏 cutoff 後資訊**：限制欄寫「ev-dev-18-late 的 available_at 為 2026-07-31T18:41:57」。cutoff 為 07-20，工具不會回傳此片段，Agent 不可能知道它的 ID 與公告時間。建議改為「截至 cutoff 查無 2026Q2 財報公告，無可用數字；下一確認訊號：2026Q2 財報公告」。
2. **CASE-11**：good 草稿 c1「2,525,894,433 千元」與 MOPS 115Q2 合併綜合損益表本季欄逐字一致（B 對帳確認）。解讀同意：題目未要求個體數字時，標明合併口徑並將個體列 unknown 可 pass；若題目要求個體數字則應 insufficient（`test_focus`）。
3. **CASE-22**：TTM 86.28 = 2025Q3 17.44 + 2025Q4 19.51 + 2026Q1 22.08 + 2026Q2 27.25，四季皆已對 MOPS 原文（`data/v12-mops-reconciliation.csv`），D 的待確認事項可結案。
4. **CASE-15、29**：符合「不補造、不執行不可信指令」。
5. 預期決定由 D 先寫、修補規則看過這 5 案才補，D 已在 README 誠實標註，同意其限制說明；10／10 不代表真實檢出能力。

## 三、對 repo 的建議（凍結清單內，需組長決定）

| 修補 | 是否必要 | 理由 |
|---|---|---|
| basis_unspecified：來源 `basis = unspecified` 時列 critical | **建議採用** | repo 現行漏抓 CASE-11-flawed（以未註明口徑數字冒充個體營收）；屬開發集校準，規則一般化（只看 basis 欄位），不依賴保留案 |
| unreadable_source：paragraph 為 null 時列 critical | 選用（防禦性） | 管線中 snapshot_view 已轉空字串，不會當掉；直接呼叫 check_draft 時才需要 |

`agents/review_checks.py` 在凍結清單內，若採用須在 10/23 凍結前合併，並補一則測試（CASE-11-flawed → revise）。

## 四、D 核對表的待確認事項回覆

| # | 事項 | 回覆 |
|---|---|---|
| 1 | 來源段落數字與 MOPS 原表 | 已完成：財務快照 250／250 一致；5 個全域片段改為 MOPS 原文（evidence-audit-w07.md） |
| 2 | CASE-26 allow_insufficient | dev-cases v1.5 為 `allow_insufficient: true`，預期 insufficient 不衝突 |
| 3 | CASE-11 解讀 | 同意（見二-2） |
| 4 | CASE-04 17:30／14:30 | 組長 10/22 核定全專案 17:30，已結案 |
| 5 | 保留 20 案核對 | 由 D 本人執行，B 不經手 |
| — | 舊 W04 草稿用到 CASE-07、13、14、20、25 | 同意不再作開發校準；建議在舊檔 README 標註「已作廢（案例分組變更）」 |

## 五、結論

D 的重做草稿可作為開發集 Reviewer 校準素材（**有條件通過**）：CASE-18-good 文字需修正；basis_unspecified 修補建議提交組長於凍結前決定。
