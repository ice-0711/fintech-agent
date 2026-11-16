# 回放清單加入送 task 的兩批紀錄；三條示範路徑定案（11/15）

- 負責：A（陳柏臣）｜日期：2026-11-15
- 分支：`codex/A-replay-task-batches`（基於 main 503b8be），程式 commit 01a1789
- 依據：組長 11/14、11/15 訊息；決策紀錄第 31、34、35、37、38、40 節
- 只改 `research_ui/`、`static/`、`tests/`、`scripts/replay_demo_media.py`、`design/`、`media/`、`demo/`。
  第二段鎖定清單（`agents/`、`scripts/dev_traces.py`、`scripts/formal_runs.py`、`data/`、`fixtures/`、`evaluation/` 案例檔）都沒有動；`evaluation/dev-cases.json` 只讀取資料截止時間與快照編號。

## 一、加入的紀錄

| 檔案 | 條件（照組長寫法） | 筆數 | 註記 |
|---|---|---|---|
| `agent/calib-v2-rules-check-1115-dual.json` | 補股價後・題目送 task・11/14 覆核規則修正後（第 35、37、38 節） | 4 | 沒有註記。CASE-22 證據不足照實列出，不加註、不當示範 |
| `agent/calib-v2-task-rehearsal-1114-dual.json` | 補股價後・題目送 task・11/14 覆核規則修正前（第 35、37、38 節） | 4 | CASE-04 加註「覆核程式誤判，規則已修」（第 35 節），比照 11/12 那筆 |

回放清單由 28 筆變成 36 筆。

## 二、分組

下拉選單由 2 組改成 3 組，順序是新到舊：

1. **Agent v2・題目送 task**：8 筆，11/14、11/15
2. **Agent v2・題目送 variant**：17 筆，11/08–11/12
3. **開發期（v1 之前）**：11 筆

11/14 起題目改送 task，不再送變體名稱（第 31 節），條件和更早的紀錄不同，所以分開成兩組，不放在同一組裡比較。每筆回放的最上方仍然寫 Agent 版本、prompt 版本與條件。

## 三、三條示範路徑

三筆都在「Agent v2・題目送 task」這一組，示範時不混用兩種條件。清單上會標 ★，回放畫面上也有「示範：…」標籤。

| 路徑 | 回放 | 內容 | 誰定的 |
|---|---|---|---|
| ① 正常通過 | `calib-v2-rules-check-1115-dual:CASE-04` | 2330，第 1 輪通過。收盤價 2,480、TTM EPS 86.28（列出四季）、本益比 28.74 引用 calculate_metrics 的結果，Reviewer 另外重算一次 | 組長（11/15） |
| ② 覆核要求補查後修正 | `calib-v2-task-rehearsal-1114-dual:CASE-19` | 2330，第 1 輪退回修正（c2 critical）→ 改稿 → 第 2 輪通過。草稿指出幣別混用，沒有硬算淨利率 | 組長（11/14） |
| ③ 資料不足停止 | `calib-v2-rules-check-1115-dual:CASE-15` | 2454，Researcher 判定法說會正文讀不到，沒有補造內容，列出 2 個下一確認訊號後停止 | A（組長說兩筆都可以，由 A 決定） |

**③ 選 11/15 CASE-15，不選 11/12 CASE-18 的理由**：

- 三條路徑可以全部用同一組條件（送 task、修正後的覆核規則），講稿不必解釋為什麼有一筆的條件不一樣。
- 這筆也正好展示「不補造、列下一步」。

**原本的 CASE-15（11/08）與 CASE-18（11/12）**：留在「送 variant」那一組，不再標示範。

**講稿要照實寫的地方**：

- 三筆都是 **REPLAY**，也就是組長 Mac 上真實執行的紀錄，不是現場執行（第 34 節）。
- 「通過覆核」不等於「正確」。
- ② 的第 1 輪細節沒有保存在紀錄檔裡，畫面會寫「此輪細節未保存在紀錄檔」。只保存了退回的決定，以及被列為 critical 的主張編號 c2。

## 四、前後對照與測試

| | 修改前（main 503b8be） | 修改後 |
|---|---|---|
| 回放筆數 | 28 | 36 |
| 分組 | Agent v2／開發期 | Agent v2・題目送 task／Agent v2・題目送 variant／開發期 |
| 有「退回修正後通過」的 Agent v2 紀錄 | 0 筆 | 1 筆（11/14 CASE-19） |
| 示範路徑標示 | 沒有 | 3 筆標 ★ |

`tests/test_w09_ui.py` 改為 8 項，新增檢查以下幾點：

- 送 task 的檔案只出現在 task 組。
- 每一組在清單裡連續排列，不會穿插。
- 兩批紀錄的條件文字和組長給的完全相同。
- 三條示範路徑都在同一組，而且結果和紀錄相符：通過；退回後通過；Researcher 判定不足。
- 加註的只有 11/12 與 11/14 兩筆 CASE-04。11/15 的 CASE-04 與 CASE-22 都沒有註記。

全套 `pytest`：**503 passed**。

## 五、素材（本機，REPLAY）

| 檔案 | 內容 |
|---|---|
| `demo/sample-replays-v2-task.mp4` | 52 秒。三條示範路徑依序回放：版本與條件 → 覆核紀錄與草稿。每格畫面上方標「本機（非 Render）、01a1789、2026-11-15、REPLAY 非 LIVE、無模型呼叫」 |
| `media/w10/a-demo{1,2,3}-*-{status,review}-{1440,390}.png` | 三筆回放的狀態與覆核畫面，桌面與手機各 1 張，共 12 張 |

清單登錄在 `media/v12-screenshots-manifest.csv`。

Render 要等這個分支合併部署後才看得到；部署後由 A 上線檢查一次。

## 六、實際執行的命令（皆 exit 0）

```
python -m pytest -q                                            # 503 passed
python scripts/w07_demo_store.py /tmp/w10/store
REPORT_DB_PATH=… REPORT_STORAGE_DIR=… RESEARCH_UI_MOCK=1 RESEARCH_UI_MOCK_DB=… gunicorn web_app:app --workers 1 -b 127.0.0.1:5109
python scripts/replay_demo_media.py --base http://127.0.0.1:5109 --shots media/w10 --video tmp/replay-video
python -c "import scripts.w09_record_sample as w; w.caption('tmp/replay-video', 'demo/sample-replays-v2-task.mp4', '<標籤列>')"
```
