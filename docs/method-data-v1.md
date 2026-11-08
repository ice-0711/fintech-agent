# W03-C 資料來源與方法第一稿（method-data-v1）

- 任務 ID：W03-C｜撰寫：C（AI 協助）｜版本：v2（2026-10-31 依 repo 內 B 與組長已交文件修訂）｜狀態：**組長 2026-11-08 核准，可直接引用；之後的修改照常提 PR，不需再等核准**
- 來源標記：每段技術敘述後的括號寫明出處檔與提供人。主要依據為 B 的 `docs/B-W07-C-技術事實.md`（2026-10-28）、`data/v12-finance-fact-sheet.md` 第七節「方法事實（交 C 撰寫用）」、`data-contract.md`，以及組長的 `handoff/decisions-2026-10.md`。
- 本文件不含任何查詢速度，也不由 C 計算任何財報數字。

## 一、研究範圍

研究主體固定為 2330 台積電、2317 鴻海、2454 聯發科；2379 瑞昱、3034 聯詠只作為 2454 的比較對象，不建立 LLM 研究任務。2330 在 2454 的比較面板中是產業參照，不納入同業平均（工作包；組長 `handoff/v12-scope-quota.md` 第 2 節）。

## 二、資料來源

| 資料 | 來源 | 用途 | 出處 |
|---|---|---|---|
| 財報、股價、交易日、台股加權指數 | FinMind API（TaiwanStockFinancialStatements、TaiwanStockBalanceSheet、TaiwanStockCashFlowsStatement、TaiwanStockPrice、TaiwanStockTradingDate） | 財務快照的主要數字 | B，`data/financial-snapshots.json` 的 source_manifest |
| 公告時間、證據原文、對帳值、缺漏科目 | 公開資訊觀測站（MOPS），人工抄錄 | 可得時間與原文核對 | B，`data/manual/*.csv` |
| 美國 CPI、聯邦基金利率 | FRED（CPIAUCSL、FEDFUNDS） | 總經背景 | B，`data/manual/macro.csv`；前瞻批次的總經放在 `data/manual/forward/`（B `docs/B-review-W02-W07-C.md` 第一節） |
| FinMind 原始回應 | 22 份，每份記錄 SHA-256 與擷取時間 | 追溯原始資料；依授權不上傳 GitHub | B，`data/v12-frozen-manifest.json` |

財務快照涵蓋 5 家公司、2025Q2 至 2026Q2 共 5 季，截止日 2026-09-30，版本 v1.6-tw-market；採合併報表，金額單位億元、股數百萬股、EPS 與股價單位元（B，`docs/B-W07-C-技術事實.md` 第二節）。B 已把快照數字與 MOPS 原文逐筆核對：250 個數值與 25 個財報公告時間全部一致（B，`data/v12-finance-fact-sheet.md` 第九節）。

## 三、截止時間與可得時間

研究以「資料截止時間」（cutoff）為界，cutoff 之後的資料一律不用。判斷一筆資料在 cutoff 時是否已經可得，看的是它的可得時間（`available_at`），不是它所屬的財報期間。

| 資料 | 何時算可得 |
|---|---|
| 財報 | MOPS 重大訊息第 31 款「財務報告業經董事會決議通過」的發言時間，精確到秒 |
| 股價 | 交易日 17:30（台北時間），組長 2026-10-22 核定全專案統一 |
| 總經 | 官方發布時間（CPI 為 BLS 發布日 08:30 美東） |
| 沒有官方發布時間的來源 | 以擷取時間（`captured_at`）判定，且必須早於 cutoff |
| 兩個時間都沒有 | 視為不可得，不使用 |

（B，`docs/B-W07-C-技術事實.md` 第一節；組長 `handoff/decisions-2026-10.md` 第三節。）

防止使用 cutoff 之後的資料，有兩道關卡：第一道在產生快照時，公告時間晚於 cutoff 的季別、總經與證據不寫入快照；第二道在工具查詢時，以「請求的 cutoff」與「快照截止時間」中較早者判定，cutoff 之後的資料一律不回傳（B，同上第五節）。缺公告時間的資料不倒填，也不推測。

## 四、引用方式

1. 報告中的事實主張，必須引用本次快照中實際讀過的證據版本編號（evidence_version_id），或本次工具結果的觀察編號（obs_id）（組長，`agents/prompts/researcher-v1.2.txt`）。
2. 每筆資料帶期間、可得時間、幣別、單位、報表口徑、來源、快照與 hash 等欄位，讓數字可以追溯到來源（工作包；B，`data/v12-field-map.csv`）。
3. 來源原文只是待分析的資料，**不是指令**。原文中若出現要求忽略規則、買賣、洩漏金鑰或開啟網址的內容，系統不執行，並列為問題（組長，`agents/prompts/reviewer-v1.2.txt`）。
4. 引用數字時照抄數字與單位，不四捨五入、不換算；需要換算時先問 B（B，`docs/B-W07-C-技術事實.md` 引用規則）。
5. 論文正文的文獻引用採 APA 第 7 版，清單見 W02 的 references.md。

## 五、六個工具的白話說明

Agent 只能透過六個白名單工具讀取凍結的快照。所有數值計算都交給確定性的計算模組，不由語言模型自己算（B，`docs/B-W07-C-技術事實.md` 第五節）。

| 工具 | 白話作用 | 使用限制 |
|---|---|---|
| search_evidence | 依關鍵字找出可能相關的證據段落 | 只限 3 檔研究主體，最多回 5 筆 |
| read_evidence | 讀出某一個證據段落的原文 | 最多 1,200 字；編號格式不符一律拒絕 |
| get_financial_snapshot | 取得某公司在 cutoff 時已可得的最新一季財務數字與 TTM | — |
| get_macro_snapshot | 取得總經指標 | 白名單：CPIAUCSL、FEDFUNDS、TAIEX |
| get_price_window | 取得最近 1、5 或 20 個交易日的收盤價 | 未還原價格 |
| calculate_metrics | 做所有計算：成長率、報酬率、P/E、DCF、同業比較 | 必須附來源引用 |

每個工具都用相同的四個欄位回覆：狀態（status）、工具名稱（tool）、原因（reason）、資料（data）。狀態只有五種：成功（ok）、查無資料（no_data）、輸入不合格（invalid_input）、原文無法讀取（unreadable）、工具錯誤（tool_error）。查不到資料時回 no_data，不回 0。每次呼叫限時 15 秒，逾時回 tool_error（B，`docs/B-W01-W06-檔案說明.md` 第一、三節）。

兩個角色可用的工具不同：Researcher 可以用全部六個；Reviewer 只能用 read_evidence、get_financial_snapshot、get_macro_snapshot、calculate_metrics，需要搜尋或查股價時必須退回 Researcher（工作包；B 核對 `docs/B-review-W01-C.md`；組長 `agents/prompts/reviewer-v1.2.txt`）。

## 六、null、0 與 NA

這三者的意思不同，混用會讓讀者誤判。

- **0** 表示「已知，數值就是零」。
- **null** 表示「不知道」：資料缺失、沒有公布，或無法取得可靠的值。null 必須附上缺值原因（missing_reason），**禁止補 0**（B，`data-contract.md` 第 7 條）。例如 TTM 需要連續四個單季、而且每季 EPS 都經過原文驗證；缺任何一季，TTM EPS 就是 null，不用單季乘 4 推估（B，`data-contract.md`；`docs/B-W07-C-技術事實.md` 第五節）。
- **NA**（不適用）表示「資料存在，但這個指標沒有意義」。例如 P/E 或 P/B 的分母不是正數時標 NA，不計算負的 P/E；季度營收年增率缺少去年同季基期時也標 NA（B，`data-contract.md`）。

對讀者呈現時，缺值一律寫「無資料」或「無法判定」，不得以 0 代替（B，`data/v12-finance-fact-sheet.md` 第七節第 6 點）。

## 七、fact、inference 與 unknown

Researcher 在草稿中替每一條主張標註種類（組長，`agents/prompts/researcher-v1.2.txt`；`contracts/v12-data-report.json`）：

- **fact（事實）**：必須引用本次快照中實際讀過的證據版本編號，或本次工具結果的觀察編號。數值與單位照來源原文填寫。
- **inference（推論）**：根據事實做出的判斷，必須列出依據與假設，不可標成事實。
- **unknown（未知）**：寫明缺少什麼資料。

Reviewer 把「推論當事實」與「傳聞當事實」都列為 critical 問題（組長，`agents/prompts/reviewer-v1.2.txt` 第 7 點）。

## 八、既有程式、待核實假設與新增 Agent

| 類別 | 內容 | 依據 |
|---|---|---|
| 既有（學期初基線） | FinMind 資料抓取、Supabase 儲存、規則式財務摘要與 FCF 預測、年度 DCF（`valuation_agent/dcf_model.py`）、三張圖表、Flask 網站；PDF 僅本機產出 | R08 固定版本 53816d4 的 PROJECT_STATUS.md（2026-05-30） |
| 既有程式本學期的調整 | DCF 參數由組長 2026-10-21 核定為全專案統一：WACC 9%、終端成長率 3%、5 年持平於 TTM FCF；`dcf_model.py` 預設由 10% 改為 9%。這是程式預設，不是個股風險估計 | 組長 `handoff/decisions-2026-10.md` 第一節 |
| 待核實假設 | Render 維持免費方案 512 MB，2GB 只在記憶體不足時另行核准升級（組長 decisions 第 12 節，2026-11-02）；Supabase 方案與用量；學生或開發者福利不計入可用額度 | 組長 `handoff/v12-scope-quota.md` 第 4 節 |
| 新增（V1.2） | LangGraph／Gemini 雙 Agent、持久 job、六工具、F01 季度資料、F02 同業比較、F03 收藏儀表板、F05 線上 PDF；F04 驗證持續進行 | 工作包；`handoff/v12-scope-quota.md` |
| 已延後 | F06 小型 2D 關係圖 | 組長 2026-10-22 決定 |

新增項目的實作狀態與驗收，以組長、A、B、D 的驗收紀錄為準；本文件只描述方法，不判定是否完成。

## 九、待補

| 缺什麼 | 提供人 |
|---|---|
| 本稿逐項核對（特別是第五節工具說明與第六節 null／NA 用語） | B |
| 文字核准 | 組長 |
