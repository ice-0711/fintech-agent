# W06 閘門（W06-L）— 2026-11-06 定稿

原稿狀態截至 2026-10-21；第 2 節與第 9 節於 2026-11-06 依三模式校準 v1（D 評分、B 交叉評分、組長簽核）更新。

## 1. W06-L 驗收

| 驗收項 | 狀態 | 證據 |
|---|---|---|
| 8 calls／10 tools／2 rounds 硬限制全過 | ✅（mock） | `tests/test_budget_tools.py`、`test_provider_mock.py`、`test_research_graph.py`（test_budget_exhaustion_never_skips_review、test_parallel_calls_beyond_two_are_skipped 等） |
| resume 保留累計 | ✅（mock） | test_crash_mid_run_resumes_from_checkpoint_without_resetting_budget、test_daily_quota_pauses_and_resumes_later |
| critical 未解決不成功發布 | ✅ | test_rules_override_model_pass_then_bounded_revision、test_budget_exhaustion_never_skips_review；`publication_status` 一律 draft |
| 依 required_evidence 回 Researcher，最多 2 輪 | ✅ | 修正輪為精簡新對話（W05） |
| cancel／timeout／lease 恢復，預算不歸零 | ✅ | cancel：test_cancel_*（2026-10-21 新增）；timeout：test_simulated_tool_timeout_*；lease：test_expired_lease_* |
| 驗證失敗後不重複發布 | ✅ | test_finished_job_is_not_rerun_or_republished |
| 10/23 前明列 F06 決定 | ✅ 延後（10/22） | 見第 4 節 |

## 2. N01–N03、N07 核對（D 的驗收矩陣）

| 項目 | 狀態 | 說明 |
|---|---|---|
| N01 季度／YTD／TTM／年度 | ✅（11/06） | TTM 可由 `period` 判定（10/31）；B 的 TR-14 已修，全套 395 項測試通過；校準 v1 的 53 個事實數值經 B 程式核對全部正確 |
| N02 同業與產業參照 | ✅（11/06） | 同業平均規則 11/02 核定（不同財報期都計入、逐列標季別）；A 的比較測試通過、網站已顯示「同業財報期不同」 |
| N03 收藏與已發布清單 | ✅（11/06） | 已發布清單接真實 `report_versions`；11/02 第一份 LIVE 報告（2317 前瞻第 1 批）已公開 |
| N07 Researcher 選工具、Reviewer 發現矛盾後補查 | ✅（附限制，11/06） | CASE-08 dual（d8884abc）Reviewer 發現來源衝突、退回修正一次後停在證據不足（D、B 判合理）；dual 新規則 10 案 4 案覆核通過（CASE-01、11、22、26）。限制見第 9 節：Researcher 常太早停，且停止理由與執行紀錄不符 |

## 3. 凍結（方法／工具／案例）

- 案例：30 案結構符合第 06 章（5 類 × 2 開發 + 4 保留，每類三檔各 2）；保留集 20 案 SEAL hash 相符（10/21 驗證），組長不讀保留集內容。
- **B 的 10/20 凍結已失效**：`scripts/build_freeze.py --verify` 顯示 20 個檔案在凍結後被修改（B 10/21 的提交與組長 W06 修正）。
- 計畫：10/23 live 結束、model 定案後，由組長凍結 prompt、工具、契約與 model 版本，並請 B 以 `build_freeze.py` 重新產生凍結紀錄。凍結後只修 bug，若影響實驗，依第 06 章另發版本。
- 待 B：`data/manual/announce_times.csv`、`balance_overrides.csv`、`macro.csv` 未上傳，快照無法由他人重建。

## 4. F06（2D 關聯圖）判定 — **組長 2026-10-22 決定：延後**

第 04 章：W06 的 Agent 閉環、F01/F02 基礎回歸、來源凍結任一未過，就登記 F06 延後。

| 條件 | 10/21 狀態 |
|---|---|
| Agent 閉環 | 待 10/22–10/23 live |
| F01/F02 基礎回歸 | 未全過（TR-14、A 的比較測試） |
| 來源凍結 | 已失效，10/23 重做 |
| 圖資料 | `graph-approved.json` 3 點 2 線 |

**決定：F06 延後，轉後續版本**（組長 2026-10-22）。理由：W06 時 Agent 閉環尚在驗證、F01/F02 回歸與來源凍結未在 10/22 全過、核准圖資料僅 3 點 2 線。依第 04 章：C/E 仍完成已核實資料表與設計稿；N06 不驗收並與核心失敗分開記錄；不挪用正式實驗、PDF 或 12/11 定稿時段；成果不得說關聯圖已上線。

## 5. model 決定 — **組長 2026-10-23 決定：維持 gemini-3.5-flash-lite**

`gemini-3.5-flash-lite`（RPD 500，J=6）為有條件選定。10/15 比較：`gemini-3.6-flash`（RPD 20，J=2）會編造工具與參數，未較佳。依 10/22–10/23 的 10 個開發案結果定案；若仍不足，記錄限制，不換付費。

## 6. 組長核定的實作決定（凍結時一併記錄）

1. 採用 D 的 `claims[].facts`（W05）。
2. 每輪最多執行 2 個工具；接近輸入上限時壓縮舊工具結果、Reviewer 首訊息逐步精簡。
3. token 預估：ASCII 3 字元 1 token（live 實測皆未低估）。
4. model：`gemini-3.5-flash-lite`（待 10/23 定案）。
5. Researcher prompt `researcher-v1.2.1`（10/21 依開發案校準：先讀快照來源、部分缺資料列 unknown）。
6. 總經白名單：CPIAUCSL、FEDFUNDS、TAIEX。

## 7. 影響後續週次的未完成事項

| 事項 | 影響 | 需要誰 | 最晚 |
|---|---|---|---|
| Supabase 測試專案（W02 遺留） | W07 report 版本、Storage PDF、job 持久化全部依賴它；Render 重啟會遺失本機 job | 組長開專案、給 `.env` 變數 | **10/26（W07 開始）** |
| 核准的登入方式 | W07 驗收「核准需登入」；A 的畫面接真 API 也需要 | 組長與 A 決定 | 10/26 |
| 前瞻快照：`build_snapshot_finmind.py` 的 cutoff 寫死 2026-09-30 | 10/30、11/06、11/13 21:00 前瞻 9 份無法建快照 | B 加 `--cutoff`；組長 10/30 執行 | **10/29** |
| B 的 `data/manual/*.csv` 未上傳 | 快照無法重建與核對 | B | 10/23 |
| A 的 3 個畫面測試、B 的 TR-14 | N02、N01 回歸 | A、B | 10/23 |
| Render／Supabase 方案與用量（W01 遺留） | W08 部署與 2GB 驗收 | 組長登入後台 | 10/30 |
| 固定流程（workflow）模式 | W10 三模式實驗 | 組長；D 的 W09 runner | 11/06 |


## 8. 2026-10-23 定案（組長）

- **model**：維持 `gemini-3.5-flash-lite`（3.6-flash 同樣編造工具、RPD 僅 20）。
- **開發結果**（v1.5，16 次 live）：系統面無錯誤、預估從未少算、無錯誤數字通過、無越權工具；尚無一案走到覆核通過。最近一次 CASE-01 草稿數字與原文完全一致，卡在 Reviewer 最後一回合仍要求工具，已改為最後一回合不宣告任何工具（31eea4f，mock 通過）。
- **凍結分兩段**：
  1. 10/23 凍結案例、分組、資料與評分規則（B 重跑 `scripts/build_freeze.py`）。
  2. Researcher/Reviewer prompt、Agent 程式與 thinking 等級：10/26 以開發集 live 再驗證一次後鎖定，最遲於 W09（手冊鎖實驗版本週）前；若 Reviewer 仍無法完成覆核，依 model-config.md 預設備案把 thinking_level 由 minimal 改為 low 再驗一次。調整只用開發集，保留集不動。


## 9. 2026-11-06 三模式校準 v1 簽核（組長）

- **範圍**：開發集 10 案 × 3 模式 = 30 列（`evaluation/d-drafts/dev-runs-calib-v1.jsonl`；dual 只用 10/31 新規則的 10 列，舊 dual 8 列與 10/27 CASE-01 single 失敗列不計分）。
- **評分**：D `evaluation/d-drafts/calib-v1-scores-D.txt`；B 交叉評分 `evaluation/d-drafts/calib-v1-scores-B.md`：30 列標籤全部一致，53 個事實數值全部正確（1 個由人工確認，原因是中文金額含空格，11/06 已修）。
- **組長裁決（11/03）**：obs-* 引用算可解析；CASE-19 依 `allow_insufficient=False` 選證據不足判不符合預期行為；S28 依凍結快照改回 supported。S10、S15 備註中「待組長裁決」以此為準。
- **結論**：沒有任何錯誤數字被當成事實寫進覆核通過的報告；主要問題是**該答的案例停在證據不足**（CASE-04、CASE-19 的 `allow_insufficient=False` 都選了不足），而且**停止理由常與執行紀錄不符**：S30（CASE-04 說價格工具無資料，未呼叫）、S17／S27（CASE-26 說逾時，未發生）、S18（CASE-15 說快照截斷，實為系統壓縮舊結果）、S20（CASE-18 說無法再呼叫工具，預算尚有 4 次）。
- **後續**：W09 鎖定前是否修正 Researcher，見 `handoff/W09-researcher-fix-proposal.md`（待組長決定）。
- **簽核**：組長 2026-11-06 簽核校準 v1（W06-D）。
