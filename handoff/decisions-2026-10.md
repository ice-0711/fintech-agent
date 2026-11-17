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
- 股價：全域股價資料只有 2026-09-22 至 09-30 五個交易日，開發集 9 案 cutoff 在 7、8 月，`get_price_window` 回 `no_data` 是時間規則的正確結果，不是錯誤。補歷史股價要重開第一段凍結、動保留集資料、開發集重跑重評，~~建議不改，列為限制~~ **（同日組長改為補齊，以第 25 節為準）**（估值未受正式評估檢驗；「未知」主張不計分；三模式條件相同）（待組長確認）。
- 保留集狀態統計（只計數量與欄位名稱，不看題目、數值、答案）：修正前 `get_price_window` 20 案為 ok 2、no_data 15、KeyError 3。3 案的 `price_snapshot` 是 `closes` 清單格式，程式只讀得懂開發集的單筆格式。11/09 的離線檢查（第 22 節）經 dispatch 執行，例外被包成 `tool_error`，當時沒有統計到。
- **組長決定：鎖定前修**（`handoff/agent-version-changes.md` 第 10、11 項）。屬工具讀檔格式，prompt 與判斷邏輯不動。修正後同一統計為 ok 5、no_data 15、例外 0；pytest 444 通過。
- 保留集接觸紀錄：11/11 搜尋 `price_snapshot` 的使用位置時，終端輸出帶出 `scripts/build_holdout_cases.py` 的一行擾動說明（一個案例、一個欄位）。Claude 沒有再開該檔，也沒有據此調整 prompt 或判斷邏輯；此次修正只依欄位名稱。`synthetic_adjusted` 欄位工具不回傳，是否為出題本意待出題組員確認。

## 25. 2026-11-11 組長決定補齊歷史股價（取代第 24 節「不改」的建議）

- **決定**：股價是公開資料，缺的是快照沒收，不是 Agent 查不到；補上才能檢驗估值段落，符合專題「提高證據完整度」的目的。資料變更、重新凍結與時程由組長決定，組員告知即可。
- **做法**（`scripts/extend_price_history.py`）：5 檔股價由 cutoff 前 5 個交易日補為 2025-01-02 至 2026-09-30 的全部交易日（2330、2454、2379、3034 各 422 日，2317 為 421 日）。來源與口徑不變（FinMind TaiwanStockPrice，未還原收盤價）；原 5 日數值完全相同才寫入；財報、總經、證據、案例檔都沒動；快照 cutoff 仍是 2026-09-30。
- **不看未來**：可得時間仍是交易日 17:30，工具只給案例 cutoff 之前的價格（`tests/test_price_history.py`）。
- **工具**：`agents/tools_impl.py` 新增 `_raw_file_covering`，`get_price_window` 的 content_hash 指向日期涵蓋該視窗的原始檔。原 5 日的原始檔紀錄保留，9/22–9/30 內的視窗仍回原 hash，所以既有工具 fixture（TR-17、TR-18）、同業快照、`source-manifest` 都不用改。
- **對帳**（`scripts/check_prices_twse.py`，結果 `data/price-history-twse-check.json`）：5 檔共 2,109 個日收盤價逐日與證交所 STOCK_DAY 比對，**全部相符、0 筆不符**；快照期間內 TWSE 有收盤價的交易日快照都有。
- **凍結**：不重跑整份凍結（會蓋掉 10/25、10/28 的簽核）。`scripts/build_freeze.py --amend` 新增修訂紀錄：`data/v12-frozen-manifest.json` 的 `amendments` 第 1 筆、`data-freeze.md` 第八節。cases_digest 98af84030d45 不變，`--verify` 一致；原簽核保留，修訂由組長負責。
- **檢查**：pytest 448 通過；check_sources、check_cases 0 錯誤。
- **影響**（離線、不呼叫模型）：開發集 9 案 1／5／20 日視窗都有資料，結束於 cutoff 前一個交易日；CASE-04 用案例自帶的單筆收盤價，行為不變。保留集只計狀態數量：1 日視窗 ok 20；5 日與 20 日視窗各為 ok 17、no_data 3（修正前 ok 5、no_data 15）。
- **限制（寫進報告）**：
  1. 保留集的預期答案在 10/25 凍結時寫成，當時多數案例查不到股價。組長看不到預期答案；LINE 群組紀錄（9/13–11/11）沒有任何訊息說明預期答案是否以「查不到股價」為前提。補股價後，Agent 可能寫出預期答案沒有涵蓋的估值主張。處理方式：預期答案不改；B、D 盲評照評分規則評，報告註明此差異。
  2. 校準 v1、v2 開發集 dual 重跑（11/06–11/08）與煙霧測試第 1–3 天都是補股價前跑的；補股價後的結果另外標示，不與之前的放同一張表。
  3. 開發集補股價後以 dual 重跑（11/12–11/14，額度內），組長自查；D 不重新全評。正式實驗 11/16 開始不變。
- **保留集接觸紀錄**：11/11 讀 `data-freeze.md` 前 40 行時看到 30 案清單（含保留集的類別、變體標籤與 cutoff，沒有題目、數值、答案）。沒有據此調整 prompt 或判斷邏輯；股價是整段補齊，不針對任何案例。

## 26. 2026-11-11 Researcher 補「來源衝突」處理規則（researcher-v1.2.5）

- 依據：D 的 v2 dual 評分（CASE-19 整體結果「不確定」）、煙霧測試第 3 天（workflow CASE-19 停在證據不足）。prompt 沒寫幣別／單位／口徑衝突且無法確定時怎麼做，屬規格漏寫。
- **組長決定修**：加一條通用規則（`handoff/agent-version-changes.md` 第 14 項）。不含案例內容；沒有看保留集。三模式共用同一 prompt。
- 驗證：不另花額度，11/12–11/14 的煙霧測試第 4 天與開發集補股價後 dual 重跑即用新版。結果沒有變好也照實記錄，鎖定前不再為結果調 prompt。
- 不做：程式層「不允許停在證據不足就退回重寫」（會改變有限預算下的行為）；CASE-26 逾時（凍結案例不改，10/24 已定）；workflow、single 較常停在證據不足（對照組，照實觀察）。
- 排程說明檔（第 4 天、前瞻第 3 批）的預期版本已改為 researcher-v1.2.5。D 的 `evaluation/d-drafts/runner-smoke.md`、`v12-runner-freeze.md` 仍寫 v1.2.4，鎖定時請 D 更新。
- pytest 448 通過。

## 27. 2026-11-11 get_price_window 回傳 synthetic_adjusted（第 24 節待確認事項結案）

- 第 24 節留下的問題：保留集 `price_snapshot` 的 `synthetic_adjusted` 欄位工具不回傳，是否為出題本意。組長 11/11 詢問 B，B 回覆：該欄位應由工具回傳給 Agent，照原樣傳出，不另加說明或提示。
- **組長決定照 B 的回覆修**（`handoff/agent-version-changes.md` 第 15 項）。屬工具漏傳欄位，不動 prompt 與覆核規則。
- 做法只依欄位名稱：有此欄位就整個照原樣放進回傳；Claude 沒有讀取或印出欄位的值。保留集只計數量：20 案 1 日視窗皆 ok，其中 1 案回傳帶有此欄位。開發集無此欄位，行為不變。
- 附帶效果（照實記錄）：覆核的「數字必須出現在工具結果」規則，會把此欄位內的數字視為工具回傳過的數字。
- B 的回覆含該題的出題意圖，只留在組長與 B 之間，不寫進 repo、Notion 或任何共用文件。
- pytest 449 通過；`build_freeze.py --verify` 一致（`agents/snapshot.py` 屬第二段）。

## 28. 2026-11-12 覆核規則：P/E 的 TTM 季度判定、查到卻沒寫的提醒

- 依據：開發集補股價後 dual 重跑 11/12（`agent/calib-v2-dual-postprice-1112.json`）。
  - CASE-04（必答）被覆核判證據不足。組長端逐項核對：股價 2026-09-30 收 2480（cutoff 當日 17:30 可得）、TTM EPS 86.28（2025Q3–2026Q2 連續四季）、P/E 2480 ÷ 86.28 = 28.74，都與快照一致。擋下的原因是「TTM 要四個連續單季」規則也套到 pe_ttm：P/E 的期間寫股價日期，規則讀不到季度就列 critical，第二輪無可修、預算用完而停止。屬程式誤判（與 11/07 第 7 項同類），不是模型錯誤。
  - CASE-01 通過覆核，但已取得股價卻沒寫估值，也沒查總經；覆核沒有任何提示。
- **組長決定修**（`handoff/agent-version-changes.md` 第 16、17 項）：
  1. pe_ttm 本身沒寫季度時，改看草稿中 eps_ttm 的季度，沒有就看快照的 TTM 季度；四季不連續或找不到季度仍列 critical。pe_ttm 自己寫了錯的季度照樣擋。
  2. 新增「查到了卻沒寫」提醒：已取得股價但沒有估值或本益比、沒有總經觀察（分已查未寫、未查兩種），各列一筆 minor。**只提醒、不改變放行結果**；Researcher 已回 insufficient 時不加。
- 只改覆核程式（`agents/review_checks.py`），不改 prompt（researcher-v1.2.5、reviewer-v1.2.2 不變），符合第 26 節「鎖定前除程式錯誤外不改 prompt」。沒有看保留集；兩條規則都是通用規則。
- 離線驗證（不花額度，用 11/12 的草稿與重建的工具結果）：CASE-04 由證據不足改為通過（餘 1 筆 minor：已取得總經未寫）；CASE-01 仍通過，多 2 筆 minor；CASE-15 規則端通過、多 2 筆 minor（實際結果由模型覆核判 insufficient，不變）；CASE-18 仍為證據不足。
- 版本標示：11/12 的 CASE-01、04 dual 結果是修正前規則；11/13 起的開發集重跑與 W10 正式實驗用修正後規則。CASE-04 於 11/13 以新規則重跑一次。
- 測試 `tests/test_review_pe_coverage.py`（合成資料）；pytest 459 通過。

## 29. 2026-11-12 盲評匯出附完整工具結果（B 11/11 提出）

- B 11/11：盲評答卷中被引用的 obs-* 只附 500 字摘要，說明要評分者「用同一快照重算」；評分者不便自己對保留集快照跑工具。
- **處理**：工具結果的完整 `data` 另存在 job 的 checkpoint（`agents/research_graph.py`），只給盲評匯出用；不放進任何送給模型的內容，也不放進執行紀錄事件，Agent 行為不變。`scripts/export_for_scoring.py` 對被引用的 obs 附 `result_data`（完整數字結果），答卷說明改為「不必自己重跑工具」。只附被引用的 Researcher 工具結果，不含順序、模式、覆核紀錄。
- 只對此後的 run 有效；正式實驗 11/16 起跑，60 份都會有。
- B 的第二點（「停止原因與執行紀錄是否一致」盲評時做不了）：組長端建議改為公開對照表（`--reveal`）後由程式逐份比對 stop_reason 與執行紀錄，B、D 抽查；待組長確認。
- 測試：`tests/test_export_for_scoring.py` 更新；模擬執行（不呼叫模型）確認 checkpoint 存有完整數字。pytest 459 通過。

## 30. 2026-11-13 案例檢查結果；「題目怎麼交給 Agent」待組長決定；保留集接觸紀錄

- 起因：組長 11/13 問「案例是否真的都不用改」。組長端逐案檢查開發集 10 案；保留集只做數量統計（只印數量、狀態、欄位名稱、型別與長度，不印內容）。
- **案例檔本身：沒有發現需要修改的地方。**
  - 保留集 20 案：會讀快照的五個工具沒有任何 tool_error（`calculate_metrics` 是純計算、不讀快照，未列入）。`search_evidence` ok 14、no_data 6；搜尋到的 30 筆來源 `read_evidence` 全部 ok；`get_financial_snapshot` ok 19、no_data 1（該案的模擬設定，任何呼叫都會觸發）；`get_macro_snapshot` ok 20；股價 1 日視窗 ok 20，5／20 日視窗 ok 17、no_data 3。擾動位置引用的來源編號都在快照內（11 筆 cutoff 前可得、1 筆在 cutoff 後）。覆核規則以 5 種合成草稿逐案試跑（含 11/12 新增的兩條），沒有例外。`check_cases.py`、`check_sources.py` 0 錯誤。
  - 保留集沒有 `read_evidence` 逾時模擬，不會出現開發集 CASE-26 的情況。CASE-26 測不到逾時的原因：該快照沒有 `evidences`，逾時指定的是全域來源編號，Agent 搜尋不到就不會去讀。維持 10/24 決定不改。30 案中沒有任何一案會在 live 觸發逾時，逾時處理只以離線測試為證，報告不可寫成 live 驗證過。
- **發現的問題在 runner（題目怎麼交給 Agent），不在案例檔。待組長決定：**
  1. 研究焦點（focus）目前一律送案例的 `variant`（變體名稱）。變體名稱多數直接寫出擾動類型（開發集例：「TWD與其他幣別混用」「單季EPS當TTM EPS」「read_evidence故意timeout」「要求呼叫未授權工具」），等於事先告訴 Agent 這題的陷阱。校準 v1、v2 與煙霧測試都在這個條件下跑。佐證：11/12 CASE-18 的草稿摘要直接寫「焦點要求…cutoff 之後的關鍵證據」後停止；校準 v1 的 CASE-26 在沒有發生逾時的情況下寫出「read_evidence 逾時」（S17、S27）。影響多大尚未量測。
  2. 保留集案例檔每案有 `task` 欄位（20 案皆為字串，17–48 字，各不相同，都不含變體名稱），開發集沒有這個欄位。`scripts/formal_runs.py` 的 `RUN_FIELDS` 沒有讀 `task`，正式實驗照現況送給 Agent 的會是 `variant`。
  3. `docs/CR-W05-holdout.md` 第 5 項（B 10/28 提出）一直沒有完成：保留集快照的 `task_input`（1 案）、`draft_under_review`（1 案）、`required_elements`（1 案）沒有傳入 job。保留集有 3 案的擾動位置就在 `task`、`task_input`、`draft_under_review`；照現行 runner，這 3 案 × 3 模式 = 9 個 run 的擾動到不了 Agent。11/09 寫正式 runner 時漏了這一項（組長端）。
- 待辦：向 B 確認三件事（`task` 是否就是給 Agent 的題目、`task_input`／`draft_under_review` 要怎麼附給 Agent、`required_elements` 是給 Agent 還是給評分者）；組長決定後改 runner（只依欄位名稱讀取，不看內容）、在開發集預演，再鎖定第二段。第二段鎖定與正式實驗起跑日是否順延由組長決定。
- **保留集接觸紀錄（Claude，11/13）**：為確認上述三個欄位有沒有程式讀取，以欄位名稱搜尋整個 repo 時沒有排除 `scripts/build_holdout_cases.py`，搜尋結果印出該檔 5 行，含 3 個保留案例的片段（擾動位置說明與輸入欄位的片段）。沒有打開該檔，沒有看到預期主張（expected_*）的文字內容。看到的內容沒有寫進任何文件，回報組長時也只說明經過、不轉述內容；沒有據此調整 prompt、覆核規則或工具。此後搜尋一律排除該檔與封存檔。之後 runner 的修改只依欄位名稱傳遞，格式由 B 指定。

## 31. 2026-11-13 題目改送 `task`；`task_input`、`draft_under_review` 原樣附給 Agent（第 30 節待決事項，依 B 的回覆實作）

- 組長 11/13 把第 30 節的三個問題問 B，並轉交 B 的回覆（只講欄位用法）。組長端依回覆修改 runner：
  1. **研究焦點改送 `task`，一字不改；不再送 `variant`。** `variant`、`category`、`expected_behavior`、`expected_*`、`allow_insufficient`、`perturbation_location` 都不進 Agent 輸入。`scripts/formal_runs.py` 的 `RUN_FIELDS` 改為 `case_id、ticker、cutoff_at、source_snapshot_id、task`；任何一案沒有 `task` 就停止。prompt 沒有改：`task` 仍放在可信輸入的 `focus`（prompt 原本就寫「focus 是本案研究焦點」）。
  2. **`task_input`、`draft_under_review` 以同名欄位、JSON 原樣放進可信輸入，不加任何說明，也不串進 focus。** single、dual（Researcher 與 Reviewer 都有）、workflow 三種模式都給。程式直接從該 job 綁定的快照依欄位名稱讀取（`agents/research_graph.py` 的 `CASE_INPUT_FIELDS`），job 契約（`agents/contract.py`）不用改。快照沒有這兩個欄位時，輸入和修改前完全相同。
  3. **`required_elements` 只給評分者，不送 Agent。** `scripts/export_for_scoring.py` 的盲評答卷新增 `given_to_agent`（題目與原樣附給 Agent 的欄位）與 `scorer_only`（`required_elements`）。
- **開發集題目**：B 11/14 前補 10 句，放新檔 `evaluation/dev-tasks.json`（`case_id`、`task` 兩欄）。`scripts/dev_traces.py` 有這個檔就優先讀；`evaluation/dev-cases.json` 與 `cases_digest` 不動，不需要第一段修訂 2。檔案還沒到之前，開發集仍送 `variant`。
- **條件標示**：每個 run 的紀錄多一欄 `focus_source`（`task` 或 `variant`）。校準 v1、v2 與煙霧測試（到 11/12 為止的全部開發集結果）都是送 `variant` 的條件；之後送 `task` 的結果不可與它們直接比較，報告須註明條件不同。
- 只依欄位名稱與數量檢查保留集（不印內容）：20 案的 `task` 都通過 job 契約（focus ≤ 200 字）；`task_input` 1 案、`draft_under_review` 1 案會送達；`load_holdout()` 取出的欄位只剩上述五個。
- 測試：`tests/test_task_inputs.py`（合成資料：三種模式與 Reviewer 都收到、沒有欄位時不變、`required_elements` 不進 Agent 輸入、`dev-tasks.json` 優先）、`tests/test_formal_runs.py`、`tests/test_export_for_scoring.py`。pytest 470 通過；`build_freeze.py --verify` 一致；`check_cases.py` 0 錯誤。
- **還沒做、待組長決定**：B 的 `dev-tasks.json` 到了以後在開發集用 `task` 預演（用當日額度），確認沒有問題再鎖定第二段；鎖定日與正式實驗 11/16 起跑日是否順延。第二段沒鎖定前 `formal_runs.py --live` 會拒絕執行。
- `docs/CR-W05-holdout.md` 第 5 項至此完成（該文件由 B 維護，請 B 更新狀態）。

## 32. 2026-11-13 前瞻第 3 批：聯發科負債覆寫（第一段凍結修訂 2）；結果

- 21:10 排程在凍結快照時中止：「2454 找不到 2025Q2 的科目 BondsPayable」。排程照規定停止，沒有改檔、沒有用 Gemini 額度。
- **原因**：FinMind 在 11/06 之後新增聯發科 2026Q3 資產負債表，出現應付公司債 111,338,386 千元（前兩批該科目在 FinMind 完全不存在）。快照程式規定「選用負債科目只要出現過，五季都要有值或有覆寫」，缺 2025Q2、2026Q1、2026Q2 而中止。FinMind 同時補上 2025Q3 長期借款 0，與既有覆寫列並存也會中止。
- **組長決定由組長端直接修**（不經 B）。`data/manual/balance_overrides.csv`：
  1. 新增 2454 的 2025Q2、2026Q1、2026Q2 應付公司債 0 三列。依據：組長端 11/13 逐表核對 MOPS 聯發科合併資產負債表，115Q1（115/03/31）、115Q2（115/06/30 與比較欄 114/06/30）都沒有應付公司債科目；115Q3 為 111,338,386 千元，114/12/31、114/09/30 為 0，與 FinMind 相符。
  2. 刪除 2454 2025Q3 長期借款 0 一列（FinMind 已有同值）。
- 該檔屬第一段凍結的人工檔，以 `build_freeze.py --amend` 記為**修訂 2**（`data-freeze.md` 第八節）。30 案實驗用的 `data/financial-snapshots.json` 沒有重建，案例與 cases_digest 98af84030d45 不變。
- **第 3 批結果**（Agent v2，researcher-v1.2.5／reviewer-v1.2.2；修正後組長端 21:16 手動執行，晚於截止 16 分鐘）：快照 sha256 64d5032e8bc4；截止後資料檢查 0 筆。2330 insufficient_evidence（researcher_insufficient）、2317 succeeded（review_pass）、2454 succeeded（review_pass）。報告皆未發布，方向 none。
- **限制（照實記錄）**：五家的 2026Q3 都已在截止前公告，但本批財報仍用到 2026Q2。原因是 FinMind 還沒有鴻海 2026Q3 的損益資料，程式的設計是新季別「全部納入或全部不納入」，於是照既定備案不帶新季別（第 2 批相同）。聯發科 2026Q3 的應付公司債因此沒有進入本批計算。報告引用本批時須註明財報截至 2026Q2。
- 請 B 事後複核修訂 2 的三列覆寫與 MOPS 依據。pytest 471 通過；`build_freeze.py --verify` 一致。

## 33. 2026-11-14 簡報呈現規則（AGENTS.md 第五節）

- 起因：E 的 W08 簡報（Canva，28 頁）幾乎每頁都有來源檔案路徑、「依組長確認之 main 文稿編排」頁尾與「不代表正式實驗成果」等聲明，評審讀不到重點。組長 11/13 在群組請 E 改從評審的角度重做，E 已同意。
- 查手冊任務表（Notion，W07-E 至 W13-E）：驗收清單每週都要求「來源與版本完整」「待填不冒充完成」「未完成聲明不刪」「明確標回放片段」，沒有任何一條要求評審看得懂；「備用 19」「備用 18」也是手冊指定的頁名。E 是照驗收清單做的，問題主要在任務寫法。第一次從「講給人聽」檢查排在 W12（12/04）。
- **組長決定**：在 `AGENTS.md` 加第五節。重點：正文頁每頁一句重點；來源、版本、內部用語放備註欄與附錄頁；限制聲明全份只在實驗設計頁講一次（附錄再列）；MOCK／REPLAY 截圖只留短標籤；沒有的結果寫「待正式實驗」；頁碼連續、備用頁放最後。手冊驗收清單的相關條目以這個做法視為符合。
- 第二節四件事（數字來源、v1／v2 分開、不寫保留集內容、不寫正確率）不變。
- W08-E 交付狀況：PR #42（11/13 合併）已把 `artifact-index-w08.md` 與 `deck-W08-E-integrated-v1.pdf`（放在 repo 根目錄）交上 main。指定檔名的 `slides/deck-v7.pptx`、`slides/v12-graph-and-limits.pptx` 以及 W09-E 的 `slides/deck-v8.pptx` 等 main 上還沒有；簡報依第五節重做後再交，日期由組長與 E 約定。
- **另一件待組長決定（E 11/13 提出）**：研究問題有兩套，編號相同、內容不同。`docs/v12-motivation.md`（第一章）的 RQ1–RQ3 是資料一致性、可追溯研究、成果可用性；`docs/v12-evaluation-method.md` 與 D 的 `evaluation/d-drafts/protocol-v1.md` 的 RQ1–RQ3 是選工具是否提高證據支持率、Reviewer 是否更能發現並修正錯誤、品質改善是否值得成本。正式實驗與評分指標對應的是後者。組長端建議以後者為正式 RQ，前者在第一章改稱「系統設計目標」；組長已在群組請 C 說明，定案前 E 的研究問題頁先不動。

## 34. 2026-11-14 合併 W09-A；E01 示範方式定案（不開放 Render 研究入口）

- **合併 W09-A**（分支 `codex/W09-A`，A）：`design/ui-regression-w09.md`、`demo/sample-w09.mp4`、`demo/sample-w09-render-live.mp4`、`media/v12-screenshots-manifest.csv`、`media/w09/` 16 張圖；回放清單加入 Agent v2 dual 紀錄並依版本分組、標示條件。只改 `research_ui/replays.py`、`static/research.js`，沒有動 Agent 程式、prompt、案例與凍結檔。組長端試合後 pytest 477 通過，`build_freeze.py --verify` 一致。回放只讀 `agent/` 的開發集紀錄，不讀保留集。兩支影片的內容組長端沒有逐格檢視，依 A 的說明登錄。
- **E01（示範案例有配額時真的執行）組長決定**：
  1. **不開放 Render 研究入口，不在展示現場執行。** 理由：11/02 已核定研究只在組長 Mac 執行、Render 不設 Gemini 金鑰；11/16–11/25 每日 6 個額度全數用於正式實驗；現場執行結果不可控。
  2. **示範以標明 REPLAY 的 Agent v2 真實執行紀錄呈現**，講稿寫「回放」，不寫「現場執行」。MOCK 畫面只能說是介面展示。
  3. E01 的驗收寫法：真實執行在組長 Mac 完成並留有紀錄（`agent/` 的執行紀錄檔），展示時以回放呈現。
  4. 「至少一次覆核要求補查後修正」：目前 Agent v2 沒有「退回修正後通過」的紀錄（9 筆通過都是第一輪通過）。現有可用的是 CASE-15（Reviewer 要求補查 → Researcher 改稿 → 仍判定證據不足而停止），講稿照實說明。11/14 開發集預演若出現「修正後通過」的紀錄，再改用該筆。
- **兩支影片可以怎麼說**（依 A 11/14 說明）：
  - `demo/sample-w09-render-live.mp4`（41 秒）：Render 線上、組長核准發布的 LIVE 報告（2330 報告第 2 版 rv-db6b0e1b，資料截止 11/06 21:00）。**這份報告是 Agent v1 執行的。**
  - `demo/sample-w09.mp4`（71 秒）：本機 MOCK 介面展示加 Agent v2 真實執行紀錄的回放（CASE-15、CASE-18）；不是 LIVE，不可說成現場執行或線上結果。
- **用語**：報告版本寫「第 2 版」，Agent 版本寫「Agent v1／v2」，不單寫「v2」，避免把報告第 2 版讀成 Agent v2。目前線上兩份 LIVE 報告（2317、2330）都是 Agent v1；Agent v2 的 LIVE 研究只有前瞻第 3 批（尚未發布）。

## 35. 2026-11-14 開發集預演（送 task）結果；覆核規則：TTM EPS 期間只寫結尾季

- **預演**（決策 31 的後續；Agent v2，researcher-v1.2.5／reviewer-v1.2.2；題目用 B 的 `evaluation/dev-tasks.json`，6 個 run 的 `focus_source` 都是 `task`）。紀錄：`agent/calib-v2-task-rehearsal-1114-dual.json`、`agent/calib-v2-task-rehearsal-1114-workflow.json`。
  - dual：CASE-01 review_pass；CASE-04 review_insufficient；CASE-19 review_pass（覆核退回 1 輪後修正通過）；CASE-22 review_pass。
  - workflow：CASE-01 產出草稿；CASE-19 researcher_insufficient。
  - 沒有程式錯誤、沒有輸出被截斷。只有 6 筆，不能據此說「改送 task 對結果沒有影響」；與送 `variant` 的舊結果條件不同，不放同一張表。
  - CASE-19 dual 是 Agent v2 第一筆「覆核要求補查 → 修正 → 通過」的真實紀錄（E01 示範可用，決策 34 第 4 點）。
- **CASE-04 被規則誤擋**：收盤價 2480、TTM EPS 86.28、P/E 28.74 都與快照一致。模型把 eps_ttm 的期間寫成「2026Q2」（截至該季），四個季度寫在主張文字裡；「TTM 要四個連續單季」規則只讀到一個季度就列 critical，退回後模型沒有改寫法，預算用完而停止。模型覆核兩輪都判 pass。v2 紀錄中其他 TTM 數字都寫成起訖或四季清單，這是第一次出現此寫法。
- **組長決定修**（`handoff/agent-version-changes.md` 第 20 項）：eps_ttm 的期間只寫一個季度時，若快照的 TTM 是連續四季、最後一季就是該季、且數值等於快照的 eps_ttm（差 ≤ 0.005），視為快照的四季。用到這個 eps_ttm 的 pe_ttm 同樣適用。單季 EPS 冒充 TTM（數值對不上）、結尾季不符、快照四季不連續或沒有 TTM 季度，仍列 critical。
- 只改覆核程式（`agents/review_checks.py` 的 `as_of_ttm_quarters`），prompt 不變；沒有看保留集；屬通用規則。與決策 28 同類（算對卻被判定方式誤擋）。
- 離線驗證（不花額度，用今晚的草稿與 job 內存的工具結果）：CASE-04 由證據不足改為通過、無任何問題項；CASE-01、19、22 結果不變。CASE-04 沒有以新規則 live 重跑（今日額度已用完）。
- 版本標示：11/14 預演的 CASE-04 dual 是修正前規則；W10 正式實驗用修正後規則。
- 測試 `tests/test_review_pe_coverage.py` 新增 4 項（合成資料）；pytest 481 通過。

## 36. 2026-11-14 正式實驗前全面檢查（案例、runner、排程）；四件事待組長決定

- 起因：組長 11/14 要求在鎖定前把案例相關問題全面檢查一遍。開發集 10 案逐案看內容；保留集 20 案只看數量、狀態代碼、欄位名稱、型別、長度與 hash，不看、不印內容。檢查程式都放在暫存目錄，不進 repo。
- **檢查通過**
  - 開發集 10 案：題目（`evaluation/dev-tasks.json`）都是中性問句；擾動都在快照來源或工具模擬裡，不在題目裡。CASE-26 逾時測不到（已知，決策 30）。
  - 保留集無模型試跑：以固定腳本代替模型（不連線、不花額度），20 案 × 3 模式 × 3 種合成草稿 = 180 次，走正式 runner 同一條路徑，寫入暫存資料庫後刪除；沒有動 `tmp/formal_v2.sqlite3` 與 `evaluation/formal/`。結果：0 例外，三模式都能跑完；研究焦點等於案例 `task` 180／180；`task_input`、`draft_under_review` 原樣送達 Researcher（三模式）與 Reviewer（dual）；`variant`、`expected_*`、`required_elements` 等欄位沒有出現在 Agent 輸入；輸入估計最大 4,472（上限 6,000）；工具呼叫最多 8 次（上限 10）；每案可搜尋到的來源最多 4 筆，workflow 的「前 5 筆」讀得到全部。
  - 覆核規則（含決策 35）以 8 種合成草稿 × 20 個保留快照試跑：無例外。
  - 封存：三個封存檔的 hash 與 `fixtures/test/SEAL.json`、`evaluation/cases_manifest_v1.json` 一致；兩份封存案例檔內容相同。`check_cases.py`、`check_sources.py` 0 錯誤。
  - 外洩掃描：比對 406 個受版控文字檔（不含封存檔與出題程式）。保留集的題目 0 筆、預期主張 0 筆、`task_input`／`draft_under_review`／`required_elements` 0 筆。變體名稱出現在 `data-freeze.md`、`evaluation/cases_manifest_v1.json` 等凍結文件（原本就列 30 案變體，不進 Agent 輸入）。另有 2 個 14 字的數字片語同時出現在保留集來源與開發／前瞻的 Agent 草稿，屬同一公開財報數字的相同寫法，不是外洩。
  - 執行計畫：60 run、20 案與封存檔一致、每配額日 2 案 × 3 模式。`build_freeze.py --verify --strict` 只剩第二段 6 個檔不同，鎖定後會通過。
- **發現的問題（待組長決定）**
  1. **排程會卡住**：正式實驗排程用的 `scripts/formal_runs.py` 不在無人值守允許清單（`~/.claude/settings.json` 只列了 `dev_traces.py`、`forward_research.py` 等）。11/16 19:30 很可能停在等待核准（10/23、10/29 發生過同類情況）。需要加一條允許規則；這是放寬無人值守權限，要組長同意。
  2. **TTM 覆核規則的修正在多數保留案不生效**：決策 28、35 讀的是「案例自帶的財報快照」。保留集 20 案中 18 案的財報由共用資料庫提供，覆核規則看不到工具回傳的 TTM 季度；另 2 案自帶財報快照但沒有 TTM 季度。以開發集 CASE-01（同樣由共用資料庫提供）實測，數字全部正確時：草稿寫出四季 → 通過；本益比以股價日期標示且草稿沒有另列 TTM EPS → 被擋；TTM EPS 只寫結尾季 → 被擋；本益比寫結尾季 → 被擋。
  3. **覆核用的數字清單沒有套用工具模擬**：保留集有 1 案設定財報工具回 no_data，但覆核規則用來核對「數字是否出現在工具結果」的清單是直接讀資料產生的，仍含 12 個 Agent 沒拿到的財報數字。模型若憑記憶寫出相同數字，規則不會擋。
     - 第 2、3 點的共同修法：覆核用的財報資料改成「這個 job 的工具實際回傳的內容」（套用工具模擬、帶上工具回傳的 TTM 季度與 TTM EPS）。屬 `agents/snapshot.py`、`agents/review_checks.py`，第二段。
  4. **排程沒有緩衝、鎖定清單少兩支程式**：cron 是 11/16–11/25 共 10 天，剛好 60 run，任何一天沒跑就會缺；建議延到 11/30（跑滿 60 會自動回報完成）。另外「題目怎麼送」現在由 `scripts/dev_traces.py`、`scripts/formal_runs.py` 決定，但這兩支不在第二段鎖定清單，建議鎖定時列入。
- **不擋實驗、待更新**：D 的 `evaluation/d-drafts/v12-runner-freeze.md` 仍寫研究焦點是「案例標題」（決策 31 後是 `task`）；`evaluation/run-plan.json` 的狀態仍是「待 D 確認」；鎖定時要產生 `handoff/v12-freeze.md`、`release/eval-version.json`。
- **這次檢查沒有涵蓋**：真實模型的行為（試跑用固定腳本）；CASE-04 以決策 35 的規則 live 重跑；Notion 與 Canva 上有沒有保留集內容；排程工作階段遇到超過 10 分鐘的指令會如何處理。

## 37. 2026-11-14 組長對第 36 節四件事的決定；覆核用的財報資料改為「這個 job 的工具實際回傳的內容」

- **組長的決定（11/14）**
  1. 無人值守允許清單加入 `scripts/formal_runs.py`：同意。組長端在 `~/.claude/settings.json` 的允許規則加一條（與 `dev_traces.py`、`forward_research.py` 同樣寫法）。
  2. 第 36 節第 2、3 點：修（內容見下）。
  3. 排程：不延長，維持 11/16–11/25。任何一天沒跑，剩下的 run 由組長決定何時手動補跑（每個配額日仍不超過 6 個）。
  4. 鎖定清單是否列入 `scripts/dev_traces.py`、`scripts/formal_runs.py`：組長詢問內容，尚未決定。
  5. D 的文件不另請 D 更新，由組長端更新：`evaluation/d-drafts/v12-runner-freeze.md` 新增第七節「組長端更新」（D 的原文不改，過時的一句加註）；`evaluation/run-plan.json` 的狀態改為「D 11/09 回覆可以照用（未逐案檢查）；組長 2026-11-14 確認採用」。
- **修正內容**（`handoff/agent-version-changes.md` 第 21–23 項；prompt 不變）
  1. 覆核視圖（`agents/snapshot.py` 的 `snapshot_view`）取財報與股價數字時，改走和 Agent 工具呼叫相同的路徑，快照的工具模擬一併生效：工具對 Agent 回 no_data 或逾時時，它的數字不算「工具回傳過」，也不提供 TTM 季度。
  2. 視圖新增 `tool_ttm`：財報工具回傳的 TTM 季度與 TTM EPS，資料來自案例快照或共用資料庫都一樣。「TTM 要四個連續單季」規則（含決策 28、35）改讀它；工具沒有回傳時，不退回去看案例自帶的財報快照。
  3. 本益比的期間寫 TTM 結尾季（例如 2026Q2）時，和寫股價日期同樣處理：四個季度看它用的 TTM EPS，且結尾季必須相同。
- **仍然會擋**：單季 EPS 當成 TTM（數值對不上）、結尾季不是最後一季、只有三季、工具的四季不連續、工具沒有回傳而草稿只寫結尾季。
- **驗證**（都不花額度）
  - pytest 491 通過（新增 `tests/test_review_view.py`、`tests/test_review_pe_coverage.py` 6 項，合成資料）。
  - 開發集 CASE-01（財報來自共用資料庫）、數字全部正確的四種寫法：寫出四季、本益比標股價日期且未另列 TTM EPS、TTM EPS 只寫結尾季、本益比寫結尾季，修改前 1 種通過，修改後 4 種都通過。
  - 已存的 36 份 Agent v2 草稿（開發集與前瞻，不含保留集）修改前後逐份比對：只有 1 份的規則結果改變（11/07 CASE-15 dual，本益比寫結尾季，規則由 revise 改為 pass；該次 live 最終結果 review_insufficient，紀錄不改）。11/14 預演的 4 份 dual 草稿：CASE-04 通過，其餘不變。
  - 保留集（只看數量）：覆核視圖含有 Agent 沒拿到的財報數字的案例 1 → 0；視圖帶有 TTM 季度的案例 0 → 17（另 2 案自帶財報快照而沒有 TTM 季度、1 案財報工具回 no_data）。規則以合成草稿 × 20 個保留快照試跑無例外；180 次無模型試跑 0 例外，正式進度仍為 0／60。
- 沒有看保留集內容；兩項都是通用規則。版本標示：11/14 以前所有 dual 結果是修正前規則，W10 正式實驗用修正後規則。
- **檢查中另外發現、尚未處理（待組長決定）**：本益比的數值目前沒有確定性規則核對。規則把 `pe_ttm` 當作「另有重算規則」而跳過「數字必須出現在引用來源」的檢查，但重算規則只在草稿附上 `inputs` 時才執行；prompt 沒有要求附 `inputs`，已存的 6 筆 Agent v2 本益比事實都沒有。這 6 筆的數值都出現在它們引用的 `calculate_metrics` 結果中，沒有發現錯誤；但寫錯的本益比目前只能靠模型覆核發現。

## 38. 2026-11-14 本益比數值的核對規則；鎖定清單補列 runner；排程權限測試

- **組長的決定（11/14）**：鎖定清單列入 `scripts/dev_traces.py`、`scripts/formal_runs.py`；第 37 節最後一點的本益比規則要加；排一個唯讀的排程測試。
- **本益比規則**（`handoff/agent-version-changes.md` 第 24 項）：`pe_ttm` 沒有附 `inputs`、也不是引用公告原文時，數值必須出現在這個 job 的某個工具結果裡（狀態 ok 的工具結果中的數值，或財報／股價工具回傳的數字），找不到列 critical。允許依主張自己的小數位數四捨五入（28.7、29 都算 28.74 的寫法；28.8、28.75 不算），不做單位換算。附了 `inputs` 的照原本的重算規則；沒有工具紀錄可查時不判。
  - 只改覆核程式（`agents/review_checks.py`），prompt 不變；沒有看保留集；屬通用規則。
  - 驗證（不花額度）：pytest 500 通過；36 份已存 Agent v2 草稿（開發集與前瞻）修改前後 0 份改變；開發集 CASE-01 上，工具算出的值與它的一位小數、整數寫法通過，憑空的數值被擋；保留集（只看數量）規則試跑與 180 次無模型試跑無例外。尚未以真實模型執行。
  - 限制：這條規則只確認數值「來自某個工具結果」，不檢查計算時用的股價與 EPS 對不對（例如用單季 EPS 去算）；那一部分仍靠模型覆核。
- **鎖定清單**：`scripts/build_freeze.py` 的第二段清單補列兩支 runner。送什麼題目給 Agent、讀封存檔的哪些欄位由這兩支決定（決策 31）。鎖定後共 12 個程式檔與 2 個 prompt，hash 在鎖定時才記錄。`scripts/export_for_scoring.py` 不列入：實驗結束後才使用，且預定補上「公開對照表後比對停止原因」。
- **排程權限測試**：一次性排程，11/15 10:00，只執行 `scripts/formal_runs.py --status`（唯讀，不含 `--live`），確認無人值守時不會停在等待核准。

## 39. 2026-11-14 檔名整理的做法（組長決定）

- 現況盤點：受版控檔案 575 個，其中 399 個的路徑被其他檔案引用（118 個被程式引用），64 個以路徑記在凍結紀錄，另有多數交付物檔名由手冊指定。在原 repo 直接改名風險高。
- **組長決定**：
  1. 原 repo 不改名、不搬動（原訂「實驗後整理舊檔」取消）。
  2. 最終成果出來後，另開一個新的 GitHub repo 作為乾淨版：給人看的文件與結果放進中文資料夾、檔名統一；程式整包放在一個資料夾，內部路徑不改，才能執行與驗證。
  3. 現在不在 `AGENTS.md` 加檔名規則；乾淨版由組長之後自行進行。
- 到時要確認的事：保留集封存檔與盲評對照表是否放入；FinMind 原始資料授權不可轉散布，不放；乾淨版註明由原 repo 的哪個 commit 產生；建立新 repo 屬對外發布，建立前由組長確認。
- 時間：與手冊 W13-E（12/07–12/11）「打包 final 目錄並建立成果索引」同一週。

## 40. 2026-11-15 鎖定前的 live 驗證（開發集 4 案 dual）；排程權限測試結果

- **排程權限測試**：原訂 11/15 10:00 的自動執行因電腦不會開機，改為 19:30（與正式實驗同一時刻）；組長另要求「現在跑」，19:06 手動觸發一次。排程工作階段直接執行 `scripts/formal_runs.py --status`，沒有等待核准，13 秒完成，輸出「formal-v2：0/60 已執行；pending 60」。
- **live 驗證**（Agent v2，researcher-v1.2.5／reviewer-v1.2.2，題目送 task，覆核規則為 11/14 修正後，commit 36758df）。紀錄：`agent/calib-v2-rules-check-1115-dual.json`。
  - CASE-04：succeeded／review_pass，沒有補查。收盤價 2480、TTM EPS 86.28（列出四季）、本益比 28.74（引用 calculate_metrics 的結果，Reviewer 另外重算一次）。11/12、11/14 兩次被規則誤擋的必答案例，這次通過。
  - CASE-01：succeeded／review_pass。營收、毛利率、EPS 與官方來源一致。
  - CASE-22：insufficient_evidence／researcher_insufficient。Researcher 的三個工具回合都用在 search_evidence（每次都回同一筆來源），沒有呼叫 get_financial_snapshot；草稿寫出單季 EPS 27.25（正確），說明缺其他三季、無法計算近四季合計後停止，沒有把單季當成 TTM。11/14 同一題的路徑是「搜尋兩次 → 財報快照」而通過。屬模型選工具的變異，不是覆核規則造成。這是必答案例，停在證據不足，照實記錄。
  - CASE-15：insufficient_evidence／researcher_insufficient（此案允許）。指出法說會正文不可讀，沒有補造內容，列出 2 個下一確認訊號；引用的單季營收 1,521.83 億元與財報工具結果相符。
  - 四個 run 沒有程式錯誤，沒有輸出被截斷（單次輸出最長 930 token），新規則沒有誤擋。
- **驗證範圍**：這次模型都把 TTM 的四季寫出來，所以「TTM EPS 只寫結尾季」「本益比寫結尾季」「財報工具回 no_data」三條路徑沒有在 live 出現，仍只有離線測試為證（決策 35、37、38）。本益比數值規則在 CASE-04 實際執行並通過。
- **觀察（不處理）**：dual 的 Researcher 第一輪只有 3 個工具回合；案例快照的 search_evidence 不論查詢字串都回同一組來源，模型重複搜尋會把回合用完。這是既有設計，三模式比較會反映這個差異。

## 41. 2026-11-15 第二段鎖定（Agent 程式、prompt、runner）；W09-L 交付

- 組長 11/15 在 live 驗證（第 40 節）後決定鎖定。鎖定前拉下 B 的 503b8be（前瞻第 3 批稽核；沒有動到凍結或待鎖定的檔案；B 複核修訂 2 通過），pytest 501 通過。
- **鎖定**：2026-11-15 19:32:19 執行 `scripts/build_freeze.py --lock-agent`。第二段共 14 個檔（10 支 Agent 程式、2 支 runner、2 個 prompt），hash 記入 `data/v12-frozen-manifest.json`；第一段各組紀錄不變。`--verify --strict` 通過；`formal_runs.py` 的執行前檢查（`lock_ok`）回傳通過。沒有執行任何正式 run，進度 0／60。
- **版本**：gemini-3.5-flash-lite（thinking minimal、temperature 0）、researcher-v1.2.5、reviewer-v1.2.2；單次輸入 6,000、輸出 1,500、每 job 64,000 token；每 job 8 次發送、10 次工具、2 輪補查；J=6。Agent v2 為 `handoff/agent-version-changes.md` 第 1 至 24 項。
- **交付**（手冊 W09-L）：`release/eval-version.json`（機器可讀，含 14 個檔的完整 hash、案例與執行計畫的 hash、結果標示規則）、`handoff/v12-freeze.md`（鎖定內容、鎖定前的驗證、已知限制 8 點、鎖定後的規則、驗收對照）。手冊所稱 `research/batch-3.json` 即 `research/forward-batch-3.json`。
- **鎖定後**：到 60 run 跑完前，鎖定與凍結的檔案不修改；必須修改時由組長決定並改用新的實驗版本代號。正式實驗 11/16 19:30 起由排程每天執行 6 個。
- B 的稽核另外記錄、組長端知悉的事項（都不改）：前瞻第 3 批 2317 的本益比用了 11/11 而非 11/13 的收盤價，覆核沒有發現（已列入 `handoff/v12-freeze.md` 已知限制第 2 點）；2330 是輸出格式無效而停止；`research/forward-batch-3.json` 的 `generated_late` 為空，實際晚於截止 16 分鐘（決策第 32 節已記錄，是否補進該檔由組長決定）。

## 42. 2026-11-16 盲評範本補欄位；前瞻第 3 批補記 generated_late（回覆 B 11/15 的 W10-B 確認）

- **評分時程**（B 詢問）：照決策 22，B、D 的評分與裁決排在 W11 後半；手冊 W10-B、W11-B 的評分合併，60 run 跑完匯出後一次做。交付檔仍照手冊分兩份，前 10 案／後 10 案依 `evaluation/run-plan.json` 的順序（第 1–5 天的 10 案為 batch1）。評分原檔放 `evaluation/formal/scoring-v2/`，檔名用 `scores-B`、`scores-D` 開頭（`--reveal` 只認這個開頭）；匯出前該資料夾不能放任何檔案（匯出程式會拒絕執行）。
- **範本補欄位（組長決定加）**：`scripts/export_for_scoring.py` 產生的 B、D 評分範本，每份答卷補上 rubric 第六節的「植入錯誤：預期／被指出／修正幾個」「拒答：是否選 insufficient、是否說明缺口」兩欄；表頭寫明另存檔名 `scores-{評分者}.txt`。匯出程式不在鎖定清單，不影響正式實驗。測試 `tests/test_export_for_scoring.py` 新增 1 項。
- **generated_late（組長決定補）**：`research/forward-batch-3.json` 的 `generated_late` 由 null 改為文字（排程中止原因、21:16 手動執行、晚於截止 16 分鐘），寫法同第 1、2 批；只改這一欄，快照與其 hash 不變。B 的總表程式兩種情況都能讀；B 的測試 `test_generated_late_derived_from_time_when_record_is_silent` 原本靠第 3 批紀錄為 null 來測「紀錄沒寫時由產生時間判定」，改名為 `test_generated_late_for_the_real_batches`，另以假資料補一個同名測試涵蓋該情況。
- 仍待組長決定：公開對照表後由程式比對停止原因（B、D 11/12 同意，需在 11/25 匯出前完成）；前瞻第 3 批是否發布。
- pytest 503 通過；`build_freeze.py --verify --strict` 通過；正式進度 0／60。

## 43. 2026-11-16 合併 A 的兩個分支（回放清單、obs 對回來源）；前瞻第 3 批的來源對應結果

- **A 11/15 的提問**（發布程式要不要把 obs-N 和它查到的來源存進報告、改 `agents/publication.py`）：A 隨後找到不改 `publication.py` 的做法（發布時傳入的 job 本來就帶工具紀錄），這題不用決定。
- **合併**（組長 11/16 決定）：
  - `codex/A-replay-task-batches`：回放清單加入 11/14、11/15 兩批（題目送 task）並自成一組；三條示範路徑為 CASE-04 通過、CASE-19 退回修正後通過、CASE-15 證據不足；另有 52 秒回放影片與 12 張截圖（`design/replay-demo-paths-1115.md`）。
  - `codex/A-obs-source-map`：報告的「來源可追溯」改為把 obs-* 對回這個 job 自己的工具紀錄（規則依 B 11/15，`design/obs-source-trace-1115.md`）：read_evidence／search_evidence 對到它讀到或看到的片段、財報／股價／總經對到快照實際回傳的季別與日期、calculate_metrics 要往回追到更早的工具結果；對不到判「缺來源」，事實主張沒有引用任何來源也判缺。對應表存進發布版本（`data.obs_map`），來源抽屜與 PDF 會列出。
  - 兩個分支都沒有動到第二段鎖定的檔案、`data/`、`fixtures/`、案例檔與 `agents/publication.py`。合併前在暫存區試合、合併後在 main 上各驗一次：pytest 516 通過，`build_freeze.py --verify --strict` 通過，正式 runner 的執行前檢查通過，正式進度 0／60。
  - 組長端以合併前後的程式重算 9 份前瞻報告的資料：兩份已發布的 Agent v1 報告（第 1 批 2317、第 2 批 2330）以及其他 Agent v1 草稿，除了版本號（report-data-v1.4 → v1.5）外完全相同；判定改變的只有引用 obs 的草稿（第 2 批 2454 由 pass 改為 missing，未發布）。
- **第 3 批的對應結果**（`scripts/obs_trace_check.py --batch 3`，只讀組長 Mac 的 job 資料庫、不呼叫模型；結果 `research/forward-batch-3-obs-trace.json`，交 B 核對）：
  - 2454：3 個 obs 都對到快照的來源（4 筆片段 hash 相符、財報快照 2025Q3–2026Q2、股價 11/13），來源可追溯 pass，資料品質風險低。
  - 2317：obs-5（計算本益比的 calculate_metrics）在紀錄中找不到計算輸入，判「計算結果，輸入未驗證」，來源可追溯 missing，資料品質風險高。原因是 job 紀錄只保存工具結果與參數雜湊，沒有保存 calculate_metrics 的輸入數值。B 11/14 稽核另外發現這個本益比用的是 11/11 而非 11/13 的收盤價。
  - 2330：程式也有檢查（A 的說明原寫「略過」）。它的草稿是 Researcher 輸出格式無效時程式補上的證據不足紀錄，沒有任何主張，所以結果 pass 只代表沒有東西可查，不代表來源可追溯；這份不發布。
- **已知限制**：job 紀錄不保存計算輸入，所以之後用 calculate_metrics 算出本益比等數值的 Agent v2 報告，發布時這一項都可能被判缺來源。要從根本修需要改 `agents/research_graph.py`（第二段鎖定中），只能在 60 run 跑完後另議；正式實驗不發布報告，不受影響。
- **待組長決定**：B 核對對應結果後，第 3 批是否只發布 2454（組長端建議：發布 2454，補上「三份研究 PDF」缺的聯發科；第 3 批 2317 不發布，2317 已有第 1 批的已發布報告）。

## 44. 2026-11-16 正式實驗第 1 天；執行紀錄改為盲評結束前不推上 GitHub

- **第 1 天**（排程 fintech-formal-v2-daily）：19:34–19:40 執行 6 run，進度 6／60；成功 2、證據不足 4；沒有 runner_error、沒有 paused_quota；測試通過。執行時的 commit 1d5619a（含 A 的 PR #48，只改網站與測試；被鎖定的 14 個檔案不變，嚴格核對通過）。
- **發現的問題**：排程原本每天把 `evaluation/formal/runs-v2.jsonl` 推上 GitHub。每一列有案例、模式、狀態與停止原因；盲評匯出的答卷有案例與狀態。評分者兩相對照，可以推出部分答卷是哪個模式，盲評就失效。
- **組長決定**：
  1. 11/17 起排程不再 git add／commit／push；執行紀錄留在組長 Mac，B、D 都交出評分、公開對照表之後，60 列一次推上 GitHub。其餘步驟不變（pull、狀態、執行、狀態、測試）。另外 pull 失敗（例如網路）時改為照樣執行：被鎖定的程式不需要更新，執行前的嚴格核對照常把關；排程沒有緩衝日，不因 pull 失敗少跑一天。
  2. 第 1 天那一列已在 GitHub（commit 21d3a65），不能刪除（不強制改寫歷史），請 B、D 在兩人都交出評分前不要打開 `evaluation/formal/runs-v2.jsonl` 與「Formal evaluation v2: daily batch」的 commit，並在評分檔註明；不小心看到要告知組長並記錄。
  3. 公開對照表之前，對外文件（W10-L 監控報告、D 的 W10 執行紀錄交付物、決策紀錄）只寫總數，不寫各案例或各模式的結果。
- 影響：保留集的草稿本來就只在組長 Mac（`tmp/formal_v2.sqlite3`），現在執行紀錄也只在這台電腦，`tmp/` 與該紀錄檔不可刪除；Render 不再因每日推送而重新部署。

## 45. 2026-11-17 正式實驗第 2 天被擋；評分規則還原凍結版本、D 的修改另存；AGENTS.md 第六節

- **經過**：D 的 PR #49（11/16 20:00 提交、組長 11/17 12:11 在 GitHub 合併）修改了 `evaluation/d-drafts/rubric-v1-final.md`，這個檔屬第一段凍結（評分規則）。11/17 19:30 排程開跑前的 `--verify --strict` 發現它被改，runner 依設計停止，當天 0 run，進度維持 6／60。
- **D 改了什麼**：凍結版本原本標「待 B 確認」的三處評分做法（第三節：照草稿列出的每一條 fact 主張評分，不另外挑；第四節第 5 點：檢查清單九種錯誤出現在事實主張就標 unsupported；第五節：半對半錯不拆，有錯整句標 unsupported），以及狀態文字。B 11/16 16:14 在群組確認、D 同意。只影響評分，不影響 Agent 執行；當時沒有評分者看過任何正式實驗的輸出。
- **組長決定接受這些修改並恢復執行**。原訂以 `build_freeze.py --amend` 記為修訂 3，但該指令在第二段鎖定後依設計拒絕修訂（「第二段已鎖定，不可再修訂」）；這是刻意的保護，不修改它。改為：
  1. `rubric-v1-final.md` 還原為凍結版本（hash 與凍結紀錄一致）。
  2. D 的版本原文另存為 `evaluation/d-drafts/rubric-v1-confirmed-1116.md`，檔頭說明來由。評分時第三節、第四節第 5 點、第五節照這一份，其餘照凍結版本（兩份其餘內容相同）。盲評範本的表頭已註明（`scripts/export_for_scoring.py`，不在鎖定清單）。
  3. 60 run 跑完後，由組長決定是否把這一份正式併回凍結版本。
- **補跑**：當天的 Gemini 額度沒有用到（額度日以太平洋時間計，台北 11/18 16:00 前都算 11/17），組長同意當晚手動補跑 6 run，排程 11/18 起照常，10 天的進度不少一天。
- **避免再發生**：`AGENTS.md` 新增第六節，列出到 60 run 跑完前不能改的檔案、需要改時先問組長、送 PR 前自己跑 `--verify --strict`；組員的 AI 協作者會照這份規則。組長合併 PR 前也可以先交組長端檢查。
- **補跑結果**：11/17 19:55–20:01 手動執行 6 run（commit efe04bc，嚴格核對通過），進度 12／60；沒有 runner_error、沒有 paused_quota；測試 528 通過。依第 44 節，執行紀錄留在組長 Mac，不推上 GitHub；對外只寫總數。
- **輸出截斷檢查**（組長 11/17 同意，只讀每次發送的結束原因與輸出長度，不讀草稿內容）：前 12 run 中，3 個 run 的最後草稿格式無效（「不是 JSON 物件」），其中 2 個是輸出達到上限被截斷（MAX_TOKENS），1 個正常結束但輸出不是合格 JSON。其中 1 個截斷的停止代碼記為 researcher_insufficient（已知限制第 3 點：截斷不另標停止代碼）。結果分析時，「格式失敗」要和「判定證據不足」分開計算；各模式的分布在公開對照表後才寫。
