# W07-B 證據與報告一致性稽核（evidence-audit-w07）

- 任務：W07-B｜確保凍結來源與報告一致；報告欄位一致
- 期間：2026-10-26 至 2026-10-30（10/22 提前開始可獨立的部分）
- 版本：v0.2（2026-10-22；納入組長 10/22 核定：股價 17:30、開發案例 v1.5、F06 延後、2317 不做 FCF 正常化）
- 驗收人：D（財務與證據），組長合併

## 一、五點重述

| 項目 | 內容 |
|---|---|
| 目標 | 三檔研究報告（2330、2317、2454）的引用、季度、比較、DCF 與凍結來源一致；前瞻批次 1（10/30 21:00）的來源與價格口徑凍結 |
| 既有狀態 | 30 案快照已凍結（cases-v1，digest 98af84030d45，事實清冊 V1.9 已逐筆對照 MOPS）；報告 report.json／PDF 由 W07-L 產生，**10/22 尚未存在**（`output/` 只有舊版圖檔） |
| 輸入 | `data/financial-snapshots.json`、`data/v12-peer-snapshot.json`、事實清冊 V1.9、W07-L 的 report.json 與 PDF、MOPS 原文 |
| 交付 | `research/forward-batch-1-sources.json`、`evidence-audit-w07.md`（本檔）、`data/v12-report-audit.csv` |
| 驗收人 | D 檢查財務與證據；組長合併 |

## 二、四個步驟的狀態

| 步驟 | 狀態 | 說明 |
|---|---|---|
| 1. 核對 3 檔報告引用與金融口徑 | ⏳ 等 W07-L | 已用 `scripts/audit_report.py --baseline` 產生 56 項核對基準值（`data/v12-report-audit.csv`）；報告產生後執行 `--report` 自動判定，報告產生後只需填 report_value／pdf_value 並判定 |
| 2. 檢查 cutoff 之前的可得資料 | 🟡 進行中 | 前瞻快照 builder 已能依 cutoff 自動排除尚未公告的季別、總經與證據（見第三節）；10/30 實際確認 |
| 3. 提供前瞻批次來源 ID 與價格口徑清單 | ✅ 草稿 | `research/forward-batch-1-sources.json` v0.1：來源 ID、快照檔名、證據候選、進出場口徑、NA 規則、10/30 檢查清單 |
| 4. 核對網頁／PDF；前瞻 cutoff 資料凍結；交 C 核准敘述 | ⏳ 等 W07-L、10/30 | 前瞻快照於 10/30 21:00 後產生並記錄 sha256；C 的敘述待報告完成 |

## 三、前瞻快照的技術準備（B，最晚 10/29）

W06 閘門列為「B 加 `--cutoff`；組長 10/30 執行」。組長已加入 `--cutoff／--out`，但實際以 10/30 執行會失敗，B 於 W07 補齊：

| 問題 | 影響 | 處理（`scripts/build_snapshot_finmind.py` V1.7） |
|---|---|---|
| FinMind 2026-10-20 起 2330 2026Q2 損益表**金額**改為 1–6 月累計（EPS 仍為單季） | 重抓即被 MOPS 對帳擋下，前瞻快照無法產生 | 金額與 EPS 分開判定單季／累計：以 MOPS 對帳值比對「原值」與「原值 − 前季」；無營收對帳值時以「母公司淨利 ÷ 流通股數 ≈ 已驗證 EPS」交叉判定；皆不符即中止。輸出 `period_basis_source` |
| 季別寫死到 2026Q2 | 10/30 前若 2454 已公告 2026Q3 會漏掉最新可得資料 | `FORWARD_PERIODS = [2026Q3]`：只在 announce_times.csv 有列且公告時間 ≤ cutoff 時納入，各公司可不同並輸出 `periods_by_ticker` |
| 晚於 cutoff 的總經／公告列會使程式中止 | 同一份人工檔無法服務不同 cutoff | 晚於 cutoff 的列視為「尚未可得」略過（基本 5 季仍嚴格中止） |
| 證據沿用 30 案用的證據 | 前瞻研究讀到錯的證據 | 新增 `--evidence`，前瞻模式必填，例如 `data/manual/forward/evidence-2026-10-30.csv` |
| 新季別無 MOPS 對帳值 | EPS 只能標 unverified，TTM 為 null | 新增 `data/manual/mops_control.csv`，B 於公告後填入本季營收與 EPS，不必改程式 |
| 股價只存 5 天 | `get_price_window` 的 20 日無資料 | 前瞻模式保留 cutoff 前 20 個交易日 |
| 工具只讀固定快照 | 前瞻研究無法改讀前瞻快照 | `agents/tools_impl.py` 新增環境變數 `FINTECH_SNAPSHOT_PATH`；未設定時行為不變 |

### 離線驗證（2026-10-22，B 以本機 FinMind 原始檔模擬，不重抓）

| 測試 | 結果 |
|---|---|
| 以 10/20 新版 2330 原始檔（金額為累計）重建 30 案快照 | 自動換算為單季；25 季所有欄位與凍結快照**完全相同**（0 差異） |
| 以 10/17 舊版 2330 原始檔重建 | 0 差異 |
| 前瞻模式，2454 2026Q3 公告晚於 cutoff | 自動略過，只到 2026Q2 |
| 前瞻模式，2454 2026Q3 公告早於 cutoff（合成資料）＋ mops_control.csv | 納入 2026Q3，EPS 標 mops_direct；工具以 cutoff 17:00 查詢仍回 2026Q2、21:00 查詢回 2026Q3 |
| `--out data/financial-snapshots.json` 搭配 `--cutoff` | 中止（保護 30 案快照） |
| 前瞻模式未給 `--evidence` | 中止 |

### 工具防護（`agents/tools_impl.py` W07 版，須在 10/23 凍結工具前合併）

- `use_snapshot(path)`／`FINTECH_SNAPSHOT_PATH`：前瞻研究改讀前瞻快照，30 案行為不變。
- 快照截止防護：快照有 `cutoff_at` 時，請求的 cutoff 一律被截斷到快照截止時間，cutoff 後的片段、季別、股價、總經都不會回傳（前瞻價格不回流 Agent）。
- 片段 ID 白名單：網址、路徑、空白等格式回 `invalid_input`（W08「未授權 ID 不通過工具」）。
- 新增 `tests/test_forward_guard.py` 15 項；B 的 48 項與全套可執行測試結果與修改前相同。

### 稽核工具（`scripts/audit_report.py`，不在凍結清單）

- `data/v12-report-audit.csv` 由 `--baseline` 自動產生（56 列，數字由六工具以同一快照重算，與事實清冊 V1.9 一致）。
- W07-L 報告產生後執行 `--report`，自動判定引用可解析、hash、可得時間、數字、假資料、比較組。
- 以合成報告測試：正確報告 8 項全 pass；錯誤報告 7 項全被抓出（不存在片段、cutoff 後資料、合成資料、舊假數字 853.27、2317 給負 DCF、單季 EPS×4 冒充 TTM、2317 出現比較面板）。

### 全域證據片段的可得時間（步驟 2）— 2026-10-22 已依 MOPS 原文更正

`data/financial-snapshots.json` 的 5 個全域片段（非 30 案用）逐筆對照 MOPS 重大訊息；段落改為原文、可得時間改為發言時間、`captured_at` 改為實際擷取時間，並新增 `paragraph_type`、`source_ref`、`verified_note`。財務數字（financials）未變。

| 片段 | 原可得時間 | MOPS 公告（發言時間） | 更正後可得時間 | 判定 |
|---|---|---|---|---|
| ev-2330-2026q2-01 | 07-16 14:00 | 重大訊息第51款「台積公司2026年第二季每股盈餘新台幣27.25元」115/07/16 15:12:31 | 07-16 15:12:31 | 原時間早 72 分鐘（前視）；數字一致 |
| ev-2454-2026q2-01 | 07-31 15:00 | 重大訊息第51款「本公司2026年第2季合併財務報告」115/07/31 18:43:05（董事會 18:41:57） | 07-31 18:43:05 | 原時間早 3 小時 43 分（前視）；數字逐字一致 |
| ev-2317-2026q2-01 | 08-05 16:00 | 08/05 無任何重大訊息；最早含第二季數字為董事會通過財報 115/08/12 14:15:01（1–6 月累計） | 08-12 14:15:01 | 原文字「自結、創同期新高、AI 伺服器」查無原文，改用董事會公告原文 |
| ev-2379-2026q2-01 | 08-05 16:00 | 08/05 無公告；董事會通過財報 115/07/30 17:13:13（1–6 月累計） | 07-30 17:13:13 | 原時間錯誤；「約 376.0 億」與原表 375.53 億不符 |
| ev-3034-2026q2-01 | 08-08 16:00 | 08/08 無公告；董事會通過財報 115/08/04 16:30:51（1–6 月累計） | 08-04 16:30:51 | 原時間錯誤（較晚，非前視） |

影響：
- 30 案不受影響（案例使用 `fixtures/dev`、`fixtures/test` 各自的快照）。
- `fixtures/tool-responses.json` TR-01、TR-05 由 `build_w02_fixtures.py` 依新片段重新產生；`data/source-manifest.json` 重建。
- A 的 `ui/v12-dashboard-fixture.json` 三則 fact 主張需改為引用原文寫法（2454「1,521億8仟3佰萬元」、2330「1兆2,703億8千萬元」、2317「1–6 月累計 4,645,427,824 仟元」），否則 A 的 `test_fixture_claims_quote_their_source_text` 會失敗。

> 注意：`agents/tools_impl.py` 在凍結工具清單內。此修改向下相容，建議在組長 10/23 凍結工具**之前**合併；若已凍結，依手冊第 06 章另立版本。

## 四、未完成、原因及提供人

| 項目 | 原因 | 提供人 | 最晚 |
|---|---|---|---|
| 3 檔 report.json／PDF | W07-L 尚未產生 | 組長 | W07 |
| 前瞻證據擷取（9 月營收、法說會、2454 第三季） | 需在 cutoff 前擷取 | B | 10/30 21:00 |
| 2454／2379／3034 2026Q3 是否 cutoff 前公告 | 未發生 | B 於 10/30 查 MOPS | 10/30 |
| CPI、FEDFUNDS 最新觀察值與發布時間 | 需查 BLS／FRED | B | 10/30 |
| 前瞻快照執行與 sha256 | 21:00 後 | 組長執行、B 記錄 | 10/30 |
| 除權息是否影響報酬口徑 | 方法決定 | D | 11/02 前 |
| snapshot.py 保留集防護（CR-W06） | 組長檔案，凍結工具清單內 | 組長 | 10/23 |
| C 的報告敘述核准 | 報告未完成 | C 撰寫、D 核准 | W07 |

## 五、測試與版本

- 執行（本機）：`python scripts\check_sources.py`、`python scripts\check_cases.py`、`pytest -q tests\test_adapter_tools.py tests\test_tool_fixtures.py`（未執行者寫「未執行」）
- 版本：builder V1.7、tools_impl W07（含快照截止防護、ID 白名單）、audit_report v1、forward-batch-1-sources v0.1、v12-report-audit v0.1（由 audit_report --baseline 產生）
- 測試（B 於雲端以本機原始檔與 repo 測試執行）：`tests/test_forward_guard.py` 15 passed；`test_adapter_tools.py`＋`test_tool_fixtures.py` 48 passed；全套可執行部分修改前後皆為 161 passed、2 failed（既有失敗，與本次無關）

## 六、交接給 D 的短訊（草稿）

D 你好：W07-B 已先準備前瞻批次 1（10/30 21:00）的來源與價格口徑（research/forward-batch-1-sources.json），請確認 entry＝下一交易日開盤、D1／D5／D20 收盤、未還原價格與除權息註記規則是否同意；報告核對表 data/v12-report-audit.csv 已預填 50 項基準值，W07-L 報告完成後逐項填入。
