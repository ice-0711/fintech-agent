# A｜W05–W06 交付紀錄與交接（2026-10-21）

> 依工作包「最終回覆固定」五段格式。狀態「待驗收」；組長確認後才改「已完成」。

## 1. 實際產物與連結

分支 `codex/W05-A-review-risk`（基於 main `65656dc`），3 個 commit：

| commit | 內容 |
|---|---|
| `5881186` | W05 後端：`research_ui/risk.py`（±15%、資料品質）、`review_view.py`（覆核輪次、草稿差異）、`replays.py`（REPLAY）、MOCK `revise_then_pass`；比較面板改吃 B 10/21 快照；修復組長閘門列出的 A 測試 |
| `6baf023` | W05 畫面：覆核與修正面板、草稿 v1/v2、核准 403、REPLAY、估值與風險顯示、DCF 敏感度；`design/review-states.md`、`ui/v12-risk-state-cases.md`、`design/w05/` |
| `000f408` | W06：中斷恢復修正、S01–S06 初版截圖、儀表板驗收；`design/research-qa-v1.md`、`ui/v12-dashboard-acceptance.md`、`design/screenshots/S01-S06-v1/`、`design/w06/` |

沒有改組長的 `agents/`、B 的資料或工具；`web_app.py`、`dashboard.html` 未動。

## 2. 逐項驗收結果

| 任務 | 驗收項 | 結果 |
|---|---|---|
| W05 | 能看出哪一項退件 | ✓ |
| W05 | 不覆蓋舊草稿 | ✓ MOCK；真實 job 需 CR-A04 |
| W05 | 不足狀態有具體缺口 | ✓ |
| W05 | 低資料風險不暗示股價安全；風險文字經 B/D 核對 | 文字已上；**B/D 未核對** |
| W06 | 390×844 與 1440×900 無重疊 | ✓（20 張溢出 0） |
| W06 | 過期／回放明確 | ✓ |
| W06 | 重新載入不丟 job | ✓ |
| W06 | 手機無重疊；未核准不公開；四五檔切換不自動重算 | ✓（純讀點擊只有 GET） |

## 3. 來源、測試與版本

- 資料：B `data/financial-snapshots.json`（manifest v1.5-eps-source／v1.6-tw-market）、`data/v12-peer-snapshot.json` v1.7-w04；DCF 參數依 `handoff/decisions-2026-10.md`。
- REPLAY：`agent/researcher-v12-traces.json`（commit 20d2e9a）、`agent/dev-v14-batch1.json`（49bafcd）、`agent/researcher-v12-traces-gemini-3.6-flash.json`。
- 測試（2026-10-21，Python 3.13）：`pytest -q tests/test_research_ui.py tests/test_review_risk.py` → **66 passed**。
- 全套 `pytest -q tests` → 206 passed、11 failed、2 xfailed。**11 個失敗都不是 A 的檔案，在 main `65656dc` 上就已失敗**：
  - `tests/test_research_graph.py` 10 個：測試用的 CASE-01 證據 `ev-dev-01-official` 在 B 10/21 更新 `fixtures/dev/case_fixtures.json`（可得時間改為 08-11）後，對測試的 cutoff 不可得，模擬回應不夠用而 `pop from empty list` → 組長更新測試的 cutoff 或 fixture。
  - `tests/test_tool_fixtures.py::TR-14`：組長閘門已列，待 B。
- 未執行：LIVE Gemini、Render、Supabase。

## 4. 未完成、原因與提供人

| 項目 | 原因 | 提供人 |
|---|---|---|
| ±15%、風險用語、「DCF ≤ 0 → 無法判定」、120 天過期標準 | 需金融口徑核對 | B、D（`ui/v12-risk-state-cases.md` §3） |
| CR-A04：每版草稿存進 `checkpoint["drafts"]` | graph 目前只留最新草稿 | 組長 |
| CR-A05：review 事件存每輪 issues | REPLAY 早輪次細節缺 | 組長 |
| 研究工作台接正式 job API | 授權方式未定 | 組長（10/26 前，閘門第 7 節） |
| S06 真 PDF 畫面 | W07 | 組長 Storage＋A |

## 5. 給組長的交接短訊（草稿，未發送）

> 組長好，我是 A。W05–W06 在分支 `codex/W05-A-review-risk`（3 個 commit），請 review。
> ① 你 W06 閘門列的「A 的比較測試失敗」已修：比較面板改吃 B 10/21 快照，P/E、P/B、YoY、FCF 全部由工具重現且與 B 一致；DCF 照你 10/21 核定（9%／3%／持平 5 年）。
> ② 新增覆核與修正面板（每輪退件項目、草稿 v1/v2 差異、核准按鈕回 403）、REPLAY 你的 11 筆 live 紀錄、估值 ±15% 與資料品質風險、S01–S06 初版截圖。
> ③ 想請你看兩個 CR：A04 每版草稿 append 到 `checkpoint["drafts"]`；A05 review 事件帶 issues。
> ④ 全套測試有 11 個非 A 的失敗：`test_research_graph.py` 10 個是 B 10/21 改了 CASE-01 證據可得時間，你的測試 cutoff 要跟著改；TR-14 待 B。
