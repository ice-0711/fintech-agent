# Agent 版本變更紀錄（給報告第三、四章引用）

正式實驗必須說清楚每一批結果是用哪個版本跑的。這裡只記會影響 Agent 行為的變更；文件與網站的修改不列入。

## 版本一覽

| 版本 | 期間 | Researcher prompt | Reviewer prompt | 單次輸入上限 | 每 job token 上限 | 用在哪些結果 |
|---|---|---|---|---|---|---|
| v1（校準版） | 10/26–11/06 | researcher-v1.2.2 | reviewer-v1.2.1（10/31 起） | 3,000 | 40,000 | 三模式校準 v1（開發集 30 列）、前瞻第 1、2 批 |
| v2（W09 修正版） | 11/06 起（11/07 再修覆核規則；11/10 補 next_signals） | researcher-v1.2.3 → researcher-v1.2.4（11/10）→ **researcher-v1.2.5**（11/11） | **reviewer-v1.2.2**（11/07） | **6,000** | **64,000** | W09 開發集 dual 重跑、W09 鎖定後的正式實驗（保留集 60 次）、前瞻第 3 批 |

以下不變：每 job 最多 8 次模型發送、10 次工具呼叫、2 輪補查；單次輸出 1,500 token（含 thinking）；模型 `gemini-3.5-flash-lite`；thinking `minimal`；初次研究最多 4 次發送（dual）。

## v1 → v2 改了什麼、為什麼（組長 2026-11-06 決定）

**依據**：三模式校準 v1（D 評分、B 交叉評分，`handoff/W06-gate-v12.md` 第 9 節）。dual 有 6/10 案停在證據不足，其中兩案（CASE-04、CASE-19）的案例設定不允許選證據不足；停止理由也常和執行紀錄對不上。查程式後發現原因有兩種（`handoff/W09-researcher-fix-proposal.md`）：

1. **系統限制沒有清楚告訴模型**：輸入接近 3,000 token 時，舊的工具結果會被壓成 160 字摘要，模型看到的確實是截斷的資料（S18）；工具因研究次數或輸入上限被關閉時，模型只知道「不能再呼叫工具」，不知道原因（S20）。
2. **模型編造停止理由**：在沒有發生的情況下寫「價格工具無資料」「read_evidence 逾時」（S30、S17、S27）。

| # | 變更 | 位置 | 對應問題 |
|---|---|---|---|
| 1 | **單次輸入上限 3,000 → 6,000 token、每 job token 上限 40,000 → 64,000** | `agents/budget.py` | 減少工具結果被壓縮，Agent 較不會因看不到資料而放棄（原因 1） |
| 2 | 停止原因由程式依執行紀錄產生（`stop_facts` 事件：哪些工具回什麼、工具為何關閉、是否壓縮、用了幾次預算） | `agents/research_graph.py` | 給人看的停止原因不再依賴模型自述（原因 2） |
| 3 | 覆核規則新增：草稿提到「無資料、逾時、截斷、無法呼叫工具」，但執行紀錄沒有，列 critical | `agents/review_checks.py` `unsupported_system_claims` | 編造的停止理由不能通過覆核（原因 2） |
| 4 | 被壓縮的工具結果加註「需要原數字請重新呼叫同一工具」；工具關閉時告知原因，並要求依現有證據完成草稿、缺的列 unknown | `agents/research_graph.py` | 原因 1 |
| 5 | Researcher prompt 加一句：摘要只寫缺少哪些證據，不描述工具或系統事件 | `agents/prompts/researcher-v1.2.txt`（版本 researcher-v1.2.3） | 原因 2 |

**用校準 v1 的草稿離線驗證第 3 項**：S30（CASE-04）、S17／S27（CASE-26）都會被抓到；覆核通過的 CASE-01、11、22 沒有被誤擋；CASE-15 的「快照截斷」因確實發生過壓縮而不標記。

## v2 的 11/07 補修（組長 11/07 決定）

v2 重跑第 2 天（11/07）發現 4 案未通過中，有 2 案主要是覆核規則的 bug，把正確內容判錯：

| # | 變更 | 位置 | 案例 |
|---|---|---|---|
| 6 | unknown 主張引用 no_data 的工具結果不再列 critical（那是「查過、確實沒有」的證據）；fact／inference 引用 no_data 仍列 critical | `agents/review_checks.py` | CASE-15、CASE-26 |
| 7 | 數字比對接受「40.0」「40.00」這類整數加小數零的寫法 | `agents/review_checks.py` `num_variants` | CASE-19 |
| 8 | Reviewer prompt：obs 結果已附在覆核資料中，read_evidence 只讀 ev- 來源編號（避免浪費一次發送） | `agents/prompts/reviewer-v1.2.txt`（reviewer-v1.2.2） | CASE-15、CASE-26 |

開發集重跑中，CASE-01、04、08（11/06）與 CASE-11、18、22（11/07）用的是補修前的規則；這三項只會造成「誤判錯」，不會讓錯的內容通過，所以這 6 案的結果不受影響。受影響的 CASE-15、19、26 於 11/08 用補修後版本重跑，以 11/08 的結果為準。

**仍未解決（寫進限制）**：CASE-19（數字口徑，不允許選證據不足）Researcher 遇到幣別混用仍自行放棄，沒有改正或填 null。

## 對研究問題與結果的影響（寫報告時要說明）

- **「有限預算」的定義改變**：輸入上限放寬一倍。仍是免費方案、每 job 仍最多 8 次模型發送；額度用量的主要限制（每日 J＝6、RPD 500）不變。報告中預算的描述一律寫 v2 的數字，並註明 v1 曾用 3,000。
- **校準 v1 與正式實驗不是同一版本**：校準 v1 用來找問題、決定修正；正式實驗只用 v2。兩者的數字不可放在同一張表比較，要比較時須標明版本。
- **前瞻報告跨兩個版本**：第 1、2 批是 v1，第 3 批是 v2。前瞻不計方向命中（方向一律 none），報告中逐份標示版本。
- **修正後結果可能沒有變好**：若 v2 重跑仍常停在證據不足，照實記錄，不再為了結果繼續調整（W09 鎖定）。

## v2 的 11/10 補修（組長 11/10 決定）

D 的 v2 dual 開發集評分（`evaluation/d-drafts/calib-v2-scores-D.txt`，PR #37）：CASE-15、CASE-18 沒有補造數字、有說明不足，但 `next_signals` 是空的，少了案例預期的「下一確認訊號」。查 prompt 發現輸出格式有這個欄位，卻沒有任何一句要求填寫——是規格漏寫，不是依結果調模型。

| # | 變更 | 位置 | 案例 |
|---|---|---|---|
| 9 | Researcher prompt：回 insufficient 時，next_signals 寫 1 至 3 個之後可補上缺口的確認訊號，只寫訊號不寫結論 | `agents/prompts/researcher-v1.2.txt`（researcher-v1.2.4） | CASE-15、CASE-18 |

版本標示：11/09 single 煙霧測試第 1 天用 researcher-v1.2.3；11/10 起的煙霧測試、11/12 CASE-15、18 dual 重跑、W10 正式實驗與前瞻第 3 批用 researcher-v1.2.4。D 的 v2 dual 評分屬 v1.2.3，引用時標明。


## v2 的 11/11 補修：股價快照兩種格式（組長 11/11 決定）

不是 prompt 或判斷邏輯的變更，prompt 版本不變（researcher-v1.2.4、reviewer-v1.2.2）。案例快照的 `price_snapshot` 有兩種格式（`scripts/check_cases.py` 兩種都檢查）：單筆收盤價在最外層，或 `closes` 清單、每筆各有 `available_at`。`agents/snapshot.py` 只讀得懂第一種，遇到第二種會丟 KeyError，被包成 `tool_error`。

| # | 變更 | 位置 |
|---|---|---|
| 10 | `get_price_window` 兩種格式都讀，照每筆 `available_at` 與 cutoff 過濾；沒有 `available_at` 的價格不用，回 `no_data` | `agents/snapshot.py`（`price_rows`） |
| 11 | P/E 輸入核對：`closes` 格式時，價格須等於清單中任一筆收盤價；快照有 `eps_ttm` 才核對 EPS | `agents/review_checks.py` |

測試 `tests/test_snapshot_price_formats.py`（合成資料）。開發集 10 案行為不變（都是第一種格式或沒有股價）。

## v2 的 11/11 資料變更：補齊歷史股價（組長 11/11 決定，決策 25）

prompt 與判斷邏輯不變（researcher-v1.2.4、reviewer-v1.2.2），但 Agent 查得到的資料變了，結果要分開標示。

| # | 變更 | 位置 |
|---|---|---|
| 12 | 全域股價由 cutoff 前 5 個交易日補為 2025-01-02 至 2026-09-30 全部交易日（未還原收盤價；逐日與 TWSE 對帳相符）。可得時間規則不變（交易日 17:30），案例 cutoff 之後的價格不給 | `data/financial-snapshots.json`（v1.7-price-history）、`scripts/extend_price_history.py` |
| 13 | `get_price_window` 的 content_hash 指向涵蓋該視窗日期的原始檔 | `agents/tools_impl.py`（`_raw_file_covering`） |

補之前，cutoff 在 7、8 月的案例 `get_price_window` 一律回 `no_data`，估值段落多寫未知；補之後可取得 cutoff 前的收盤價。

版本標示：校準 v1、v2 開發集 dual 重跑（11/06–11/08）、D 的 v2 dual 評分、煙霧測試第 1–3 天（11/09–11/11）是**補股價前**；11/12 起的煙霧測試、開發集 dual 重跑、W10 正式實驗與前瞻第 3 批是**補股價後**。兩者不放同一張表。第一段凍結以修訂方式記錄（`data-freeze.md` 第八節）。

## v2 的 11/11 補修：來源衝突的處理（組長 11/11 決定，決策 26）

D 的 v2 dual 評分與煙霧測試第 3 天：CASE-19（幣別混用，不允許停在證據不足）在 dual 把兩個數字都保留並加警告，在 workflow 直接回證據不足。查 prompt：只寫「數字互相衝突時先核對期間、幣別與單位」，沒寫核對後仍無法確定時該怎麼做——是規格漏寫。補的是通用規則，不含任何案例的數字或答案。

| # | 變更 | 位置 |
|---|---|---|
| 14 | Researcher prompt：來源的幣別、單位或口徑不一致且核對後無法確定時，不換算、不擇一當事實；有官方來源以官方為準，其餘改列 unknown 並在 conflicts 寫明；其他有來源的觀察照常寫成 draft，不因單一衝突回 insufficient | `agents/prompts/researcher-v1.2.txt`（researcher-v1.2.5） |

版本標示：11/12 起的煙霧測試第 4 天、開發集補股價後 dual 重跑、W10 正式實驗與前瞻第 3 批用 researcher-v1.2.5。11/10–11/11 的煙霧測試（第 2、3 天）是 v1.2.4。此後除非出現程式錯誤，鎖定前不再改 prompt。

## v2 的 11/11 補修：price_snapshot 的 synthetic_adjusted 欄位（組長 11/11 決定，決策 27）

prompt 版本不變（researcher-v1.2.5、reviewer-v1.2.2）。

| # | 變更 | 位置 |
|---|---|---|
| 15 | 案例快照的 `price_snapshot` 有 `synthetic_adjusted` 欄位時，`get_price_window` 照原樣放進回傳的 `data`，不加說明、不改寫；沒有該欄位的案例回傳不變 | `agents/snapshot.py` |

依據：出題組員（B）11/11 確認此欄位出題時就是要給 Agent 看的，工具原本漏傳。開發集沒有這個欄位，10 案行為不變。測試 `tests/test_snapshot_price_formats.py`（合成資料）。

## v2 的 11/12 補修：覆核規則（組長 11/12 決定，決策 28）

prompt 版本不變（researcher-v1.2.5、reviewer-v1.2.2），只改覆核程式。

| # | 變更 | 位置 | 案例 |
|---|---|---|---|
| 16 | 「TTM 要四個連續單季」：pe_ttm 的期間是股價日期，本身沒寫季度時改看草稿 eps_ttm 或快照的 TTM 季度；不連續或找不到仍列 critical | `agents/review_checks.py`（`eps_ttm_quarters`） | CASE-04（算對卻被擋） |
| 17 | 新增 minor 提醒：已取得股價卻沒有估值或本益比、沒有總經觀察。只提醒，不改變放行結果；Researcher 回 insufficient 時不加 | `agents/review_checks.py`（`coverage_notes`） | CASE-01 |

第 16 項只會讓「算對卻被誤擋」的結果通過，不會讓季度錯誤的結果通過。第 17 項不影響任何案例的覆核結果，但覆核紀錄會多出 minor 項目。

版本標示：11/12 開發集 CASE-01、04 dual 結果是修正前規則；11/13 起的開發集重跑、W10 正式實驗與前瞻第 3 批用修正後規則。測試 `tests/test_review_pe_coverage.py`（合成資料）。
