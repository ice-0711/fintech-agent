# V1.2 實驗版本鎖定（W09-L）

- 鎖定時間：2026-11-15 19:32:19（台北）｜鎖定人：組長｜指令：`python scripts/build_freeze.py --lock-agent`
- 核對：`python scripts/build_freeze.py --verify --strict` 通過（凍結紀錄一致，cases-v1，cases_digest 98af84030d45）
- 機器可讀版本：`release/eval-version.json`（含每個檔的完整 hash）
- 用途：W10／W11 正式評估 `formal-v2`，保留集 20 案 × 3 模式 = 60 run，2026-11-16 至 11-25 每天 19:30 執行 6 個

## 一、鎖了什麼

第二段共 14 個檔。之後任何一個檔的內容改變，`--verify --strict` 就不通過，`scripts/formal_runs.py --live` 會拒絕執行。

| 檔案 | sha256（前 12 碼） |
|---|---|
| `agents/tools.py` | bf3a3e807f4c |
| `agents/snapshot.py` | fc9c844af513 |
| `agents/contract.py` | c7e093ef481e |
| `agents/review_checks.py` | a5179ac6c1ae |
| `agents/review_contract.py` | d2abcbf19fa4 |
| `agents/research_graph.py` | 9dfa5936879e |
| `agents/provider.py` | 2aa8dca02488 |
| `agents/budget.py` | 2360a38d7ed9 |
| `agents/store.py` | 1e2e38df8b1e |
| `agents/worker.py` | 77e620ca524d |
| `scripts/dev_traces.py` | c1bd92f81b21 |
| `scripts/formal_runs.py` | 2dab4fc4be57 |
| `agents/prompts/researcher-v1.2.txt` | 795da03d0a11 |
| `agents/prompts/reviewer-v1.2.txt` | a42c3338a07a |

- 兩支 runner 是 11/14 補列的：送什麼題目給 Agent、讀封存檔的哪些欄位，由它們決定（決策第 31、38 節）。
- 第一段（案例、資料、B 的工具、評分規則、人工檔）已於 2026-10-25 凍結，之後有修訂 1（11/11，補齊歷史股價）與修訂 2（11/13，2454 負債覆寫，B 11/14 複核通過）；案例與 cases_digest 沒有變。
- commit：鎖定前的 main 是 503b8be；被鎖定的檔案最後一次修改在 ddb20c2（11/14）。鎖定的 commit 只更新凍結紀錄並新增本檔與版本檔。

## 二、版本與上限

| 項目 | 值 |
|---|---|
| 模型 | gemini-3.5-flash-lite，thinking minimal，temperature 0 |
| Researcher prompt | researcher-v1.2.5 |
| Reviewer prompt | reviewer-v1.2.2 |
| 每個 job | 最多 8 次模型發送（dual 的 Researcher 第一輪 4 次）、10 次工具、2 輪補查、180 秒主動時間 |
| token | 單次輸入上限 6,000、單次輸出上限 1,500、每 job 64,000 |
| 每配額日 | J = 6 個 job（太平洋時間日期，台北 16:00 重置） |
| 執行計畫 | `evaluation/run-plan.json`，固定種子 20261116，同案三模式連續、起始模式輪替 |

## 三、送給 Agent 的輸入（決策第 31 節）

- 研究焦點是案例的 `task`（題目，一字不改）。
- 快照若有 `task_input`、`draft_under_review`，以同名欄位原樣附上；single、dual（Researcher 與 Reviewer）、workflow 都有。
- 不送：`variant`、`category`、`expected_behavior`、`expected_*`、`allow_insufficient`、`perturbation_location`、`required_elements`（最後一項只給評分者）。
- 三個模式的輸入相同，差別只在誰決定用哪些工具、有沒有覆核。

## 四、Agent v2 的內容

完整清單見 `handoff/agent-version-changes.md` 第 1 至 24 項。11/11 之後的項目：

| 項 | 日期 | 內容 | 決策 |
|---|---|---|---|
| 14 | 11/11 | Researcher 補「來源衝突無法確定時列 unknown」（researcher-v1.2.5） | 26 |
| 15 | 11/11 | get_price_window 回傳 synthetic_adjusted | 27 |
| 16、17 | 11/12 | P/E 的 TTM 季度改看所用的 TTM EPS；查到卻沒寫的 minor 提醒 | 28 |
| 18、19 | 11/13 | 題目改送 task；task_input、draft_under_review 原樣附上 | 31 |
| 20 | 11/14 | TTM EPS 的期間只寫結尾季且數值相符時，視為那四季 | 35 |
| 21–23 | 11/14 | 覆核用的財報資料改為該 job 的工具實際回傳的內容；P/E 寫結尾季比照處理 | 37 |
| 24 | 11/14 | P/E 沒附計算輸入時，數值必須出現在該 job 的某個工具結果裡 | 38 |

11/13 之後的修改都只動程式，prompt 自 11/11 起沒有改。這些修改都沒有依據保留集的內容；保留集只做過數量與狀態的統計（決策第 30、36 節，含 11/13 一次搜尋時印出片段的接觸紀錄）。

## 五、鎖定前做過的驗證

| 驗證 | 結果 | 決策 |
|---|---|---|
| 開發集預演（送 task，4 dual + 2 workflow，live） | 無程式錯誤；CASE-04 被規則誤擋 → 修正 | 35 |
| 保留集無模型試跑（180 次，只看數量與狀態） | 0 例外；題目與附加欄位送達正確；輸入最大 4,472 token | 36、37 |
| 已存 36 份 v2 草稿修改前後比對（開發集與前瞻） | 決策 37 改變 1 份（CASE-15 由被擋改為通過）；決策 38 改變 0 份 | 37、38 |
| 封存檔 hash、外洩掃描（406 個檔） | hash 一致；題目、預期主張、附加欄位 0 筆 | 36 |
| 排程權限測試 | 無人值守執行 `formal_runs.py --status`，沒有等待核准 | 40 |
| 鎖定前 live 驗證（4 dual，修正後規則） | CASE-04、01 通過；CASE-15 證據不足（允許）；CASE-22 證據不足（模型三次都用在搜尋） | 40 |
| 全部測試 | 501 個通過 | — |

## 六、已知限制（報告須照實寫）

1. **三條規則路徑只有離線測試**：「TTM EPS 只寫結尾季」「本益比寫結尾季」「財報工具回 no_data」在 11/15 的 live 驗證中沒有出現。
2. **本益比規則只查數值來源，不查計算輸入**：數值是工具算出來的就通過，不檢查用的是哪一天的股價、哪一種 EPS。前瞻第 3 批 2317 的本益比用了 11/11 而非 11/13 的收盤價，覆核沒有發現（B 11/14 稽核，`research/forward-batch-3-audit.md`）。
3. **輸出被截斷會記成證據不足**：單次輸出達 1,500 token 上限時，草稿不是完整 JSON，程式記為 `insufficient_evidence`／`researcher_insufficient`。前瞻第 3 批 2330 發生一次（B 稽核同樣記錄「原因是輸出格式，不是證據不足」）。停止代碼沒有分開標示。
4. **逾時處理沒有 live 驗證**：30 案中沒有任何一案會在 live 觸發 read_evidence 逾時（CASE-26 的逾時對象搜尋不到），只有離線測試為證。
5. **保留集預期答案寫於補股價之前**（決策第 25 節）：Agent 可能寫出預期答案沒有涵蓋的估值主張，盲評照評分規則。
6. **dual 的 Researcher 第一輪只有 3 個工具回合**；案例快照的搜尋不論查詢字串都回同一組來源，重複搜尋會把回合用完（11/15 CASE-22）。這是設計的一部分，三模式比較會反映。
7. **排程沒有緩衝**：10 天剛好 60 run。任何一天沒跑，剩下的由組長決定何時手動補跑。
8. **模型每次執行的做法不完全相同**：同一題 11/14 通過、11/15 證據不足（CASE-22）。每個 run 只跑一次，不重跑挑結果。

## 七、鎖定後的規則

- 到 60 個 run 跑完之前，下列檔案不修改、不搬動、不改名：第一節的 14 個檔、`data/`、`fixtures/`、案例檔（`evaluation/dev-cases.json`、封存檔、`evaluation/cases_manifest_v1.json`）、評分規則、B 的工具程式、`evaluation/run-plan.json`。
- 真的必須修改（例如程式錯誤使實驗無法執行）：由組長決定，記入決策紀錄，改用新的實驗版本代號；已跑的 run 保留、不覆蓋。
- 不重跑已記錄的 run；失敗、逾時、證據不足都照實留在 `evaluation/formal/runs-v2.jsonl`。
- 保留集內容仍不可讀：正式 run 的草稿與覆核只存在組長 Mac 的 `tmp/formal_v2.sqlite3`，60 run 跑完後由 `scripts/export_for_scoring.py` 匿名匯出給 B、D 盲評。
- 其他檔案（`research_ui/`、`static/`、`design/`、`media/`、`demo/`、`docs/`、`slides/`、`tests/`）可以照常修改。

## 八、W09-L 驗收對照

| 驗收條件 | 狀況 |
|---|---|
| 不改保留測試答案 | 封存檔 hash 與 `fixtures/test/SEAL.json`、`evaluation/cases_manifest_v1.json` 一致（決策第 36 節） |
| 版本含 hash | 本檔第一節與 `release/eval-version.json` |
| 無未核准新功能 | 11/11 之後的每項修改都有組長決定與決策編號（第四節） |
| 沒有混合模型／工具版本成績 | v1 與 v2 分開；送變體名稱與送 task 分開；規則修正前後分開（`release/eval-version.json` 的 result_labels） |
| 9 份前瞻資料按規約留存 | 三批都已凍結並研究；B 的總表（11/15 推上 main）：9 列，通過覆核 4、證據不足 5、已發布 2（`research/forward-manifest-9.json`） |

手冊交付物 `research/batch-3.json` 在本專案的檔名是 `research/forward-batch-3.json`。
