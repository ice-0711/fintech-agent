# 研究 job 狀態機 v1（W06-L）

依實際程式整理（`agents/store.py`、`agents/worker.py`、`agents/research_graph.py`、`agents/budget.py`），2026-10-21。

## 1. status（job 生命週期）

```
            create (冪等)                    claim（lease 60s，一次只一個 running）
  [請求] ─────────────▶ queued ───────────────────────────────▶ running
                          │  ▲                                    │
             cancel ──────┤  │ resume_after 到期 / requeue          │ 圖執行結束或預算停止
                          ▼  │                                    ▼
                     cancelled  paused_quota ◀── daily_quota / rate_limited / provider_429 / quota_unknown
                                     │
                                     └─ cancel → cancelled

  running 結束時：
    succeeded              Reviewer 最終決定 pass（dual）或 single 模式產出草稿
    insufficient_evidence  Researcher 回 insufficient、Reviewer insufficient、修正輪用完仍有 critical、
                           call_limit / token_limit / reserved_for_review / input_too_large 等預算停止
    timed_out              主動時間 > 180 秒（模型 + 工具，含模擬逾時）
    cancelled              執行中收到取消，在下一步開始前停止
    failed                 非預期程式錯誤（worker_error）
  lease 過期（worker 當掉）：running 由下一個 worker 接手，checkpoint 與預算延續（lease_recovered）
```

- 終態：succeeded、insufficient_evidence、timed_out、failed、cancelled。終態不會再被 claim、不會被 cancel 改寫；同一 idempotency_key 重送回傳同一個終態 job（不重跑、不重複發布）。
- paused_quota 有 `resume_after` 者到時自動回到可執行；`quota_unknown` 沒有 `resume_after`，只能 `store.requeue`。

## 2. stage（研究流程）

| stage | 誰 | 進入條件 | 離開 |
|---|---|---|---|
| research | Researcher | job 建立 | 輸出草稿 → review（dual）或 finished（single／insufficient） |
| review | Reviewer | Researcher 草稿 status=draft | pass/insufficient → finished；revise → revision |
| revision | Researcher | Reviewer revise，且補查輪 < 2、剩餘發送 ≥ 2 | 修正草稿 → review |
| finished | — | 任一結束 | — |

## 3. 預算與硬限制（共用一個 BudgetGate）

| 限制 | 值 | 超過時 |
|---|---|---|
| 模型發送（含失敗、格式重試、網路重試） | 8 | call_limit → insufficient_evidence |
| 初次研究 | 前 4 次；第 5 次保留覆核 | 第 4 次強制只能輸出文字；格式重試不得占用第 5 次 |
| 工具呼叫 | 10；同工具同參數 2 次；每輪最多執行 2 個 | 回 refused／skipped 給模型 |
| 補查輪 | 2 | unresolved_critical → insufficient_evidence |
| 每次輸入 | 3,000 token（預估：非 ASCII 1 字 1 token、ASCII 3 字 1 token） | 舊工具結果壓成摘要；空間不足不給工具；仍超過 → input_too_large |
| 每次輸出 | 1,500（含 thinking） | — |
| 每 job token | 40,000（先預留後發送） | token_limit |
| 主動時間 | 180 秒（模型 + 工具） | timed_out |
| 專案 | RPM/TPM 80%、RPD 80%、每日 job 上限 J | paused_quota（自動恢復） |

## 4. checkpoint（每一步寫入，經 fenced lease）

`job.checkpoint` = next 節點、Researcher／Reviewer 對話、observations（含摘要）、draft、reviews（每輪 model／rules／final）、format_retries。worker 重啟後由 `checkpoint.next` 繼續，`calls_used`、`tokens_*`、`tool_calls_used`、`supplement_rounds`、`active_seconds` 不歸零。

## 5. 發布

本狀態機不發布。`publication_status` 一律為 `draft`；人工核准、不可變 report 版本與 Storage PDF 在 W07 加入，模型沒有發布權限。
