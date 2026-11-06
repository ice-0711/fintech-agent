# W04-C Researcher 流程與 Agent 定義（method-researcher）

- 任務 ID：W04-C｜版本：v2（2026-10-31 依組長的 trace 與狀態機文件修訂）｜狀態：**草稿，待 B 核對技術事實、組長核准**
- 依據：組長 `handoff/state-machine-v1.md`（2026-10-21）、`agents/prompts/researcher-v1.2.txt`、`agent/*.json` 開發集 trace；B `docs/B-W07-C-技術事實.md`；R04。
- 本稿只描述流程與定義。實驗結果由 D 提供，本稿不引用任何成功率。

## 一、本專題怎麼定義 Agent

本專題的 Agent，是指模型依手上的證據**自己選工具**、取得工具回傳的**觀察**、接受 Reviewer 的**覆核**、在預算內**有限補查**，並在證據足夠或預算用盡時**停止**。

這與固定流程不同。R04 把「由預先寫好的程式路徑編排 LLM 與工具」的系統稱為 workflow，把「LLM 動態主導自己的流程與工具使用」的系統稱為 agent，並指出 agent 每一步要從環境取得真實回饋，且常設最大迭代次數等停止條件。R04 是工程觀點，不是統一的學術定義。

**功能多不等於 Agent。** 系統功能很多、用了語言模型，並不使它成為 Agent。判斷標準是：下一步做什麼，由模型依證據決定，還是由程式固定。本專題用三種模式對照這一點（組長 `handoff/calibration-plan-v1.md`、`agents/research_graph.py`）：

| 模式 | 誰決定下一步 | 是否覆核 | 初次研究可用的模型發送 |
|---|---|---|---|
| workflow | 程式先執行固定工具，模型只撰稿一次 | 否 | 1 次 |
| single | Researcher 自選工具 | 否 | 最多 8 次 |
| dual | Researcher 自選工具，Reviewer 覆核 | 是 | 前 4 次；第 5 次保留給覆核 |

## 二、Researcher 的流程

每一輪包含四個要素：

| 要素 | 說明 |
|---|---|
| 輸入 | 研究問題、標的代號、資料截止時間（cutoff）、快照編號 |
| 選工具 | 從六個工具中依目前證據選擇；每輪最多執行 2 個工具 |
| 觀察 | 工具回傳的四欄位結果（狀態、工具、原因、資料），以觀察編號（obs-N）記錄 |
| 下一動作 | 依觀察決定：再取資料、交計算工具計算、輸出草稿，或回報證據不足 |

（組長 `handoff/state-machine-v1.md` 第 2、3 節；B `docs/B-W07-C-技術事實.md` 第五節。）

Researcher 撰寫草稿時，替每一條主張標註 fact、inference 或 unknown。fact 必須引用實際讀過的證據版本編號或本次工具結果的觀察編號；數學一律交給 calculate_metrics；不用記憶補營收、EPS、股價；null 不可補 0（組長 `agents/prompts/researcher-v1.2.txt`）。

## 三、交給 Reviewer 之後

dual 模式下，Researcher 的草稿交給 Reviewer。Reviewer 回覆 pass、revise 或 insufficient：

- pass：job 結束，狀態為 succeeded。
- revise：若補查輪少於 2，且剩餘模型發送至少 2 次，就退回 Researcher 修正；否則停止。
- insufficient：job 結束，狀態為 insufficient_evidence。

（組長 `handoff/state-machine-v1.md` 第 2 節。Reviewer 的規則詳見 W05 method-reviewer.md。）

## 四、live、mock、trace 重播的差別

| 名稱 | 意思 | 寫作時可以怎麼說 | 依據 |
|---|---|---|---|
| live | 真實模型（gemini-3.5-flash-lite）每一步自己決定，工具與快照是真的 | 可描述為實際執行，必須附 job_id | 組長 `agent/*.json` note |
| mock | 模型的回覆是預錄腳本，工具與快照是真的 | 只能寫「模擬（MOCK）」，不得講成模型的判斷或研究結論 | 同上 |
| trace 重播 | 網站重播已保存的 live 紀錄（trace），只讀、不呼叫模型 | 只能寫「重播」，不得講成即時執行 | A `research_ui/replays.py`（標示 REPLAY） |

**注意：「trace 重播」和 F04 的「evidence-replay」是兩件事。** trace 重播只是把已保存的執行紀錄重新顯示，不呼叫模型；evidence-replay 是 F04 的驗證方法，用事後擷取、依 cutoff 篩過的資料實際呼叫模型重新研究（見方法章 3.7 節，組長 `handoff/v12-scope-quota.md`）。

例如 A 在 W07 產生的三份線上 PDF 是 MOCK（模型決策為預錄腳本），PDF 首頁標示「MOCK 測試報告：不是研究結論」（A `reports/v12-online-pdf-check.md` 第 2 節）。

## 五、證據的規則

- 案例中的每個動作都以 trace 為證：以 **job_id** 加 **步驟序號（seq）** 識別，例如 `e9045bbd#6`。
- trace 記錄的是模型發送、工具名稱與回傳狀態；工具回傳的數值，以草稿中引用的觀察編號或證據編號對照。
- **不使用模型的隱藏思考過程作證明。** 只用 trace 中可見的工具呼叫、回傳狀態、草稿與覆核結果。
- 沒有 trace 的步驟，一律標示「情境規劃」。

## 六、本週案例

依組長提供的開發集 trace，本週案例取自三模式校準第 4 天（2026-10-31）的 CASE-22 dual 模式 live 執行，見 case-walkthrough-v1.md 與 v12-agent-case.md。該次執行在 10/31 修正前的規則下被誤擋；修正後重跑（job 0dd723ce，組長 `agent/calib-v1-dual-rerun-2.json`）模型與規則都判 pass，通過覆核（通過覆核不等於正確，正確性待 D 評分）。CASE-22 是開發案例，不是保留案例。

## 七、待補

| 缺什麼 | 提供人 |
|---|---|
| 本稿技術敘述核對 | B |
| 文字核准 | 組長 |
