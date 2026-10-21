# W06 閘門（W06-L）— 草稿，10/23 定稿

狀態截至 2026-10-21。標「待 10/22–10/23」的項目在當天更新。

## 1. W06-L 驗收

| 驗收項 | 狀態 | 證據 |
|---|---|---|
| 8 calls／10 tools／2 rounds 硬限制全過 | ✅（mock） | `tests/test_budget_tools.py`、`test_provider_mock.py`、`test_research_graph.py`（test_budget_exhaustion_never_skips_review、test_parallel_calls_beyond_two_are_skipped 等） |
| resume 保留累計 | ✅（mock） | test_crash_mid_run_resumes_from_checkpoint_without_resetting_budget、test_daily_quota_pauses_and_resumes_later |
| critical 未解決不成功發布 | ✅ | test_rules_override_model_pass_then_bounded_revision、test_budget_exhaustion_never_skips_review；`publication_status` 一律 draft |
| 依 required_evidence 回 Researcher，最多 2 輪 | ✅ | 修正輪為精簡新對話（W05） |
| cancel／timeout／lease 恢復，預算不歸零 | ✅ | cancel：test_cancel_*（2026-10-21 新增）；timeout：test_simulated_tool_timeout_*；lease：test_expired_lease_* |
| 驗證失敗後不重複發布 | ✅ | test_finished_job_is_not_rerun_or_republished |
| 10/23 前明列 F06 決定 | ⏳ 待組長 | 見第 4 節 |

## 2. N01–N03、N07 核對（D 的驗收矩陣）

| 項目 | 狀態 | 說明 |
|---|---|---|
| N01 季度／YTD／TTM／年度 | 🟡 | TTM 連續四季已修（20d2e9a）；B 的 `tests/test_tool_fixtures.py` TR-14（content_hash）仍失敗，待 B |
| N02 同業與產業參照 | 🟡 | B 已鎖同業快照（2454 主體、2330 排除，P/E 23.23、P/B 6.29）；A 的 `test_comparison_rules` 因資料更新失敗，待 A；live 尚未跑到 peer_comparison |
| N03 收藏與已發布清單 | 🟡 | A 的收藏與清單骨架存在；已發布清單需 W07 的 report 版本，現為 mock |
| N07 Researcher 選工具、Reviewer 發現矛盾後補查 | ⏳ 待 10/22–10/23 live | mock 全過；10/21 第一批 6 案（v1.4）全為 insufficient，原因是 Researcher 不讀快照來源。已校準 prompt（researcher-v1.2.1）並修 2 個串接問題；受每日 J=6 限制，10/22 重跑 6 案、10/23 跑 4 案 |

## 3. 凍結（方法／工具／案例）

- 案例：30 案結構符合第 06 章（5 類 × 2 開發 + 4 保留，每類三檔各 2）；保留集 20 案 SEAL hash 相符（10/21 驗證），組長不讀保留集內容。
- **B 的 10/20 凍結已失效**：`scripts/build_freeze.py --verify` 顯示 20 個檔案在凍結後被修改（B 10/21 的提交與組長 W06 修正）。
- 計畫：10/23 live 結束、model 定案後，由組長凍結 prompt、工具、契約與 model 版本，並請 B 以 `build_freeze.py` 重新產生凍結紀錄。凍結後只修 bug，若影響實驗，依第 06 章另發版本。
- 待 B：`data/manual/announce_times.csv`、`balance_overrides.csv`、`macro.csv` 未上傳，快照無法由他人重建。

## 4. F06（2D 關聯圖）判定 — 待組長 10/23 決定

第 04 章：W06 的 Agent 閉環、F01/F02 基礎回歸、來源凍結任一未過，就登記 F06 延後。

| 條件 | 10/21 狀態 |
|---|---|
| Agent 閉環 | 待 10/22–10/23 live |
| F01/F02 基礎回歸 | 未全過（TR-14、A 的比較測試） |
| 來源凍結 | 已失效，10/23 重做 |
| 圖資料 | `graph-approved.json` 3 點 2 線 |

**建議：登記 F06 延後**（轉後續版本）。C/E 仍完成已核實資料表與設計稿；不挪用正式實驗、PDF 或 12/11 定稿時段。

## 5. model 決定 — 待 10/23

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
