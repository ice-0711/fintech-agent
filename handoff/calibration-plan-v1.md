# 三模式校準計畫 v1（W06-D 簽 v1 用）— 組長 2026-10-24 核定

開發集 10 案 × 3 模式（single／dual／workflow）= 30 個 job。每日上限 J=6，所以每天跑 2 案 × 3 模式，共 5 天。只用開發集，不碰保留集。

| 天 | 日期（台北） | 案例 | 執行方式 |
|---|---|---|---|
| 1 | 10/28（三）20:00 | CASE-01、CASE-08 | 組長在對話中做：先實作 workflow 模式，live 驗證 Reviewer 最後回合修正，再跑 |
| 2 | 10/29（四）16:30 | CASE-04、CASE-11 | 排程 `fintech-calib-day2` |
| 3 | 10/30（五）16:30 | CASE-15、CASE-19 | 排程 `fintech-calib-day3` |
| 4 | 10/31（六）16:30 | CASE-18、CASE-22 | 排程 `fintech-calib-day4` |
| 5 | 11/01（日）16:30 | CASE-26、CASE-29 | 排程 `fintech-calib-day5` |
| 6 | 11/02（一）16:30 | CASE-01、CASE-08（只重跑 dual） | 排程 `fintech-calib-day6`，跑完匯出給 D |

- **為什麼排 16:00**：Gemini 的每日額度在太平洋時間午夜重置，10/27～10/31 這段是台北 15:00。排在 16:30（11/01 起美國冬令時間，重置改為台北 16:00），每天各落在不同的額度日，不會互相卡到 J=6。
- **指令**：

  ```bash
  .venv/bin/python scripts/dev_traces.py --live --db calib_v1.sqlite3 --modes single,dual,workflow --cases <兩案> --out calib-v1-day<N>.json
  ```

  所有 job 存在同一個 `tmp/calib_v1.sqlite3`，J 會跨天累計。
- **匯出**：第 5 天執行 `scripts/export_dev_runs.py --db tmp/calib_v1.sqlite3 --out evaluation/d-drafts/dev-runs-calib-v1.jsonl`，交 D 評分並簽 v1。原本 18 筆 dual 的 `dev-runs.jsonl` 保留不動。
- **啟用條件**：排程預設停用。第 1 天 workflow 模式完成、測試通過、live 驗證沒問題後，組長才啟用第 2～5 天的排程。
- **延後規則**：電腦沒開，當天那批就不跑，也不補跑、不一天跑兩批，順延一天。若 Reviewer 仍無法完成覆核，依 `model-config.md` 把 thinking_level 改為 low，再用開發集驗證一次（約多 1 天）。最晚 11/06（W09 鎖版前）完成。
- **CASE-26（第 5 天）**：開發快照中沒有可被搜尋到的證據，模型不會去讀 `ev-2317-2026q2-consolidated`，所以 live 測不到工具逾時。組長 2026-10-24 決定不改快照（以免升 cases-v2），結果註明「此案未觸發逾時」；逾時處理以離線測試 `test_simulated_tool_timeout_*` 為證。
- **10/26 校準開跑前一併合併**：覆核規則 basis_unspecified（B 建議，CASE-11-flawed 應判 revise）、CR-W06 保留集防護（snapshot.py）。兩者都屬第二段，校準 30 筆全部使用合併後的版本。
- **前瞻第 1 批**（10/30 21:00 建快照）是另一件事，使用 FinMind，不佔 Gemini 額度。

- **2026-10-27 順延一天**：10/26 組長未上線，第 1 天改在 10/27 晚上（太平洋時間仍為 10/27），第 2～5 天順延為 10/28～10/31。
- **2026-10-28 實際執行**：10/27 第 1 天因 Gemini 403（原 key 的專案失去免費層）只跑 1 個 job 即停止（failed，見 `handoff/quota-test-log.md`）；10/28 換成 Default Gemini Project 的 key 後重跑第 1 天 6 筆。
- **第 1 天發現**：dual 兩案 Reviewer 都完成覆核，但 `decision_summary` 超過 120 字，格式重試後仍超過，被判「輸出不合格」→ insufficient。已改為摘要超長即截短並記 `review_normalized` 事件，結論與 issues 驗證不變（commit 見下）。single／workflow 不經 Reviewer，不受影響。
- **第 6 天**：重跑 CASE-01、CASE-08 的 dual（2 筆），之後才匯出。匯出含 31 列以上：10/27 失敗 1 筆（基礎設施）、第 1 天修正前 dual 2 筆，以 `repo_commit` 區分，交 D 時註明。
