# Agent 6 大工具與模組對照表 (V1.4)

依據專題執行手冊 V1.2 第 02 章「六工具契約」「資料契約 V1.2」與第 04 章 F01/F02 規格，本表定義 Researcher 與 Reviewer 所呼叫工具之責任邊界、可重用模組位置、參數約束與快照欄位需求。

- 版本：V1.4（2026-10-20，W01-B 修正）
- 依據檔案：`agents/tools.py`（宣告與驗證）、`agents/tools_impl.py`（實作）、`agents/register_tools.py`、`agents/calculator.py`、`agents/snapshot.py`、`report_downloader.py`、`main.py`、`financial_analyzer.py`、`valuation_agent/dcf_model.py`、`scripts/build_snapshot_finmind.py`、`data/manual/*.csv`、`data/financial-snapshots.json`
- 路徑：依工作包必交位置存於 `data/tool-field-map.md`；根目錄舊檔僅保留轉址說明。

### V1.4 相對 V1.3 的修正

| 項目 | V1.3 | V1.4 | 理由 |
|---|---|---|---|
| 頂層回傳欄位 | `missing_reason`、`source_refs` | `reason`；來源欄位放在 `data` 內 | 沿用既有框架：`agents/tools.py` 的 `dispatch` 與 `agents/research_graph.py` 讀取 `reason`，不另創欄位 |
| 錯誤狀態 | `error` | `tool_error` | `dispatch` 在工具例外或格式錯誤時固定回傳 `tool_error` |
| 未知公告時間 | `available_at = null` | `available_at = captured_at`，並標 `available_at_basis = captured_at_fallback` | 手冊第 02 章：「未知發布時間以擷取時間判可得性，不回填更早時間」 |
| 股價可得時間 | 保守 14:30 | 交易日 17:30 +08:00 | 與 `tools_impl.get_price_window` 現行實作一致，且晚於 14:30，較保守 |
| `pb_ratio`、`revenue_yoy` | 列為待實作 operation | 刪除；P/B 與營收 YoY 屬 `peer_comparison` 指標，單一公司 YoY 用 `growth_rate` | 手冊限定 `calculate_metrics` 只有五個 operation，不可自行新增 |
| `growth_rate`、`simple_return` | 未確認 | 已實作（`calculator.py` 第 15、24 行） | 已查核程式 |
| 實作狀態 | 部分規格寫成已完成 | 每列分「規格」與「實作現況」，缺口標 W03 | 驗收要求標已知/未知 |

---

## 一、核心原則

1. 全系統只有 6 個工具；`peer_comparison` 是 `calculate_metrics` 的 operation，不是第七個工具。
2. 工具只接受 schema 欄位，不接受 SQL、shell、任意 URL 或路徑（`agents/tools.py` 的 `_FORBIDDEN`、`_ID` 驗證）。
3. 查無資料回傳 `no_data`；欄位缺值為 `null` 並附 `missing_reason`，不補 0、不由模型推估。
4. 所有數字可追溯到不可變快照（`source_id`、`snapshot_id`、`content_hash`、`captured_at`、`available_at`）。
5. 財報期不是公告日；cutoff 之後可得的資料不可回傳。

## 二、統一回傳結構（沿用 `agents/tools.py` 框架）

| 欄位 | 型別 | 說明 |
|---|---|---|
| `status` | string | `ok` / `no_data` / `invalid_input` / `unreadable` / `tool_error` 之一 |
| `tool` | string | 工具名稱 |
| `reason` | string or null | `status` 非 `ok` 時必填，簡短說明原因 |
| `data` | object, array or null | `ok` 時為結果；非 `ok` 時必為 `null` |

- `invalid_input`：參數不合 schema 或規則（由 `tools.validate_tool_call` 或工具本身判定）。
- `no_data`：參數合法但快照內無 cutoff 前可得資料。
- `unreadable`：來源存在但正文無法讀取（例：`paragraph` 為 `null`，CASE-15）。
- `tool_error`：工具拋例外、逾時或回傳格式錯誤，由 `dispatch` 包裝，不讓 job 崩潰。
- `data` 內每筆數值或片段必帶 `source_id`、`snapshot_id`（或 `evidence_version_id`）、`content_hash`、`available_at`；欄位層級缺值以 `null` + `missing_reason` 表示（`agents/review_checks.py` 讀取 `missing_reason`）。

## 三、六工具對照表與可重用模組位置

| 工具 | 宣告與驗證 | 實作 | 可重用既有模組 | 角色 | 規則 | 實作現況（2026-10-20 查核） |
|---|---|---|---|---|---|---|
| `search_evidence` | `agents/tools.py`（ticker 限 2330/2317/2454、query ≤200、limit 1–5） | `agents/tools_impl.search_evidence`；job 內由 `agents/snapshot.SnapshotToolbox` 優先讀案例快照 | `data/financial-snapshots.json` → `evidences` | Researcher | 只查已入庫索引，不爬網；cutoff 後不可回傳 | 已實作。缺口（W03）：`paragraph` 為 `null` 時字串比對會拋例外 |
| `read_evidence` | `agents/tools.py`（`evidence_version_id` 為一般代號） | `agents/tools_impl.read_evidence`；job 內同上 | 同上 | Researcher / Reviewer | 單一不可變片段 ≤1,200 字；無效 ID → `no_data`；`paragraph` 為 `null` → `unreadable` | 部分。缺口（W03）：`null` 段落會崩潰；缺 `source_url` 時自動填通用 MOPS 網址，屬造來源，須改回 `null` |
| `get_financial_snapshot` | `agents/tools.py`（ticker 可含 2379/3034） | `agents/tools_impl.get_financial_snapshot` | `report_downloader.fetch_finmind_dataset`；`scripts/build_snapshot_finmind.py`（季度差分、TTM、EPS 來源）；`data/manual/announce_times.csv`、`balance_overrides.csv` | Researcher / Reviewer | 區分 `single_quarter` / `ytd` / `annual` / `instant`；四連續單季才算 TTM；缺值 `null` | 已實作，連續 4 季檢查已有 |
| `get_macro_snapshot` | `agents/tools.py`（白名單 `CPIAUCSL`、`FEDFUNDS`） | `agents/tools_impl.get_macro_snapshot` | `macro_agent/fred_scraper.py`；`data/manual/macro.csv` | Researcher / Reviewer | 區分 `observation_date` 與 `available_at`；無歷史 vintage 不稱當時已知 | 部分。缺口（W03）：`tools_impl` 內白名單仍是 6 個序列，與 `tools.py` 的 2 個不一致；手冊要求的台股市場指標尚未提供 |
| `get_price_window` | `agents/tools.py`（sessions 1/5/20） | `agents/tools_impl.get_price_window` | `report_downloader.fetch_price_history`；`data/raw/finmind/TaiwanStockPrice_*.json` | Researcher | 未還原收盤價 `raw_close`；可得時間為交易日 17:30 +08:00；停牌或缺價 → `no_data` | 已實作。缺口（W03）：回傳列未帶 `available_at`、`source_id`、`content_hash` |
| `calculate_metrics` | `agents/tools.py`（operation 五選一、`evidence_refs` 必填） | `agents/tools_impl.calculate_metrics` → `agents/calculator.execute_calculation` | `valuation_agent/dcf_model.py`（DCF 公式） | Researcher / Reviewer | 確定性計算，不讓 LLM 自算 | 已實作五個 operation（見第四節） |

註冊入口：`agents/register_tools.py` 將六個實作掛到 `agents/tools._REGISTRY`。

## 四、`calculate_metrics` operation 對應

| operation | 函式 | 輸入 | 規則 | 現況 |
|---|---|---|---|---|
| `growth_rate` | `calculate_growth_rate` | `current`、`previous` | 任一缺值 → 不適用；基期 ≤ 0 → 不適用（負基期成長率無意義，2026-10-20 起）。單一公司季度營收 YoY 用此 operation | 已實作 |
| `simple_return` | `calculate_simple_return` | `entry_price`、`exit_price` | 買價缺或非正 → 不適用 | 已實作 |
| `pe_ttm` | `calculate_pe_ttm` | `price`、`eps_ttm` | 同日未還原收盤價 ÷ TTM EPS；EPS ≤ 0 或缺 → 不適用 | 已實作 |
| `dcf_scenario` | `calculate_dcf_scenario` | `free_cash_flows`（5 年）、`wacc`、`terminal_growth`、`net_debt`、`shares_outstanding` | 任一缺 → 不適用；非 5 年 → 不適用；WACC ≤ g → 不適用；股數 ≤ 0 → 不適用；輸出 WACC ±1%、g ±0.5% 敏感度矩陣，矩陣中 WACC ≤ g 的格子為 `null` | 已實作 |
| `peer_comparison` | `calculate_peer_comparison` | `subject`=2454、`comparators`、`metrics{ticker:{price,eps_ttm,bvps,pb,revenue_yoy,fcf,dcf_intrinsic_value}}` | 最多 4 家；2330 為 `industry_reference`，不入同業平均；P/B = 價 ÷ BVPS，BVPS ≤ 0 → `null` 並附理由 | 已實作 PE、PB、YoY、DCF 差距。缺口（W03）：手冊指標含 FCF，目前未輸出；營收 YoY 只接收輸入，不檢查基期 |

### 4-1 DCF 參數

- FCF = 營業現金流 − 正值 CapEx。FinMind `PropertyAndPlantAndEquipment` 為負值流出，快照轉為正值並記錄；出現與慣例不符的正值時中止並人工確認。
- `valuation_agent/dcf_model.py` 程式預設 WACC 10%、g 3%（手冊第 02 章文字寫 9%，與程式不同，已列待決）。預設值非個股風險估計，引用時須標「參數待核定」。
- 必須輸出每股內在價值與敏感度矩陣，並標示「內在價值非保證成交價」。

### 4-2 同業比較

- 主體 2454；同業 2379、3034；產業參照 2330。
- 所有公司股價為同一基準日；各自財報期與來源明示；每個 NA 指標附理由。

## 五、快照欄位需求（`get_financial_snapshot`）

| 欄位 | 單位 | 幣別 | 期間類型 | 缺值處理 | 來源 |
|---|---|---|---|---|---|
| `ticker`、`period` | — | — | — | 不可缺 | 快照 |
| `period_basis` | — | — | `single_quarter` / `ytd` / `annual` / `instant` | 不可缺 | 快照 |
| `revenue`、`operating_income`、`net_income` | 億元 | TWD | `single_quarter`（YTD 同年同口徑差分） | `null` + `missing_reason` | FinMind `TaiwanStockFinancialStatements` |
| `eps` | 元 | TWD | `single_quarter` | `null` + `missing_reason` | 依 `eps_source` |
| `eps_source` | — | — | — | `mops_direct` / `finmind_quarterly` / `unverified` | 快照 |
| `eps_ttm`、`fcf_ttm` | 元；億元 | TWD | 四連續單季加總 | 不足 4 季或有缺 → `null` | 由快照計算 |
| `operating_cash_flow`、`capital_expenditure`、`free_cash_flow` | 億元 | TWD | `single_quarter`（YTD 差分） | 不補 0 | FinMind `TaiwanStockCashFlowsStatement` |
| `shares_issued`、`treasury_shares`、`shares_outstanding` | 百萬股 | — | `instant` | 不補 0；存量不跨期相加 | FinMind `TaiwanStockBalanceSheet` |
| `bvps` | 元／股 | TWD | `instant` | 非正 → `null` | 歸屬母公司權益 ÷ 流通股數 |
| `interest_bearing_debt`、`net_debt` | 億元 | TWD | `instant` | 不補 0；淨現金可為負 | FinMind + `balance_overrides.csv` |
| `statement_basis` | — | — | — | `consolidated` | 快照 |
| `currency`、`unit` | — | — | — | 不可缺 | 快照 |
| `available_at` | ISO-8601 +08:00 | — | — | 官方時間；未知時用 `captured_at`，不得早於擷取時間 | MOPS 發言時間（`announce_times.csv`） |
| `available_at_basis` | — | — | — | `official` / `captured_at_fallback` / `rule_close_1730` | 快照 |
| `captured_at` | ISO-8601 +08:00 | — | — | 不可缺 | 原始檔擷取時間 |
| `source_id`、`snapshot_id`、`content_hash` | — | — | — | 不可缺 | 快照 |

## 六、既有模組風險盤點（工作包步驟 2）

| 位置 | 問題 | 影響 | 處理週次 |
|---|---|---|---|
| `main.py` 第 403–406 行 | 缺 P/E 時以「營收 ÷ 淨利」代替，缺 P/B 時以「營收 ÷ 營業利益」代替 | 產生看似合理但不是市價比率的數字 | 舊網站路徑；新工具不得引用此值，已列 CR |
| `main.py` 第 337–338 行 | 淨負債全部缺時設為 0 | DCF 估值偏差 | 舊網站路徑；新工具 DCF 缺淨負債即拒算 |
| `financial_analyzer.py` 第 26–31 行 | `money_100m(None)` 回傳 0.0 | 違反 null 與 0 分開 | W03 修正 |
| `report_downloader.py` 第 180–193 行 | 年度 P/E、P/B 取自 FinMind `TaiwanStockPER` | 定義與本專題 TTM P/E 不同 | 新工具不使用，僅舊路徑 |
| `valuation_agent/dcf_model.py` | 預設 WACC 10%、g 3% | 非個股估計 | 參數待核定 |

## 七、已知／未知清單

| 項目 | 狀態 | 依據或缺口 |
|---|---|---|
| 財報公告時間（5 檔 × 2025Q2–2026Q2） | 已知 | `announce_times.csv` 25 列，取自 MOPS 發言時間 |
| FinMind 財報資料集是否含公告日 | 已知：不含 | FinMind 只提供財報期 `date`，不保證有公告日欄位，須另查 MOPS |
| FinMind 財報是否為合併口徑 | 部分已知 | 快照註記「假設為合併報表，請以抽查確認」；快照 25 季 EPS 中 20 季標 `mops_direct`（已與 MOPS 合併損益表對帳），5 季標 `finmind_quarterly` |
| 股價官方入庫時間 | 未知 | 採交易日 17:30 保守規則 |
| FRED 歷史 vintage | 未知 | 只有現行下載值；FEDFUNDS 可得時間為保守估計 |
| TWSE STOCK_DAY 下載時間 | 未知 | 只記雜湊 |
| 台股市場總經指標 | 未提供 | 手冊要求，尚無核准序列 |
| DCF WACC、g | 未核定 | 程式預設 10%、3% |

## 八、F06 圖資料來源設定

| graph_id | 類型 | 核准輸入 | 上限 | LLM | 規則 |
|---|---|---|---|---|---|
| `graph_supply` | 2D 關係網 | `graph-approved.json`（W06 產出） | 20 點／30 線 | 0 次 | 只讀 `review_status = source_text_verified` 的關係；缺原句、網址或文件日期者剔除；`verified_date` 不能代替 `doc_date`；不得以 LLM 猜供應關係 |
| `graph_peer` | 2D 比較 | `data/v12-peer-snapshot.json` | 4 家 | 0 次 | 2454 主體；2379、3034 同業；2330 產業參照不入平均；同一基準日股價 |

來源文件登記見 `graph-source-register.csv`。

## 九、待決事項（組長核定）

1. DCF 參數：WACC 10%（手冊文字 9%）、g 3%、5 年持平 FCF。
2. 股價可得時間 17:30 規則。
3. 台股市場總經指標是否納入白名單及序列 ID。
4. `main.py` 舊路徑的 P/E、P/B 替代與淨負債補 0 是否修正或停用（CR）。