# V1.2 資料適配層與計算工具測試紀錄 (W03-B，V1.1)

- 版本：V1.1（2026-10-20）；取代 2026-10-01 規約版
- 對象：`agents/tools_impl.py`、`agents/calculator.py`、`agents/register_tools.py`、`financial_analyzer.py`
- 依據：`data/tool-contracts.json` v1.1-w02、`fixtures/tool-responses.json` v1.4-w02、`data-contract.md` V1.7
- 驗收人：D（財務與證據），組長合併

---

## 一、本次程式修正

| 檔案 | 修正 | 對應驗收 |
|---|---|---|
| `agents/tools_impl.py` | 回傳頂層固定 `status/tool/reason/data`；每筆資料帶 `available_at_basis`；財報帶 `captured_at`；股價每列帶 `available_at`（交易日 17:30），整窗帶 `source_id`、`content_hash`；總經帶 `source_id`、`content_hash`、`vintage` | 每數字有來源／期間／幣別 |
| `agents/tools_impl.py` | `read_evidence`：`paragraph` 為 null 回 `unreadable`；不再自動填通用 MOPS 網址 | 不造來源 |
| `agents/tools_impl.py` | `search_evidence`：只限 2330/2317/2454；`paragraph` 為 null 不崩潰 | 防呆 |
| `agents/tools_impl.py` | TTM：需四連續季、皆為 single_quarter、無 null、EPS 無 unverified；否則 null 並附原因 | PE 無 TTM 就 null |
| `agents/tools_impl.py` | 總經白名單改為 `CPIAUCSL`、`FEDFUNDS`，與 `tools.py` 一致 | 未核定序列不得回傳 |
| `agents/tools_impl.py` | 官方時間未知以 `captured_at` 判定；兩者皆無視為不可得 | unknown 不視為較早可得 |
| `agents/calculator.py` | `ok` 回傳補 `reason: null`；`peer_comparison` 接受 `dcf_per_share`、`fcf`，補 PE/PB/YoY/FCF 的 NA 理由，比較標的白名單檢查 | EPS/BVPS 非正不亂算 |
| `agents/register_tools.py` | 每次工具呼叫限時 15 秒（`TOOL_TIMEOUT_SECONDS`），逾時由 `dispatch` 包成 `tool_error` | CASE-26 |
| `financial_analyzer.py` | `money_100m(None)` 回傳 `None`（原為 `0.0`），文字顯示「無資料」 | null 與 0 分開 |
| `scripts/build_source_manifest.py` | 由實際檔案重建 `data/source-manifest.json`，取代舊版假 hash | 來源 hash 可追溯 |

未改動：`valuation_agent/dcf_model.py`、`main.py` 年度 DCF 路徑、`report_downloader.py`（不破壞年度 DCF）。

## 二、測試清單

### 2-1 既有單元測試（`tests/test_adapter_tools.py`，未修改）

| ID | 工具／運算 | 情境 | 預期 |
|---|---|---|---|
| TEST-01 | `search_evidence` | cutoff 早於可得時間 | `no_data` |
| TEST-02 | `read_evidence` | 不存在的 ID | `no_data`，不拋例外 |
| TEST-03 | `get_financial_snapshot` | 只有 2 季可得 | `eps_ttm` 為 null，附 `missing_reason` |
| TEST-04 | `get_price_window` | sessions=10 | `invalid_input` |
| TEST-05 | `calculate_pe_ttm` | EPS ≤ 0 | 不適用 |
| TEST-06 | `calculate_dcf_scenario` | WACC = g | 不適用 |
| TEST-06b | `calculate_dcf_scenario` | 預測期 3 年 | 不適用，原因含「5 年」 |
| TEST-07 | `calculate_dcf_scenario` | 淨負債 null | 不適用，不補 0 |
| TEST-08 | `calculate_peer_comparison` | 主體非 2454 | 不適用 |
| TEST-09 | `calculate_peer_comparison` | 含 2330 | 2330 不入同業平均 |

### 2-2 契約 fixture 測試（`tests/test_tool_fixtures.py`，新增）

- `test_tool_fixture[TR-01…TR-31]`：每個 W02 fixture 經 `agents.tools.dispatch`（含參數驗證與角色權限）執行，依 `check_mode` 比對（`exact` 整筆相同；`status_only` 比狀態）。
- `TR-06`（CASE-15）、`TR-31`（CASE-26）走 `agents/snapshot.py`；組長未套用第三節 CR 前自動標 xfail，套用後自動轉為正式檢查。

| 測試 | 驗證內容 | 對應驗收 |
|---|---|---|
| TR-08、TR-14、TR-17 | 財報、總經、股價回傳的來源、期間、幣別、單位、可得時間欄位 | 每數字有來源／期間／幣別 |
| TR-09、`test_ttm_rejects_unverified_and_gaps` | 不足 4 季、含 unverified、季度不連續 → TTM null | PE 無 TTM 就 null |
| TR-04、TR-12、TR-30 | URL 字樣、多餘欄位、未授權 operation 被拒 | 工具不能任意 URL 或 SQL |
| TR-22、TR-28 | EPS ≤ 0 拒算；P/B 由 BVPS 計算、2330 不入平均 | EPS/BVPS 非正不亂算 |
| TR-17、TR-18 | 未還原收盤價；17:30 前不可用當日價 | 實際股價不被代理量取代 |
| TR-24 | DCF 853.27 元與敏感度矩陣（參數待核定） | 不破壞年度 DCF 公式 |
| `test_timeout_becomes_tool_error` | 慢工具逾時 → `tool_error` | CASE-26 |
| `test_money_100m_keeps_null` | 缺值不補 0 | null 與 0 分開 |
| `test_read_evidence_does_not_invent_url` | 缺網址回 null | 不造來源 |
| `test_unknown_time_not_available` | 兩時間皆無不可得；只有 captured_at 以其判定 | unknown 不視為較早可得 |

## 三、需組長修改（CR）

`agents/snapshot.py` 為組長（W04-L）檔案，B 不直接修改。修正內容見 `docs/CR-W03-snapshot.diff`：

| CR | 問題 | 修正 |
|---|---|---|
| CR-01 | 案例快照 `paragraph` 為 null 時 `read_evidence`、`search_evidence` 拋 TypeError（CASE-15 只得到 `tool_error`） | `paragraph` 為 null 回 `unreadable` |
| CR-02 | `case_fixtures.json` 的 `tool_simulation`（CASE-26 timeout）未被執行 | 依設定拋 `TimeoutError`，由 dispatch 包成 `tool_error` |
| CR-03 | `main.py` 第 403–406 行以營收比率冒充 P/E、P/B；第 337–338 行淨負債補 0 | 舊網站路徑；建議改為顯示「不可用」，修正前不得引用 |

## 四、已知資料問題（交 W04／W05 處理）

1. `financial-snapshots.json` 證據片段的 `published_at` 尚未逐筆對照 MOPS 發言紀錄：
   - `ev-2454-2026q2-01` 可得時間 15:00，早於 MOPS 董事會通過財報 18:41:57，且含 EPS；
     片段稅後純益 246.05 億與快照歸屬母公司淨利 243.35 億口徑不同。
   - `ev-2317-2026q2-01` 可得時間 08-05，早於財報公告 08-12（片段只有營收）。
2. `fixtures/dev/case_fixtures.json` CASE-01 的片段引用 2330 合併損益表精確數字，可得時間卻標 07-16（法說會），財報董事會通過為 08-11。
3. `data/v12-peer-snapshot.json` 的 3034 FCF TTM 為 167.47，快照計算為 167.49。

## 五、執行方式與紀錄

```bat
cd C:\專題\新增資料夾\fintech-agent
.venv\Scripts\activate
python scripts\build_source_manifest.py
python scripts\build_w02_fixtures.py
python scripts\check_sources.py
pytest -q tests\test_adapter_tools.py tests\test_tool_fixtures.py
pytest -q
```

| 項目 | 命令 | 結果（請填） | 執行日期 | commit |
|---|---|---|---|---|
| 重建 manifest | `python scripts\build_source_manifest.py` | 未執行 |  |  |
| 產生 fixture | `python scripts\build_w02_fixtures.py` | 未執行 |  |  |
| 來源與 cutoff 檢查 | `python scripts\check_sources.py` | 未執行 |  |  |
| 適配層與契約測試 | `pytest -q tests\test_adapter_tools.py tests\test_tool_fixtures.py` | 未執行 |  |  |
| 全套回歸 | `pytest -q` | 未執行 |  |  |
