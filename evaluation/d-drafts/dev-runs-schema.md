dev-runs.jsonl　欄位說明（草稿）

任務ID：W06-D　狀態：草稿，尚未經 B 與組長驗收
這個檔案一行一個 run（JSON Lines）。目前是空檔，因為還沒有任何真實執行。不能先填數字。

規則 [手冊]
1. 開發 10 案 x 3 模式 = 30 行，成功或失敗都要有一行（429、timeout、failed 也要）。
2. 取不到的值寫 null，並在 note 寫原因，不能寫 0。
3. mock、replay、live 要分開，run_mode 欄位一定要填。
4. 保留案（20 個）不可以出現在這個檔案裡。

欄位 [D初稿]
run_id             字串，匿名編號（給評分者看的），不含模式名稱
case_id            字串，只能是 CASE-01、04、08、11、15、18、19、22、26、29
mode               workflow、single、dual 其中之一（評分者看不到，只有整理表格的人看得到）
run_mode           live、mock、replay 其中之一
model_id           實際使用的模型 ID
repo_commit        執行當下的 repo commit
prompt_versions    researcher 與 reviewer 的 prompt 版本與 hash
status             succeeded、insufficient_evidence、failed 等實際狀態
stop_reason        實際停止原因
model_sends        模型發送次數（含重試），上限 8
tool_calls         工具次數，上限 10
supplement_rounds  補查輪數，上限 2
tokens_in / tokens_out   實際 usage token，取不到寫 null
latency_active_s   主動時間（秒），上限 180
latency_queue_s    排隊時間（秒）
latency_total_s    端到端時間（秒）
error              錯誤訊息或 null（429、timeout 等）
started_at         開始時間（含時區）
note               備註（例如：誰跑的、為什麼缺值）

評分結果不放在這個檔案，放在評分紀錄（見 rubric-v1-final.md 第六節）。
