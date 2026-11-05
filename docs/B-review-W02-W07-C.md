# B 核對：C 的 W01–W07 文稿技術事實（第二輪）

- 核對人：組員 B｜日期：2026-11-01｜基準：`origin/main` ee7462b（C 的 PR #14、#15 已合併）
- 範圍：C 標「待 B 核對」的 14 份文件。B 只核**技術事實與數字**，文字由組長核准；Agent 狀態、prompt、trace 屬組長，R04／R05 對應屬 D。
- 結論：**沒有錯誤數字**。需要補的只有 4 處（第二節），`glossary.md` 的「B 核對」欄已由 B 填好。

---

## 一、逐份結果

| 文件 | 結果 | 說明 |
|---|---|---|
| `docs/motivation-v1.md` | ✅ | 第一節「學期初基線」B 已用固定版本核對（見第三節）。第三節表中兩列「B 的核對檔未涵蓋」現在都可改為通過：沿用 Python/Flask、FinMind/FRED、Supabase、DCF、matplotlib、fpdf2（`requirements.txt` 都在）；只讀 0 次 LLM 有離線測試 `test_public_reads_make_no_llm_calls`（D `evaluation/e2e-w07.md` 第五節） |
| `docs/v12-motivation.md` | ✅ | F06、60 次的寫法已修正 |
| `W01-meeting.md` | ✅ | 第 5 項「提出人待註明」：提出人是 **B**（`docs/B-review-W01-C.md` 第三節，2026-10-31），依據 `docs/CR-W05-holdout.md`。第 4 項「同時 1 job」：組長 11/01 已確認，`agents/store.py` 有強制 |
| `docs/method-data-v1.md` | ✅ | 第五節工具說明（五種狀態、15 秒逾時、Reviewer 四工具）、第六節 null／0／NA 都與程式和 `data-contract.md` 第 7 條一致。建議補 1 處：第二節總經列補「前瞻批次的總經放 `data/manual/forward/`」 |
| `docs/v12-quarterly-peer-method.md` | ✅（補 1 處） | 公式、DCF 參數、2317 無法判定、年度 PER、品質風險都正確。**第六節需補**：「2379、3034 是否必須與 2454 同一財報期才計入同業平均，待組長核定」。手冊 F02 寫「各自財報期與來源明示」，B 的 calculator 不篩財報期，A 的網站同業表只算同季，兩者不一致（B `research/forward-batch-1-audit.md` 第四節） |
| `glossary.md` | ✅ 已填 | B 已逐項填寫「B 核對」欄；1 項需補註（同業平均，同上）；Agent 與發布相關 10 項標「非 B 範圍」 |
| `docs/v12-method-chapter.md` | ✅（補 1 處） | 3.2–3.4、3.7–3.9 的 B 事實都正確。3.4 同業比較建議與上面同樣補註財報期規則。3.9 表「六工具 277 項測試（10/28）」是當時數字，若要更新可加「W08 另有安全測試 41 項、估值重算 5 項（`tests/test_w08_safety.py`、`tests/test_audit_forward_valuation.py`）」 |
| `docs/v12-website-report-section.md` | ✅ | 三份報告版本、hash 前 16 碼與 manifest 一致。第八節「B 以新版報告重跑稽核」**B 已完成**：`data/v12-report-audit.csv` 的 W7A-001～039 已改指向 915bb95c、d407e7cc、a520d5cc，**39 項全部 pass**（原 3 個 fail 與 2 個 warn 都已由 A 修正：主張改引用財報快照、PDF 印出基準收盤價） |
| `case-walkthrough-v1.md` | ✅ | TTM 86.28 ＝ 17.44 ＋ 19.51 ＋ 22.08 ＋ 27.25（2025Q3–2026Q2），與快照相同 |
| `docs/v12-agent-case.md` | ✅ | 單季 27.25、TTM 86.28 與快照相同；1–6 月累計 49.33 ＝ 22.08 ＋ 27.25 |
| `docs/method-researcher.md`、`docs/method-reviewer.md`、`docs/v12-reviewer-cases.md` | ✅（B 部分） | 四工具、預算 8／10／2／180 秒、2330 不入同業平均（合成驗算 15.0 vs 26.67）都正確。狀態命名與 R04／R05 對應請 D 核 |
| `docs/literature-cards.md` | 補 R08 | 見第四節 |

---

## 二、需要 C 補的 4 處

1. `docs/v12-quarterly-peer-method.md` 第六節、`docs/v12-method-chapter.md` 3.4：補一句「組長 2026-11-02 核定：2379、3034 不同財報期也都計入，逐列標財報季別，財報期不同時註明（`handoff/decisions-2026-10.md` 第 11 節）」。（11/03 更新：原本寫「待組長核定」，組長已核定；`glossary.md` 已由 B 改好）
2. `docs/method-data-v1.md` 第二節：總經列補前瞻檔位置 `data/manual/forward/`。
3. `docs/motivation-v1.md` 第三節：兩列「B 的核對檔未涵蓋」改為「B 通過（2026-11-01）」，依據見上表。
4. `W01-meeting.md` 第 5 項提出人填「B（2026-10-31，`docs/B-review-W01-C.md`）」；第 4 項日期填「組長 2026-11-01 確認」。

---

## 三、學期初基線核對（R08 固定版本 53816d4）

B 直接讀固定 commit 的檔案（不是 main 分支）：

| 項目 | 固定版本內容 | 文稿敘述 |
|---|---|---|
| commit | `53816d4fb7d178d309cb556bd55fe9f49533e7e5`，2026-06-15 09:49:52 +08:00，「Add mobile project summary HTML」 | literature-cards 寫「commit 日期未讀到」，可補 |
| `PROJECT_STATUS.md` | 最後更新 2026-05-30；Render Free 512MB；公開版預設略過 PDF，本機可產出 | ✅ 與痛點 3 一致 |
| `requirements.txt` | pandas、matplotlib、fpdf2、Flask、gunicorn、supabase、python-dotenv、requests、PyMuPDF、FinMind、fredapi | ✅ 沿用清單正確 |
| 財報處理 | `report_downloader.py` 把 FinMind 季度損益表**加總成年度值**；全專案沒有 available_at、captured_at、TTM、ytd 的處理 | ✅ 痛點 1「季度、TTM、公告可得性待實作」正確 |
| DCF | `valuation_agent/dcf_model.py` 年度 5 期折現 | ✅ |
| 來源版本、hash、job、人工核准 | 沒有 | ✅ 痛點 2 正確 |
| LLM | 主流程 `financial_analyzer.py` 為規則式、不需模型；另有選用的 `fundamental_agent/gemini_analyzer.py`（gemini-2.5-flash 單次摘要） | 文稿未提，可不寫；若寫「基線沒有 Agent」是正確的（只有單次摘要，沒有工具選擇與覆核） |

---

## 四、文獻卡 R08 與 RQ1／RQ3 文獻

- R08「研究問題」可填：「不適用（程式基線）」；「年份／查閱日」可填上表 commit 日期；「方法摘要」可改用第三節表格（已讀固定版本）。
- RQ1、RQ3 是否要另找學術文獻：手冊第 08 章寫明「指定參考資料（C 不用自行擴充書單）」，固定 R01–R08 共 8 筆。**B 建議不另增文獻**。RQ1、RQ3 的方法依據寫成「本專題資料契約與組長核定事項」，並在限制段說明「R01–R08 沒有直接對應資料一致性的學術文獻」。若組長要求補充，B 再提供 MOPS 公告規範等官方來源。