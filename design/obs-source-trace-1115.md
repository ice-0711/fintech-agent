# obs-* 對回來源；事實主張必須有來源（B 11/15）

- 負責：A（陳柏臣）｜日期：2026-11-15｜分支 `codex/A-obs-source-map`（基於 main 11d8a5e，第二段鎖定之後）
- 依據：B 11/15 的回覆（四個實作重點，以及「對不到判 missing」）

## 一、為什麼要改

Agent v2 的草稿引用的是工具觀察編號 `obs-1`、`obs-2`（這個 job 的第幾次工具呼叫），不是快照片段編號 `ev-…`。以第 3 批為例：

- 2317 的 c1–c3 只引用了 obs-1、obs-2、obs-3、obs-5。
- 2454 只引用了 obs-1～obs-3。

改之前，這種報告一發布就會出兩個問題：

- 來源全部顯示「未解析」，因為網站只認得 `ev-`。
- 「來源可追溯」反而判通過：舊規則只檢查主張引用的 `ev-` 片段，草稿一個都沒有引用，就等於沒有東西可以擋。

## 二、規則

1. **只依這個 job 的工具紀錄來對**：checkpoint 裡每個 obs 的工具、參數、回傳結果，和決策 29 匯出用的是同一份。不重跑工具，也不採用模型自己的說法。
   - 參數的來源：checkpoint 裡模型的 function_call，用 worker 記錄的 `args_hash` 對上是哪一次呼叫。
2. **各工具的對應方式**：

   | 工具 | 對到什麼 |
   |---|---|
   | `read_evidence` | 它讀的那一筆 `ev-`，標「讀過全文」 |
   | `search_evidence` | 它回傳的那幾筆 `ev-`，標「只看到摘要」 |
   | `get_financial_snapshot` | 快照實際回傳的季別（最新一季＋TTM 四季）、source_id、content_hash |
   | `get_price_window` | 回傳的交易日 |
   | `get_macro_snapshot` | 回傳的總經列（series、日期） |
   | `calculate_metrics` | 往回追輸入：每個數值輸入都必須出現在同一個 job 更早的工具結果裡，才跟著對到那些 obs 的來源；任何一個找不到，就標「計算結果，輸入未驗證」，不算有來源 |
   | 工具沒有成功（no_data、refused…） | 不算來源 |

3. **對出來的 `ev-` 照現有規則檢查**：片段要在快照裡，hash 要相符。財報三檔組合 hash 那一半不變。
4. **對應表存進發布版本**：存在 `data.obs_map` 與 `data.sources`，所以來源抽屜顯示的是「obs-1 → ev-fwd3-…（只看到摘要、hash 吻合、cutoff 前可得）」這種實際對應，之後可以重查。

**「來源可追溯」的引用片段那一半**（`research_ui/obs_trace.claim_trace`）：

| 情況 | 判定 |
|---|---|
| 引用的 `ev-` 不在快照中 | missing（原規則，文字不變） |
| 引用的 `ev-` hash 不符 | conflict（原規則，文字不變） |
| 引用的 obs 對不到任何通過規則的片段，也對不到快照資料 | **missing**（缺來源） |
| 事實主張（kind = fact）沒有引用任何來源 | **missing**；推論與未知類可以不引用 |
| 引用了 obs，但這個 job 的紀錄（checkpoint）拿不到 | not_run，畫面寫「無法判定」。只有這一種情況用這個寫法 |

原本註解寫「主張沒引用任何片段也算通過」（also when nothing is cited）。現在這條只用在比較面板，因為比較面板檢查的是 B 同業快照列出的片段；報告一律改走上面的規則。

## 三、改了哪些檔

| 檔案 | 內容 |
|---|---|
| `research_ui/obs_trace.py`（新） | obs 對應與引用規則 |
| `research_ui/report_data.py` | 報告資料呼叫上面的規則；`data.obs_map`；`report-data-v1.5` |
| `research_ui/comparison.py` | `evidence_half` 參數：報告用自己的檢查結果 |
| `research_ui/__init__.py` | 來源抽屜可以開 obs，以及 obs 對到的片段 |
| `static/research.js`、`static/research.css` | 抽屜裡的「obs → 實際查到的來源」 |
| `research_ui/report_pdf.py` | PDF 來源段落同樣列出對應 |
| `scripts/obs_trace_check.py`（新） | 組長端讀 job 資料庫，印出某一批的對應結果 |
| `tests/test_obs_trace.py`（新） | 測試 11 項 |

**沒有改的**：

- `agents/publication.py`：發布時傳進來的 job 本來就帶 checkpoint（`agents/api.py` 用 `store.get_job`）。
- 第二段鎖定的 14 個檔、`data/`、`fixtures/`、`evaluation/`：都沒有動。

## 四、驗證

- **兩份已發布的 Agent v1 報告判定沒有變**：第 1 批 2317 `rv-2ed6652e`、第 2 批 2330 `rv-db6b0e1b`。
  - 用同一份草稿，分別以 main 11d8a5e 與本分支產生報告資料。除了 `data_version` 這個欄位以外，整份 JSON 逐字相同。
  - 和 Render 上已發布的內容對照也一致：資料品質風險「低」，11 項檢查全部 pass，來源 1 筆（2317）、2 筆（2330），都已解析、hash 相符。
  - 這兩份的事實主張都有引用 `ev-`，沒有引用 obs，所以報告 JSON 也不會多出 `obs_map`。
- 全套 `pytest`：**512 passed**（main 為 501，本分支新增 11 項）。
- 本機用合成的工具紀錄建了一份預覽報告，確認網頁抽屜、手機版和 PDF 都能顯示對應。合成資料只用來檢查畫面，不是第 3 批的結果，也沒有放進 repo。

## 五、第 3 批的實際對應：要在組長 Mac 上跑

第 3 批的 checkpoint 只在組長 Mac 的 `tmp/forward_batch3.sqlite3`，repo 裡的 `research/forward-batch-3-reports.json` 只有工具名稱和狀態。A 這邊沒有那份資料，所以**沒有自己產生第 3 批的對應結果**。

請組長在 Mac 上合併本分支後執行：

```
python scripts/obs_trace_check.py --batch 3
```

- 只讀資料庫（mode=ro），不呼叫模型，只寫 `tmp/forward-batch-3-obs-trace.json`。
- 會印出 2317、2454 每個 obs 對到什麼，以及「來源可追溯」的判定。
- 2330 停在證據不足、沒有可發布的草稿，會略過。

結果交給 B，由 B 對照稽核檔第五節逐條核對。
