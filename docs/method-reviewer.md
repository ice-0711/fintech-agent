# W05-C Reviewer 與缺值處理方法稿（method-reviewer）

- 任務 ID：W05-C｜版本：v2（2026-10-31 依組長程式文件、D 草稿與 B 交叉評分修訂）｜狀態：**組長 2026-11-08 核准，可直接引用；之後的修改照常提 PR，不需再等核准**
- 依據：組長 `agents/prompts/reviewer-v1.2.txt`、`handoff/state-machine-v1.md`、`agents/review_checks.py`、`agents/research_graph.py`、`handoff/decisions-2026-10.md`；D `evaluation/d-drafts/W06-D-redo/`；B `docs/B-review-W06-D-redo.md`。

## 一、Reviewer 是什麼

Reviewer 是 dual 模式中的覆核角色。它的任務是找出 Researcher 草稿中不受證據支持、時間錯置、口徑錯誤或計算不一致的主張；不得因文字流暢、結論合理或估值偏正面就通過。Reviewer **沒有發布、核准或修改資料的權限**，只能給出覆核決定（組長 `agents/prompts/reviewer-v1.2.txt`）。

Reviewer 只能使用四個工具：read_evidence、get_financial_snapshot、get_macro_snapshot、calculate_metrics。需要搜尋或查股價時，必須透過「需要的證據」（required_evidence）欄位退回 Researcher；沒有工具預算時，不能說已經核實（同上）。

## 二、三種決定與 job 狀態

Reviewer 的決定只有三種，名稱與程式一致（組長 `agents/research_graph.py` 的 DECISION_RANK；`handoff/state-machine-v1.md`）：

| 決定 | 意思 | 之後 | job 終態 |
|---|---|---|---|
| pass | 沒有未解決的 critical 問題，引用與必要數字已核對，限制已呈現 | 結束 | succeeded |
| revise | 有可以在現有來源與預算內修正的 critical 問題 | 補查輪少於 2、且剩餘模型發送至少 2 次時，退回 Researcher；否則停止 | 修正後重新覆核 |
| insufficient | 關鍵資料缺失、衝突無法排除、必要來源未讀到，或預算不足 | 結束 | insufficient_evidence |

「資料不足」是有效的研究結果，不是失敗（組長 reviewer prompt）。

每一個問題（issue）要寫明：指向哪一條主張（claim_id）、嚴重度（critical 或 minor）、原因，以及具體到工具與參數的「需要的證據」，例如「read_evidence(ev-xxx)，核對 c2 的營收期間與單位」；不能只寫「請改善」（同上）。

## 三、模型判斷與規則判斷

最終決定由**模型的判斷**與**確定性規則的判斷**共同產生，取兩者中較嚴格的一個（pass < revise < insufficient）。因此規則可以推翻模型的 pass（組長 `agents/research_graph.py`）。

規則由組長納入 `agents/review_checks.py`，其中部分來自 D 的草稿規則（repo 根目錄 README.md：「規則已由組長納入 agents/review_checks.py」）。與本稿三個例子有關的規則包括：引用的來源可得時間晚於 cutoff（lookahead）、TTM 不是連續四個單季（ttm_not_consecutive）、把累計當成單季（ytd_as_single）、同業平均納入 2330（peer_includes_2330）。

自 2026-10-31 起，可得時間與 cutoff 的先後改由程式比對，模型不再自行比較。模型若列出時間問題，而程式確認該主張引用的來源都在 cutoff 前可得，該問題會被移除，並記 `timing_issue_refuted` 事件（含模型原判與原文）供評分查核；移除後若沒有其他 critical 問題，模型的結論會改為 pass，之後仍與規則的判斷合併、取較嚴格者（組長 `handoff/decisions-2026-10.md` 第 9 節；`agents/review_checks.py` 的 `drop_refuted_timing_issues`）。也就是說，只有在這種「時間問題被程式否定」的情況下，模型原本的 revise 或 insufficient 才會改為 pass。

**Agent v2 的規則變更**（2026-11-06 起，組長 `handoff/decisions-2026-10.md` 第 14 節、`handoff/agent-version-changes.md`）：覆核新增 `unsupported_system_claims`，草稿提到「無資料、逾時、截斷、無法呼叫工具」而執行紀錄中沒有時列 critical；停止原因改由程式依執行紀錄產生。11/07 補修：unknown 主張引用 no_data 的工具結果不再列 critical（fact、inference 引用 no_data 仍列 critical）；數字比對接受「40.0」「40.00」這類寫法；Reviewer prompt 升為 reviewer-v1.2.2。本稿三個例子與下方 4／10 的結果都屬 Agent v1，與 v2 的結果不放在同一張表比較。

## 四、Reviewer 不是全能的

以下是 repo 中已記錄的實例，說明 Reviewer 會漏抓，也會誤擋：

| 情況 | 內容 | 處理 | 出處 |
|---|---|---|---|
| 漏抓 | D 的 CASE-11-flawed 草稿，以未註明口徑的數字冒充個體營收；當時的規則判 pass | 組長 10/24 核定採用 basis_unspecified 規則，10/26 合併 | B `docs/B-review-W06-D-redo.md`；組長 decisions 第七節 |
| 漏抓 | A 的三份 MOCK 報告中，有事實主張引用的公告原文找不到該數字；規則沒有攔下 | 組長 10/29 核定：事實數字必須出現在引用來源或工具結果中，否則列 critical | A `reports/v12-online-pdf-check.md` 第 0 節；組長 decisions 第八節 |
| 誤擋 | CASE-22 dual（job e9045bbd，10/31 第 4 天）的 TTM 期間寫在 period 欄，規則只讀 quarters 欄，誤判為不連續 | 組長 10/31 修正；新規則重跑（job 0dd723ce）模型與規則都判 pass，通過覆核。第 1–4 天 dual 結果與第 5 天後不可直接比較 | 組長 decisions 第 9 節；`agent/calib-v1-dual-rerun-2.json`；W04 case-walkthrough-v1.md |
| 誤擋 | CASE-11 dual（job da86df90，10/29 第 2 天）：證據可得時間 14:15 早於 cutoff 17:00（台北），Reviewer 模型自行比較時區出錯，判 insufficient；規則判 pass，最終取較嚴格的 insufficient | 組長 10/31 改由程式比對可得時間；新規則重跑（job 9fc9e029）模型與規則都判 pass，通過覆核 | 組長 `agent/calib-v1-day2.json`、`agent/calib-v1-dual-rerun-1.json`、decisions 第 9 節 |

新規則下（10/31 第 5 天與 dual 重跑，校準 v1、Agent v1），開發集 10 案的 dual 執行有 4 案通過覆核（CASE-01、11、22、26）（CASE-26 依組長 10/24 決定註明：此案未觸發逾時，逾時處理以離線測試為證），其餘 6 案停在證據不足（組長 `agent/calib-v1-day5.json`、`agent/calib-v1-dual-rerun-1.json`、`-2.json`）。「通過覆核」只表示模型與確定性規則都沒有找到 critical 問題，**不代表內容正確**；正確性要等 D 評分。

D 也在自己的草稿中說明：預期決定是 D 先寫的，修補規則也是看過案例後才補，所以「10 份草稿全部符合預期」只代表與 D 的預期一致，**不能說明 Reviewer 的真實檢出能力**（D `W06-D-redo/redo/README-redo.md` 第五節）。本稿不引用任何檢出率或成功率。

## 五、R04、R05 的引用回查（請 D 核對）

| 本稿或方法章的說法 | 來源 | 對應的本專題設計 | D 核對 |
|---|---|---|---|
| agent 每一步要從環境取得真實回饋 | R04 | 工具回傳四欄位結果，以觀察編號記錄 | |
| agent 常設停止條件，例如最大迭代次數 | R04 | 8 次模型發送、2 補查輪、180 秒 | |
| 一個 LLM 產生、另一個評估並回饋的循環 | R04 的 evaluator-optimizer | dual 模式的 Researcher 與 Reviewer；但本專題另加確定性規則與工具限制，兩者**不等同** | |
| 模型回傳函式名稱與參數，由應用程式執行後回傳結果 | R05 | 工具由程式執行，模型不直接存取資料 | |
| 函式呼叫在執行前先驗證（最佳實務「Validation」） | R05 | 工具呼叫由程式檢查與執行；發布需組長登入並核對 hash，模型沒有發布權 | |

R05 於 2026-11-01 改依英文原頁（Interactions API 版本，最後更新 2026-09-23）。英文頁的最佳實務是「執行前先驗證函式呼叫」，沒有「後果重大時先請使用者確認」這句，所以上表第五列已改寫。組長 2026-11-03 決定引用英文原頁（查閱日期 2026-11-01）；本節引用的是函式呼叫的最佳實務原則，與用哪種 API 無關。註腳：「該頁範例使用 Interactions API，本專題程式使用 generate_content；本文只引用其函式呼叫最佳實務。」

## 六、人工核准與發布

發布由人決定，模型沒有發布權。研究 job 本身不發布，報告版本一律先是草稿；組長登入後，必須帶著自己看過的報告 hash 核准，hash 不符就不發布；核准後產生 PDF、寫入 Storage，並讀回比對 hash，全部成功才算發布（組長 `handoff/state-machine-v1.md` 第 5 節；A `reports/v12-online-pdf-check.md` 第 5 節）。預算與重試見 method-budget.md。

## 七、待補

| 缺什麼 | 提供人 |
|---|---|
| 第五節 R04／R05 對應核對 | D |
| 三個例子的正式驗收（目前是草稿與交叉評分） | D、組長 |
| 本稿技術敘述核對 | B |
