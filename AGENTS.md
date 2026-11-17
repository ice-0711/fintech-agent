# 給協作 AI 的專案規則（組長 2026-11-08）

你在協助 fintech-agent 專題的組員。回答或產出前先照這份規則判斷，**能自己判斷的就直接做，不要叫組員去問組長**。

## 一、什麼算「可以用」

- **main 上的版本就是可用版本。** 檔案推上 main（或 PR 已合併）即可直接引用，不需要再等組長核准文字。
- 舊檔頭或手冊提示詞寫的「草稿」「待核准」「只依核准文稿」，一律以本規則為準：**main 上有 = 可用**。
- 簡報與文稿不需要標「草稿」。

## 二、只有這幾件事不能自己決定

1. **實驗結果數字**（通過數、評分、成本、前瞻結果）只能用 D 交出的檔案或 `agent/`、`research/` 內的紀錄；沒有的就寫「待正式實驗」，不要自己填。
2. **Agent v1 與 v2 的結果不放在同一張表比較**；引用時標明版本（見 `handoff/agent-version-changes.md`）。
3. **不寫任何保留集案例的內容**（題目、情境、答案）。只能提「20 個保留案例、封存、只用於正式評分」。
4. 「通過覆核」不等於「正確」，不寫正確率、成功率。

## 三、文字、排版、用詞、頁面安排

全部由組員自己判斷，不需要問組長。

## 四、真的需要問組長時

先寫三行再問，不要直接轉貼 AI 的回答：

1. 要組長決定什麼（一句話）
2. 自己的建議
3. 不決定會卡住什麼

如果第 3 點寫不出來，代表不需要問，直接做。

## 五、簡報與對外成果（給評審看的）（組長 2026-11-14）

聽眾是評審，不是組員。第二節的四件事照舊（數字來源、v1／v2 分開、不寫保留集內容、不寫正確率），但**怎麼呈現**改成這樣：

1. **正文頁每頁只留一句要評審記住的話。** 截圖頁要寫「這張圖要看什麼」，不能只放圖和檔名。
2. **來源、版本、內部用語不上正文頁。** 檔案路徑（`docs/…md`、`design/…png`）、commit、「main」、任務代號（W08-E）、組員代號（D 組、B 已核對）、「依組長確認之文稿」這類字樣，一律放在**備註欄**或最後的**附錄頁「資料來源與版本」**。
3. **限制聲明全份只講一次。** 「不代表正式實驗結果」「開發集不等於保留集」「通過覆核不等於正確」集中寫在實驗設計那一頁，附錄再列一次；其他頁不重複。
4. **截圖如果是 MOCK 或 REPLAY**，圖旁留一個短標籤（例如「重播畫面」）即可，不寫整句聲明。
5. **還沒有的結果寫「待正式實驗」**，留版位，不填估計值。
6. **頁碼連續；備用頁放在最後**，標題不寫「備用 19」這類內部編號。

手冊驗收清單裡的「來源與版本完整」「未完成聲明不刪」「明確標回放片段」，以第 2、3、4 點的做法（附錄、備註欄、短標籤）視為符合，不需要每頁都寫。

## 六、正式實驗期間不能改的檔案（組長 2026-11-17）

正式實驗 formal-v2 在 11/16–11/25 每天 19:30 執行。開跑前程式會嚴格核對下列檔案，**任何一個被改過，當天的實驗就會停止**（11/17 就因為評分規則檔被改而停了一次）。到 60 個 run 跑完、組長宣布之前：

- 下列檔案不要修改、搬動或改名，也不要送包含它們的 PR：
  - `agents/` 整個資料夾（含 `agents/prompts/`）
  - `scripts/dev_traces.py`、`scripts/formal_runs.py`
  - `data/` 整個資料夾、`fixtures/` 整個資料夾
  - `evaluation/dev-cases.json`、`evaluation/test-cases-sealed.json`、`evaluation/cases_manifest_v1.json`、`evaluation/run-plan.json`
  - `evaluation/d-drafts/rubric-v1-final.md`、`evaluation/d-drafts/protocol-v1.md`（評分規則的補充寫在另一個檔，例如 `rubric-v1-confirmed-1116.md`）
  - `valuation_agent/dcf_model.py`
  - 根目錄的 `data-contract.md`、`source-register.csv`、`graph-reviewed.csv`、`graph-source-register.csv`
- 真的需要改：先照第四節的三行格式問組長，不要直接改、不要先送 PR。
- 送 PR 前自己檢查：`python scripts/build_freeze.py --verify --strict`，顯示「凍結紀錄一致」才送。
- 評分者（B、D）交出評分前，不要打開 `evaluation/formal/runs-v2.jsonl`，也不要看 GitHub 上「Formal evaluation v2」的 commit（決策 44）；`evaluation/formal/scoring-v2/` 在匯出前不要放任何檔案。
- 其他檔案（`research_ui/`、`static/`、`design/`、`media/`、`demo/`、`docs/`、`slides/`、`report/`、`deliverables/`、`tests/`，以及上面沒列到的 `evaluation/` 文件）照常可以改。

## 參考

- 決策紀錄：`handoff/decisions-2026-10.md`（第 19 節：C 的文稿已全部核准）
- 版本差異：`handoff/agent-version-changes.md`
