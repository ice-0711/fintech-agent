# W04-C 案例逐步說明（case-walkthrough-v1）

- 任務 ID：W04-C｜版本：v2｜狀態：**組長 2026-11-08 核准，可直接引用**
- 來源：組長 `agent/calib-v1-day4.json`（產生於 2026-10-31 16:30 台北；commit d41c828；模型 gemini-3.5-flash-lite；prompt researcher-v1.2.2、reviewer-v1.2.0）。
- 案例：**CASE-22（開發案例，類別「數字口徑」，題型「單季 EPS 當 TTM EPS」）**，標的 2330，cutoff 2026-08-12 17:00（台北）。
- 執行類型：**live**（真實模型每一步自己決定）。job_id：`e9045bbd-9c61-4d79-bc16-f12139605eca`（以下簡寫 e9045bbd）。
- trace ID 寫法：`e9045bbd#seq`。trace 記錄模型發送、工具名稱與回傳狀態；表中的數值取自草稿所引用的證據或觀察編號，不是 C 計算的。

## 一、逐步紀錄

| 步驟 | 角色 | 輸入或動作 | 工具 | 觀察（回傳狀態） | 下一動作 | trace ID |
|---|---|---|---|---|---|---|
| 1 | Researcher | 研究問題、2330、cutoff；第 1 次模型發送 | — | — | 選擇先搜尋證據 | e9045bbd#3 |
| 2 | Researcher | 搜尋證據段落 | search_evidence | ok | 再發送一次模型，決定下一步 | e9045bbd#4 |
| 3 | Researcher | 第 2 次模型發送 | — | — | 同一輪選兩個工具 | e9045bbd#5 |
| 4 | Researcher | 取得 cutoff 時可得的財務快照 | get_financial_snapshot | ok | 讀官方證據原文 | e9045bbd#6 |
| 5 | Researcher | 讀官方證據 ev-dev-22-official | read_evidence | ok | 壓縮舊工具結果後撰稿 | e9045bbd#7、#8 |
| 6 | Researcher | 第 3 次模型發送，輸出草稿 | — | 輸出草稿，含 c3（TTM 主張） | 交給 Reviewer | e9045bbd#9、#10 |
| 7 | Reviewer | 第 4 次模型發送 | — | — | 讀證據核對 | e9045bbd#11 |
| 8 | Reviewer | 核對 ev-dev-22-official | read_evidence | ok | 第 5 次模型發送，作出覆核 | e9045bbd#12、#13 |
| 9 | Reviewer | 覆核決定 | — | 模型判 pass，規則判 revise，最終 revise；critical 指向 c3 | 退回 Researcher（補查第 1 輪） | e9045bbd#15 |
| 10 | Researcher | 第 6 次模型發送，修正草稿 | — | 輸出修正草稿 | 再交 Reviewer | e9045bbd#16、#17 |
| 11 | Reviewer | 第 7 次模型發送；再讀同一證據 | read_evidence | **refused**：相同參數已呼叫 2 次 | 第 8 次模型發送 | e9045bbd#18、#19 |
| 12 | Reviewer | 第 8 次模型發送，作出覆核 | — | 模型判 pass，規則判 insufficient；critical 指向 c3、c1 | 模型發送 8 次用完，停止 | e9045bbd#20、#22 |

**結束狀態**：insufficient_evidence，停止原因 review_insufficient。預算使用：模型發送 8 次、工具呼叫 4 次、補查 1 輪、主動時間 14.743 秒（trace 的 budget 欄）。

**trace 保存的草稿內容**：trace 只保存一份草稿（draft 欄），其中三種口徑分開寫：c1 單季 EPS 27.25 元（引用 ev-dev-22-official，標 single_quarter）、c2 1–6 月累計 EPS 49.33 元（同一證據，標 ytd）、c3 TTM EPS 86.28 元，期間 2025Q3–2026Q2（引用工具觀察編號 obs-2，標 ttm；依呼叫順序推斷為步驟 4 的快照結果，待組長核對）。trace 沒有分別保存第一版與修正版，本稿不推測兩版差異。

## 二、覆核指出的問題（原文照錄）

- c3：「TTM 需要四個連續單季，收到 None」，要求「get_financial_snapshot(ticker, cutoff) 確認連續四個單季都已公告；不足則 eps_ttm 標 null」。
- c1：「還有 critical 問題但沒有剩餘預算可以補查，不可宣稱已核實」。

## 三、這次覆核其實是誤擋

組長 2026-10-31 檢討校準第 2、4 天結果後判定，dual 模式在 CASE-22 是**誤擋**：草稿把 TTM 的期間寫在 period 欄（「2025Q3-2026Q2」），沒有另外填 quarters 欄，覆核規則只讀 quarters 欄，因此讀到「None」，誤判為四季不連續。組長的修正是：quarters 沒填時改讀 period，四季清單或起訖寫法都可判定；仍必須剛好連續四季，數字仍要對得上工具結果。凍結資料與 B 的工具都沒有改。修正自校準第 5 天起生效，Reviewer prompt 升為 reviewer-v1.2.1；**第 1–4 天的 dual 結果與第 5 天之後不可直接比較**（組長 `handoff/decisions-2026-10.md` 第 9 節）。

草稿中 TTM 的數字本身有原文依據：B 已確認 2330 的 TTM EPS 86.28 元＝2025Q3 17.44＋2025Q4 19.51＋2026Q1 22.08＋2026Q2 27.25，四季皆已對 MOPS 原文（B `docs/B-review-W06-D-redo.md` 第二節第 3 點）。

### 規則修正後的重跑

組長於 2026-10-31 晚間以新規則（reviewer-v1.2.1）重跑 CASE-22 dual（job `0dd723ce-bd18-4f17-a2d6-508b3479d280`，組長 `agent/calib-v1-dual-rerun-2.json`）：

| 步 | 角色 | 動作 | 工具 | 結果 | trace ID |
|---|---|---|---|---|---|
| 1 | Researcher | 取得 cutoff 時可得的財務快照 | get_financial_snapshot | ok | 0dd723ce#4 |
| 2 | Researcher | 搜尋證據段落 | search_evidence | ok | 0dd723ce#6 |
| 3 | Researcher | 輸出草稿：單季 27.25、累計 49.33、TTM 86.28（2025Q3–2026Q2）分開 | — | 草稿 | 0dd723ce#9 |
| 4 | Reviewer | 核對 ev-dev-22-official | read_evidence | ok | 0dd723ce#11 |
| 5 | Reviewer | 覆核決定 | — | 模型 pass、規則 pass，最終 pass，沒有 critical | 0dd723ce#14 |

job 以 succeeded 結束：5 次模型發送、3 次工具呼叫、0 輪補查。**通過覆核不等於答案正確**，正確性要等 D 評分。修正前（e9045bbd）與修正後（0dd723ce）是不同規則下的結果，不直接比較。

## 四、同一案例在另外兩種模式

同一天、同一案例的另外兩次 live 執行（同一份 trace 檔）：

| 模式 | job_id | 結束狀態 | 模型發送 | 工具呼叫 |
|---|---|---|---|---|
| single | b592c572-edb9-4d5b-af66-1cb34fcd6c9b | succeeded（未經覆核） | 4 | 3 |
| workflow | 771b5eda-a4d2-47e5-9536-06dbae22fca6 | succeeded（未經覆核） | 1 | 5 |

兩者的草稿同樣把單季、累計與 TTM 分開。這只是單一開發案例的紀錄，**不能據此比較三種模式的好壞**；三模式的比較由 D 依正式實驗（20 保留案 × 3 模式 = 60 次）判定。

## 五、本案例能說明與不能說明的事

能說明：模型自己決定先搜尋、再同時取快照與讀原文；觀察結果出現在草稿的引用中；覆核由模型判斷與確定性規則共同決定，規則可以推翻模型的 pass；補查有輪數上限；預算用完就停止，不跳過覆核發布。

不能說明：Reviewer 的準確率；dual 是否優於 single 或 workflow；模型內部如何思考（本稿不使用隱藏思考過程）。
