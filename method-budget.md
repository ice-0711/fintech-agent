# W05-C 預算、重試與停止（method-budget）

- 任務 ID：W05-C｜版本：v2（2026-10-31 依組長程式文件修訂）｜狀態：**草稿，待 B 核對、組長核准**
- 依據：組長 `handoff/state-machine-v1.md` 第 3 節（2026-10-21，依實際程式整理）、`agents/budget.py`、`handoff/v12-scope-quota.md` 第 4 節。B 已核對 8／10／2／180 秒與程式值相符（`docs/B-review-W01-C.md`）。

## 一、每個 job 的硬限制

所有限制共用同一個預算關卡（BudgetGate）。

| 限制 | 上限 | 超過時 |
|---|---|---|
| 模型發送 | 8 次，**包含 Researcher 與 Reviewer 全部角色，以及失敗、格式重試、網路重試** | 停止，job 為 insufficient_evidence（call_limit） |
| 初次研究（dual） | 前 4 次；第 5 次保留給覆核 | 第 4 次只能輸出文字，格式重試不得占用第 5 次 |
| 工具呼叫 | 10 次；同一工具、同一參數最多 2 次；每輪最多執行 2 個 | 回覆 refused 或 skipped 給模型 |
| 補查輪 | 2 輪 | 仍有未解決的 critical：insufficient_evidence |
| 每次輸入 | 3,000 token | 先把舊工具結果壓成摘要；仍超過：input_too_large |
| 每次輸出 | 1,500 token（含模型思考） | — |
| 每 job token | 40,000（先預留後發送） | token_limit |
| 主動時間 | 180 秒（模型加工具，含模擬逾時） | timed_out |
| 同時執行 | 一次只有一個 job 在執行 | 其他 job 排隊 |

## 二、重試怎麼算

模型請求失敗後重新發送、或輸出格式不合格而重送，**都算一次模型發送**，與正常發送共用同一個 8 次上限；程式設定每次最多重試 1 次（`agents/budget.py` 的 max_retries）。重試越多，留給補查與覆核的次數就越少。發送前程式會先檢查，若下一次發送必定被拒絕，就不再等待重試（`agents/budget.py`）。

## 三、專案層級的額度

除了單一 job 的限制，整個專案還受 Gemini API 額度限制：每分鐘請求數、每分鐘 token 與每日請求數都只用到 80%；每日研究 job 上限 J 為 6（gemini-3.5-flash-lite，RPD 500）。唯一例外是太平洋時間 2026-10-31 這一個額度日：組長核定校準 job 上限單日開到 20，並以執行參數明確指定；其他日期仍是 J＝6，每個 job 的預算、80% 額度限制、模型與規則都不變（組長 `handoff/decisions-2026-10.md` 第 10 節）。額度用完時，job 暫停為 paused_quota，到時自動恢復；額度未知時不做真實發送（J＝0）（組長 `handoff/state-machine-v1.md`；`handoff/v12-scope-quota.md` 第 4 節）。

這些是**專題內部**的限制，不是 Google 的規定。Google 帳戶的實際額度由組長核實並保存紀錄（R06）。

## 四、停止與不補造

- 預算用完時，系統停止，不再呼叫模型或工具。
- 停止時寫明缺少什麼，**不補造數字**。
- 預算用完也**不會跳過覆核去發布**；研究 job 本身不發布，報告一律先是草稿（組長 `handoff/state-machine-v1.md` 第 5 節；W06-gate 第 1 節測試 test_budget_exhaustion_never_skips_review）。
- worker 中途當掉時，由下一個 worker 接手，已用的發送次數、token、工具呼叫、補查輪與主動時間都不歸零（同上第 1、4 節）。

## 五、人工核准

人工核准發生在研究結束之後的發布階段：組長登入、帶自己看過的報告 hash 核准，hash 不符就不發布。模型沒有發布權限（組長 `handoff/state-machine-v1.md` 第 5 節；A `reports/v12-online-pdf-check.md` 第 5 節）。

## 六、部署限制

Render 2GB 是**計畫**，repo 內設定仍是免費方案 512MB，尚未開通；是否足夠要等 W08 實測，不寫成保證足夠（組長 `handoff/v12-scope-quota.md` 第 4 節）。
