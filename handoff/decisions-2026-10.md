# 組長核定事項（2026-10-21）

來源：組員 B 提出的「需要組長核定的事項」清單。組長於 2026-10-21 回覆「照建議」核定下列各項。

## 一、估值與 DCF

| 項目 | 核定 | 備註 |
|---|---|---|
| WACC | **9%**，全專案統一 | 與 `main.py`、手冊第 02 章一致；`valuation_agent/dcf_model.py` 預設已由 10% 改為 9%。報告標註「程式預設，非個股風險估計」。B 的 `data-contract.md` 第 229 行（WACC 10%、內在價值 853.27 元）需以 9% 重算 |
| 終端成長率 g | 3% | 程式強制 WACC > g |
| FCF 預測 | 基準情境：5 年持平於基期 TTM FCF；成長率情境列入敏感度 | 終端價值占比高，敏感度必須呈現 |
| DCF 公式 | 以 `dcf_model.py` 為專案標準：終端價值 = 第 5 年 FCF ×(1+g)/(WACC−g)，折現 5 年 | |
| 估值差距 ±15% | 保留（手冊 F03 規定） | 介面註明「專題顯示門檻，非經驗證投資規則」；缺關鍵參數顯示「無法判定」 |

## 二、資料口徑

| 項目 | 核定 |
|---|---|
| Supabase 路徑應付短期票券 | 採選項 (a)：年度 DCF 不計入，文件註明差異（2317 約 934.59 億） |
| 租賃負債 | 不計入淨負債，文件註明（非 IFRS 16 口徑） |
| shares_outstanding | 流通在外股數 = 發行股數 − 庫藏股（需通知 A、D） |
| BVPS | 歸屬母公司權益 ÷ 流通在外股數 |
| 單季 EPS 來源 | 2025Q4 採 FinMind 單季值（經全年減 1–9 月驗證），標籤 `finmind_quarterly` 為正式規則 |
| 淨負債缺值 | 不得以 0 代替；DCF 每股價值顯示「無法判定」（`main.py` 已修正，commit 3292570） |

## 三、測試與案例

| 項目 | 核定 |
|---|---|
| 開發案例 | 以 dev-cases.json **v1.5**（v1.5-w04，CASE-08 依手冊附表為 2317）為準；10/21、10/22 的 live 皆在 v1.5 上執行（檔名 dev-v14-* 為命名誤植，2026-10-22 更正） |
| CASE-11 | 採選項二：測試口徑識別，不寫個體數字 |
| 保留集 | 20 個快照已在 `fixtures/test/`，SEAL.json 三個檔案 hash 皆相符（2026-10-21 驗證）。是否殘留舊假數字由 B 或 D 確認；組長不讀保留集內容 |
| 股價 available_at | **全專案統一 17:30**（收盤後資料可得的推定時間）。原記錄「14:30 較保守」有誤：14:30 早於 17:30，反而較不保守（B 指正，2026-10-22 更正）；兩者皆早於 30 案 cutoff，不影響案例 |
| 表格整理段落 | 接受 `paragraph_type` 為「MOPS 表格數值整理」，數字須與原表逐字一致 |

## 四、程式與系統

| 項目 | 狀態 |
|---|---|
| CASE-15 正文不可讀 | 已修：回傳 `status: "unreadable"`（與 B 的 tools_impl 同格式） |
| CASE-26 工具逾時模擬 | 已修：快照層讀取 `tool_simulation`，並套用 B 的 15 秒逾時；工具時間計入 180 秒上限 |
| `fundamental_uploader.py` | 目前為 insert（非 upsert），重跑會重複。待 Supabase 測試專案確認 `(stock_code, year)` 唯一索引後改為 upsert |
| `report_downloader.py` 部署 | 排在 W08 部署驗收，先在測試專案驗證 |

## 五、2026-10-22 追加核定

| 項目 | 核定 |
|---|---|
| F06 2D 關聯圖 | **延後**，轉後續版本（理由見 W06-gate-v12.md 第 4 節）；N06 不驗收 |
| 2317 FCF 正常化情境 | **不做**；2317 基準情境維持「TTM FCF 為負，DCF 無法判定」 |

## 六、2026-10-23 核定

| 項目 | 核定 |
|---|---|
| model | 維持 `gemini-3.5-flash-lite` |
| 凍結 | 10/23 凍結案例／資料／評分規則；prompt 與 Agent 程式 10/26 live 再驗一次後鎖定（W09 前） |
| 備案 | Reviewer 仍無法完成覆核時，thinking_level minimal → low，只用開發集驗證 |

## 七、2026-10-24 核定（回覆 B 10/24 待決事項）

| 項目 | 核定 |
|---|---|
| 第一段凍結（案例、資料、B 工具、D 評分規則） | **可以凍結**。B 重新產生凍結紀錄，D 簽核後組長在 `data-freeze.md` 第七節簽核。第二段檔案清單維持 B 所列 |
| CASE-26 測不到逾時 | 不改快照（避免 cases-v2）；結果註明「此案未觸發逾時」，逾時處理以離線測試為證 |
| 覆核規則 basis_unspecified | 採用（來源 basis = unspecified 時列 critical）；10/26 與 workflow 模式一起合併，三模式校準開跑前生效 |
| CR-W06 保留集防護（`agents/snapshot.py`） | 10/26 合併（不等 W10），連同 B 的測試檔 |
| Supabase 寫入方式（data-contract 待決第 4 項） | 加 `(stock_code, year)` 唯一索引，改為資料庫層級 upsert；W07 先在 Supabase 測試專案上做，不動正式庫 |
| 年度 PER 來源（data-contract 待決第 12 項） | 保留；輸出標明「年度 PER（12/31 股價 ÷ 年度 EPS）」，不得與 F02 P/E 直接比較 |
| `tests/fixtures/agent_case_fixtures.json` snap-dev-case-01 | 改標 `synthetic_fixture: true`（6,735 億為早期合成數字） |


## 八、2026-10-29 核定

| 項目 | 核定 |
|---|---|
| 覆核規則：數字必須出現在引用來源（B 10/28 提出） | 採用。事實主張的數字若引用財報快照（`snap-…`）、工具結果（`obs-…`），或未填 source_ref，也要在快照工具數值、工具結果或引用原文中找得到，否則列 critical；允許常見單位換算（千元／萬／億／百分比）與依主張位數的四捨五入。算出來的數字（ytd 還原、有 operation／derived_inputs、P/E）由原有重算規則檢查。屬第二段（`agents/review_checks.py`、`agents/snapshot.py`），10/29 16:30 校準第 2 天前生效；第 1 天 dual 於第 6 天重跑，故校準的 dual 全部使用同一套規則 |
| 前瞻方向命中：零報酬（D 10/29 請登記） | 觀察期報酬恰為 0 記 `zero_return`，不計入方向命中率的分子與分母；報告另列筆數並註明「零報酬不判方向」。與 `scripts/forward_eval.py` 現行做法一致 |

## 9. 2026-10-31 組長決定：dual 誤擋的兩個修正

依校準第 2、4 天結果（本段程式修改，第 5 天起生效，Reviewer prompt 升為 `reviewer-v1.2.1`）：

- **TTM 季度判定（CASE-22）**：`quarters` 沒填時改讀 `period`，四季清單或 `2025Q3-2026Q2` 起訖都可判定；仍必須剛好連續四季，數字仍要對得上工具結果。凍結資料與 B 的工具都沒有改。
- **可得時間比對（CASE-11）**：`available_at`／`captured_at` 與 `cutoff_at` 的先後改由程式比對，prompt 要求模型不自行比較。模型若仍列時間問題，而引用來源經程式確認都在 cutoff 前可得，該問題移除，並記 `timing_issue_refuted` 事件（含模型原判與原文）供評分查核；若因此沒有其他 critical，模型結論改為 pass，最終仍由規則把關。
- **校準影響**：第 1–4 天的 dual 是舊規則、舊 prompt，與第 5 天起不可直接比較；重跑範圍由組長決定。

## 10. 2026-10-31 組長決定：J=6 單次例外

組長核定，太平洋時間 2026-10-31 這一個額度日的校準 job 上限開到 20（已跑 6 + 第 5 天 6 + 舊版 dual 重跑 8），由 `dev_traces.py --j-exception 20 --j-exception-day 2026-10-31` 明確指定，其他日期仍是 J=6。每個 job 的預算、80% RPD／RPM／TPM 限制、模型與規則都不變。前瞻研究 3 個 job 存在獨立的 `tmp/forward_batch1.sqlite3`，讓 D 的校準匯出只含開發案例。

實際執行（2026-10-31，台北）：前瞻 3 個（19:17）、第 5 天 6 個（19:23）、dual 重跑 8 個（22:09 完成）。重跑第一次卡在 mock 階段：mock 的 quota 沒帶例外，第 7 案被 J=6 暫停，當時尚未送出任何真實請求；停掉後拆成 6＋2 兩批重跑，輸出為 `agent/calib-v1-dual-rerun-1.json`、`-2.json`。mock 階段已修正。校準比較的 dual 一律用重跑結果；`dev-runs-calib-v1.jsonl` 仍保留舊 dual，以 started_at／repo_commit 排除。

## 11. 2026-11-02 組長決定：回覆 B 的 W08 待決事項

- **中文金額單位（CR-W08，`docs/CR-W08-review-chinese-amounts.md`）**：採用。`agents/review_checks.py` 新增 `chinese_amounts()`，原文的「5,118億5,700萬元」這類寫法換算後相符即算來源支持；引用證據的數字池也納入換算值。寫錯的數字仍判 not_supported。測試 `tests/test_review_chinese_amounts.py`。屬第二段，W09 鎖定時一併鎖定。
- **來源衝突只比同單位**：`find_conflicts()` 只比較同單位（億對億、% 對 %）。月營收與季營收單位相同仍會列出，維持 minor、不擋。
- **影響範圍**：~~B 掃描過，開發集 10 案的證據沒有中文單位金額~~（**11/05 B 更正**：當時的掃描不接受數字與單位間的空格，漏掉 CASE-08 二手摘要的「2 兆 2,558.94 億元」；11/06 已改為允許空格）。校準結果仍不受影響：CASE-08 single 不經覆核，dual 的 c2 是 unknown、沒有數值。保留集由 B 用修正後的版本再掃一次。以新規則重放前瞻第 1 批草稿：2330 規則判定 insufficient → pass；2454 insufficient → pass（只剩月營收與季營收的 minor）；2317 不變。
- **前瞻第 1 批不重跑**：照手冊「資料不足照收錄」，以現有結果記錄。中文金額誤判、2454 Researcher 只搜尋一次未讀第三季證據，兩點寫進限制。
- **同業平均**：依手冊 F02「各自財報期與來源明示」，不同財報期的同業都計入（2454 比較組 n=2），表格逐列標財報季別，`periods_consistent = false` 時註明「同業財報期不同」。`research_ui/comparison.py` 已由組長端改（11/02，不再篩同財報期，`peer_stats.period_note`；PDF 同步加註），測試 `test_peer_stats_keep_peers_with_a_different_period`；請 A 核對網站呈現。
- **發布前容量 80% 檢查（`data/storage-and-safety-w08.md` 第六節）**：原則採用；門檻依 Supabase 實際方案訂，組長提供方案與用量後再實作，migration 先在測試專案演練。

## 12. 2026-11-02 組長決定：W08 部署

- **部署架構**：研究只在組長 Mac 跑（job 存 `tmp/*.sqlite3`）；Render 只做組長登入、核准、發布 PDF 與公開閱讀，不設 Gemini 金鑰與 `RESEARCH_API_TOKEN`。`research_jobs` 不搬 Supabase。詳見 `handoff/deployment-v1.md`。
- **Render 方案**：維持 Free（512 MB）。11/02 在 Free 上發布 1 份 PDF 成功；第二批發布若出現 `pdf_failed`（記憶體不足）再升級 1c-2g（US$25／月），屆時另行核准費用。
- **報告存放**：維持 Supabase 測試專案 `fintech-agent-test`（`report_versions`＋私有 bucket `reports`），正式專案不動。
- **備份**：每批發布後執行 `scripts/backup_reports.py export`，並另存一份到 iCloud Drive `fintech-agent-backups/`（11/02 首份已存）。
- **公開清單快取**：60 秒 TTL，一次查詢（commit f7014d1）。
- **Notion**：W01-L、W02-L、W06-L 改回「進行中」，與實際未完成項一致（W01 TPM 精確值；W02 job 遷移改為不搬、待記錄；W06 介面凍結紀錄與閘門文件）。

## 13. 2026-11-06 組長決定：校準 v1 簽核

- 簽核三模式校準 v1（W06-D）：D 評分 `evaluation/d-drafts/calib-v1-scores-D.txt`、B 交叉評分 `calib-v1-scores-B.md`，30 列標籤一致、53 個事實數值正確。S10、S15 備註中的「待組長裁決」以 11/03 裁決為準。
- W06 閘門定稿（`handoff/W06-gate-v12.md` 第 2、9 節）：N01–N03 ✅、N07 ✅（附限制）。
- W09 是否修正 Researcher：方案見 `handoff/W09-researcher-fix-proposal.md`，待組長決定。

## 14. 2026-11-06 組長決定：W09 Researcher 修正（Agent v2）

- 採 `handoff/W09-researcher-fix-proposal.md` 第三節 1–4：停止原因由程式依執行紀錄產生；覆核新增「草稿描述的工具事件須在執行紀錄中」；壓縮與工具關閉時告知模型；Researcher prompt 升為 researcher-v1.2.3。
- **放寬預算**：單次輸入上限 3,000 → 6,000 token、每 job token 上限 40,000 → 64,000。每 job 8 次發送、10 次工具、2 輪補查不變。**此改動須在報告中呈現**，版本對照見 `handoff/agent-version-changes.md`。
- 生效：11/06 第二批前瞻跑完後合併（第二批仍用 v1）；11/09–11/10 dual 開發集重跑，D、B 評分後 11/13 鎖定。

## 15. 2026-11-07 紀錄：CASE-13 與保留集揭露

- **CASE-13 結論（B，`evaluation/source-audit-final.md` 第一節第 3 點）**：保留集 CASE-13 與手冊附表、`data-freeze.md` 一致；10/15 以前出現的「CASE-13」（2317，缺 CapEx）是已廢除的舊開發草稿，與保留集無關。保留集未被污染。引用舊紀錄時標註「已廢除，與保留集無關」；網站 REPLAY 的舊 CASE-13 請 A 加註。
- **揭露**：上述稽核文件寫有保留集 CASE-13 的一行情境描述，組長端（Claude）11/07 查閱結論時讀到。讀到前 Agent v2 已完成且只用開發集驗證；之後不據此調整任何 prompt、規則或程式。請 B 從文件移除保留集內容，只留一致性結論。
- **排程**：第二批 21:10 的排程實際 21:39 才觸發（Mac 睡眠），與組長手動執行幾乎同時，由凍結腳本「不覆蓋」防護擋下重複。第三批 11/13 21:10 已排程；當晚 Mac 需保持清醒。

## 16. 2026-11-07 組長決定：v2 覆核規則補修

- 依 v2 重跑第 2 天：unknown 引用 no_data 不列 critical；數字比對接受「40.0」寫法；Reviewer prompt 升 reviewer-v1.2.2（不用 read_evidence 讀 obs）。詳見 `handoff/agent-version-changes.md`「v2 的 11/07 補修」。
- 11/08 重跑受影響的 CASE-15、19、26，並跑 CASE-29（共 4 個 job，J=6 內）；11/13 鎖定時程不變。CASE-19 的放棄行為不再修，寫進限制。

## 17. 2026-11-08 組長決定：fact sheet 保留集描述照原樣保留（選項 a）

- `data/v12-finance-fact-sheet.md` 第七節第 128、132 行寫了兩個保留案例各自測試的目的（題型層級，無答案、數字或來源內容）。此檔屬第一段凍結，**不修改、不重新凍結**，以本節揭露。
- 理由：題型分類本已公開（30 案總表）；保留集的有效性取決於未用於調整系統，Agent v2 只以開發集修正與驗證（第 14、16 節、`handoff/agent-version-changes.md`）。
- B 已於 11/08 從其餘共用文件移除保留集案例內容（`evaluation/source-audit-final.md`、`docs/CR-W05-holdout.md`、`docs/B-W01-W06-檔案說明.md`）。之後共用文件不得寫入保留集案例內容。

## 18. 2026-11-08 組長決定：鎖定前補做 single、workflow 的 v2 煙霧測試

- 原因：v2 改動（輸入上限、停止規則、Researcher prompt）三個模式共用，但 v2 重跑只驗了 dual。11/13 鎖定後不能再改，若 single 或 workflow 在 v2 有問題，W10 正式實驗才發現就只能整批記為失敗。
- 做法：用 11/09–11/12 空出的額度（原排 11/09–11/10 的 dual 重跑已於 11/06–11/08 提前完成），single、workflow 各跑開發集 10 案，共 20 個 job，每天 19:30 自動執行（J=6 內）。輸出 `agent/calib-v2-modes-day1..4*.json`。
- **由組長端自行執行與檢查，不交 D 評分、不需任何組員動作**；只確認不會出錯、停止理由與執行紀錄一致、必答案例（CASE-01、04、19、22）沒有停在證據不足。結果併入 11/12 的 v1／v2 比較。
- 更正：CASE-15 為 `allow_insufficient=True`，11/08 停在證據不足屬允許結果，不列為限制。
- 前瞻第三批維持 11/13 21:10：cutoff 21:00 已登錄在 `research/forward-batch-3-sources.json`，`freeze_forward_batch.py` 未到截止時間會拒絕執行。

## 19. 2026-11-08 組長決定：C 的文稿全部核准，取消「待核准」標示

- 合併 PR #30（C 依 Agent v2 更新預算數字並標示版本；B 11/08 轉達的三點已處理，組長端核對與程式值一致）。
- C 的 W01–W07 文稿（動機、RQ、文獻、引用、方法各節、第三章、7.x 網站與報告、glossary、method-budget）狀態改為「組長 2026-11-08 核准，可直接引用」。E 的簡報可直接引用 main 版本，不必再標「草稿」。
- 之後的修改照常提 PR，合併到 main 即視為可用，不再另等核准文字。仍須遵守的只有內容規則：實驗結果數字只用 D 交出的；v1、v2 結果不同表比較；不放保留集內容。

## 20. 2026-11-09 前瞻 LIVE 報告資料區塊修正與第 2 版

- 問題（A 11/08 在 Render 發現）：第 1、2 批前瞻報告的資料區塊用 30 案凍結快照計算，主張來源顯示「無來源」、收盤價停在 9/30。屬 A 的報告程式錯誤，Agent 輸出與前瞻快照本身沒錯。
- 合併 PR #32（報告改讀當時的前瞻快照）、#33（REPLAY 舊 CASE-13 標「舊開發草稿，已廢除」）、`codex/A-source-traceable`（B 11/09 決定：來源可追溯改為財報三檔組合 hash＋報告實際引用的片段；30 案 MOCK 結果不變）。main 430 passed。
- 組長端 11/09 在 Mac 建立第 2 版草稿（Supabase）：2330 `rv-db6b0e1b…`（快照 11/06，收盤 2,135，來源 2/2 可解析，資料品質低）、2317 `rv-2ed6652e…`（快照 10/30，收盤 245.5，來源 1/1，資料品質低）。資料版本 report-data-v1.4。
- 第 1 版維持已發布、留在歷史版本，不改寫；第 2 版待組長在 Render 登入核准後發布。發布後重跑 `backup_reports.py export` 並存 iCloud。
- 11/09 14:53–14:54 組長在 Render 登入後核准發布：2330 第 2 版 14:54:16、2317 第 2 版 14:54:44（台北）。線上確認：主張來源全部可解析、PDF 可下載。備份 `tmp/backups/20261109-145511`（4 份報告、4 份 PDF、11 個 job 資料庫，還原核對全部 PASS），已另存 iCloud `fintech-agent-backups/`，掃描無金鑰字串。

## 21. 2026-11-09 舊網站首頁改導向研究工作台

- 問題：舊網站「查詢分析」（`main.py`）讀的 Supabase 正式專案 `watooxoseljrnlsoequc`（東京，Free／Nano）約 11/06 起 Unhealthy，所有 REST 與內部健康檢查回 503；資源用量正常（CPU 3%、記憶體 51%、磁碟 13%），Supabase 全站狀態正常。11/09 15:03 組長同意後執行 Restart project，15:16 仍 503。組長決定不開單、不修復，舊查詢頁停用。
- 影響：只有舊查詢頁。研究工作台、LIVE 報告與 PDF 用報告測試專案，不受影響；實驗、鎖定、前瞻批次不需要舊網站。
- 組長決定：首頁 `/` 改 302 導向 `/research`（`web_app.py`，`tests/test_home_redirect.py`，commit 044e8d5），15:23 Render 上線確認。Supabase 修好後可改回。
- 風險：`fundamental_data` 只在該專案、Free 無備份；恢復後應另行匯出。

## 22. 2026-11-09 W10 正式評估排程與鎖定清單補列

- 第二段鎖定清單補列 `agents/budget.py`（v2 輸入上限 6,000、每 job 64,000 token）、`agents/store.py`、`agents/worker.py`；鎖定時另記 researcher／reviewer prompt 版本與全部預算上限。
- 正式評估 runner `scripts/formal_runs.py`：保留 20 案 × 3 模式 = 60 run；第二段未鎖定或 `--verify --strict` 未過即拒絕 live；只讀封存案例的執行欄位，結果列只含狀態與預算（`evaluation/formal/runs-v2.jsonl`），草稿留在 `tmp/formal_v2.sqlite3`，組長與 Claude 不打開。
- 執行計畫 `evaluation/run-plan.json`（固定種子 20261116；同案三模式連續、起始模式輪替；每配額日 2 案 × 3 模式），待 D 確認或替換。
- 11/09 離線檢查：保留 20 份快照工具呼叫 130 次，無例外、無缺快照（只回報錯誤，不看各案結果）。
- **組長決定：11/16–11/25 每天 19:30 跑 6 run，含週末，共 10 個配額日**（排程 fintech-formal-v2-daily）；B、D 評分與裁決排 W11 後半。

## 23. 2026-11-10 合併 D 的 v2 dual 評分；Researcher 補 next_signals 指示

- 合併 PR #37（D：`evaluation/d-drafts/calib-v2-scores-D.txt`，v2 dual 開發集 10 案）。D 標「不確定」兩處（CASE-08 c2、CASE-19 整體結果）交 B 核對，兩人不一致由組長裁決。
- CASE-15、18「不符合預期」：缺下一確認訊號。prompt 從未要求填 next_signals，屬規格漏寫。**組長決定修**：researcher-v1.2.4（`handoff/agent-version-changes.md` 第 9 項）。
- 驗證：11/10–11/12 煙霧測試即用新版；11/12 用剩餘額度以 dual 重跑 CASE-15、18。

- 11/11 補：W11 盲評匯出 `scripts/export_for_scoring.py`（回應 D 11/11 問題 3）。60 run 都執行後才匯出；去掉模式、停止原因、覆核紀錄、預算與 Reviewer 工具結果，隨機 answer_id 打亂順序；對照表存組長 Mac `tmp/`、只公開 sha256（`key-commitment.json`），B、D 都交評分後 `--reveal` 才公開並核對 hash。

## 24. 2026-11-11 股價快照格式修正；開發集缺股價列為限制

- 煙霧測試第 3 天（workflow，CASE-08、11、15、18、19、22；commit 9f84e5e）：6 案無錯誤。CASE-15、18 有寫下一確認訊號。CASE-19（不允許停在證據不足）在 workflow 停在證據不足；single 第 2 天有完成。**組長端建議不修**：workflow 是固定流程基準組，prompt 三模式共用；照實記為開發集觀察（待組長確認）。
- 股價：全域股價資料只有 2026-09-22 至 09-30 五個交易日，開發集 9 案 cutoff 在 7、8 月，`get_price_window` 回 `no_data` 是時間規則的正確結果，不是錯誤。補歷史股價要重開第一段凍結、動保留集資料、開發集重跑重評，**建議不改，列為限制**（估值未受正式評估檢驗；「未知」主張不計分；三模式條件相同）（待組長確認）。
- 保留集狀態統計（只計數量與欄位名稱，不看題目、數值、答案）：修正前 `get_price_window` 20 案為 ok 2、no_data 15、KeyError 3。3 案的 `price_snapshot` 是 `closes` 清單格式，程式只讀得懂開發集的單筆格式。11/09 的離線檢查（第 22 節）經 dispatch 執行，例外被包成 `tool_error`，當時沒有統計到。
- **組長決定：鎖定前修**（`handoff/agent-version-changes.md` 第 10、11 項）。屬工具讀檔格式，prompt 與判斷邏輯不動。修正後同一統計為 ok 5、no_data 15、例外 0；pytest 444 通過。
- 保留集接觸紀錄：11/11 搜尋 `price_snapshot` 的使用位置時，終端輸出帶出 `scripts/build_holdout_cases.py` 的一行擾動說明（一個案例、一個欄位）。Claude 沒有再開該檔，也沒有據此調整 prompt 或判斷邏輯；此次修正只依欄位名稱。`synthetic_adjusted` 欄位工具不回傳，是否為出題本意待出題組員確認。
