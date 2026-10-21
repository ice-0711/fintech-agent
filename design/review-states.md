# W05-A｜覆核問題與補查狀態 UI

- 任務 ID：W05-A（原排程 10/12–10/16，2026-10-21 補做）｜驗收人：組長
- 分支：`codex/W05-A-review-risk`｜前置：W04-A ✓（PR #2 已合併）、W05-L ✓（組長 10/15 Researcher→Reviewer 編排已在 main）

## 1. 這週做了什麼（白話）

研究工作台多了一塊「覆核與修正」面板。它回答三個問題：

1. **Reviewer 退了哪一項？**每一輪列出最終決定（通過／退回修正／資料不足）、模型與確定性規則各自的決定，以及每個問題的主張編號、嚴重度（critical／minor）、原因、要補什麼證據、是誰提出的（模型、規則或兩者）。點主張編號會跳到草稿裡那一條並閃一下。
2. **改了什麼？**草稿每一版都保留（v1、v2…），切換版本看得到每條主張是「新增／修改／刪除／未變」，修改的會列出改了哪個欄位和修改前的文字。
3. **能不能發布？**面板底部有「核准發布」。覆核沒通過時按鈕停用；通過時按下去伺服器一律回 403「需要登入的核准人（W07 開放）」，畫面照實顯示沒有權限。研究工作台本身永遠不能發布。

## 2. 資料從哪裡來

| 來源 | 標示 | 內容 | 怎麼產生 |
|---|---|---|---|
| MOCK job | MOCK | 新情境 `revise_then_pass`：草稿 v1 把單季 EPS 寫成 TTM（**標明是測試案例**）→ Reviewer 第 1 輪退回 c2（critical）→ Researcher 用 `get_financial_snapshot` 補查 → v2 → 第 2 輪通過 | 模型決策是預錄；工具步驟執行 B 的真實工具；v1、v2 的數字由工具輸出帶入（測試核對） |
| REPLAY | REPLAY | 組長保存的 11 筆 **live** 執行紀錄（`agent/*.json`，Gemini 自己選每一步） | 只讀檔案，0 次 LLM。畫面標示紀錄檔、commit、產生時間、模型 |

REPLAY 的限制照實顯示：紀錄檔只保存最後一版草稿和最後一輪的完整問題，較早輪次只有決定與 critical 主張編號。

資料格式對齊組長的 `agents/research_graph.py`：`job.checkpoint.reviews[] = {round, model, rules, final}`。所以 W07 接上正式 job 庫時，面板不用改。

## 3. 空覆核狀態（每一種都說明原因）

| 情況 | 畫面文字 |
|---|---|
| single 模式 | single 模式沒有 Reviewer，本 job 不會有覆核紀錄。 |
| 還在研究 | Researcher 還在研究，草稿完成後才會進入覆核。 |
| Researcher 判定資料不足 | Researcher 判定資料不足並停止，沒有送出可覆核的草稿，所以沒有模型覆核。 |
| 覆核前就暫停／逾時／失敗／取消 | job 在覆核前停止（stop_reason），沒有覆核紀錄。 |

## 4. 驗收自查

| 驗收項 | 結果 | 證據 |
|---|---|---|
| 能看出哪一項退件 | ✓ | 問題表逐列主張編號＋嚴重度＋要補的證據；`test_revise_then_pass_keeps_every_draft_and_points_at_the_rejected_claim`、REPLAY CASE-04 測試 |
| 不覆蓋舊草稿 | ✓（MOCK）／部分（真實 job） | MOCK 的 v1、v2 都保留並可比較。**組長的 graph 目前只保存最新草稿** → CR-A04 |
| 不足狀態有具體缺口 | ✓ | 每個問題列 `required_evidence`；空覆核列原因；`test_empty_review_states_say_why` |
| 低資料風險不暗示股價安全；風險文字經 B/D 核對 | 文字已固定在畫面；**B/D 尚未核對** | 見 `ui/v12-risk-state-cases.md` |

## 5. CR 建議（未經組長同意不實作）

- **CR-A04**：`ResearchRun` 每次產生草稿時 append 到 `checkpoint["drafts"]`（目前 `self.draft` 會被修正版覆蓋）。一行改動，UI 已支援；沒有它，真實 job 的「不覆蓋舊草稿」只能看到最後一版。
- **CR-A05**：`job_events` 的 `review` 事件加上 `issues` 摘要（目前只有 critical 主張編號），REPLAY 才看得到每一輪的完整問題。

## 6. 測試（2026-10-21 實跑）

`.venv/bin/python -m pytest -q tests/test_research_ui.py tests/test_review_risk.py` → 65 passed。
全套 `pytest -q tests`：A 的測試全過；另有 11 個非 A 的失敗（見交付紀錄）。
