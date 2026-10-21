# CR-W04：research_ui/comparison.py（A 負責）配合 B 工具修正

B 於 W03 修正六工具後，A 的比較面板有 4 處需同步。B 不直接修改 A 的檔案。

| # | 位置 | 現況 | 建議 |
|---|---|---|---|
| 1 | `build_comparison()` 取收盤價 | `last["close"]` | 改為 `last["close_price"]`（工具回傳欄位，見 `data/tool-contracts.json`） |
| 2 | `get_price_window(code, f"{price_as_of}T13:30:00+08:00", 1)` | 13:30 時當日收盤價尚不可得 | 改為 `T17:30:00+08:00`（股價可得時間規則 `rule_close_1730`，data-contract V1.7） |
| 3 | FCF 快照值 | `snap.get("fcf_100m")` | 改為 `snap.get("fcf_ttm_100m")`（`data/v12-peer-snapshot.json` 實際鍵名） |
| 4 | P/B | 寫死「快照沒有 BVPS，工具無法重算」 | `get_financial_snapshot` 已回傳 `metrics.bvps`；可用 `price ÷ bvps` 或 `calculate_metrics(peer_comparison)` 重算 |

另：舊版 B 工具不支援位置參數，面板原本實際上取不到資料；W04 版 `agents/tools_impl.py` 已支援 `fn(ticker, cutoff)` 這類呼叫，A 不必改呼叫方式。

`data/v12-peer-snapshot.json` 已標 `synthetic_fixture: false`（真實資料），面板的 `fixture_note` 可由 A 與 D 確認後更新。