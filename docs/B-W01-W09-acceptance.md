# 組員 B：W01–W09 工作包逐項對照

- 對照依據：Notion「個人_B_十四週工作包」（與 `docs/handbook_V1.2/16_六人84項任務.csv` 的 B 列逐字相同，2026-11-07 核對 W14-B 一致）
- 核對版本：main f9351e3（2026-11-07）｜核對人：組員 B｜狀態：草稿，待驗收人（D 檢查財務與證據、組長合併）確認
- 實際執行的檢查（2026-11-07，Linux）：`scripts/verify_fact_sheet.py` 全部一致；`scripts/check_cases.py` 開發 10、保留 20、關係 2，錯誤 0；`scripts/check_sources.py` 35 列錯誤 0；`scripts/build_freeze.py --verify` 第一段一致（cases_digest 98af84030d45），第二段 6 檔屬 W09 開發調整；保留集 SEAL 三檔 sha256 相符；`tests/test_forward_manifest.py` 9 項通過。全套 pytest 由使用者在 Windows 執行（11/05：389 過、1 失敗，失敗原因 CRLF，組長 a758dc1 已修）。

| 週 | 必交產物 | 在 main | 驗收清單 | 結果 |
|---|---|---|---|---|
| W01 | `data/tool-field-map.md`、`source-register.csv`、`data/v12-field-map.csv`、`graph-source-register.csv` | ✅ | 每工具有模組位置；單位期間幣別分欄；未取得資料 no_data；標已知／未知與 source | ✅ 關係官方素材 3 份（上限 6） |
| W02 | `data/tool-contracts.json`、`fixtures/tool-responses.json`、`data/v12-financial-fixtures.json`、`data-contract.md` | ✅ | unknown 時間不視為較早；null 和 0 分開；錯誤回傳結構固定；合成樣本明示 | ✅ |
| W03 | 六工具程式、`data/financial-snapshots.json`、`data/source-manifest.json`、`data/v12-adapter-tests.md` | ✅ | 每數字有來源／期間／幣別；無 TTM 時 P/E 為 null；工具不接受任意 URL／SQL；不破壞年度 DCF；實際股價不被替代 | ✅（URL／SQL 由 `tests/test_w08_safety.py` 再驗） |
| W04 | `evaluation/dev-cases.json`、`fixtures/dev/`、`data/v12-peer-snapshot.json`、`graph-reviewed.csv` | ✅ | 10 案與固定 split 一致；原始來源不覆寫；變體說明擾動；2330 不入同業統計；關係有原句與日期；不硬湊邊 | ✅ 核准 2 邊 |
| W05 | `evaluation/test-cases-sealed.json`、`fixtures/test/`、`data/v12-finance-fact-sheet.md` | ✅ | 20 案完整且不供 prompt 調整；擾動非真實指控；WACC≤g 拒算；缺債務不填 0；數字可重現 | ✅ fact sheet V1.9 用 WACC 9%，2454 DCF 975.52 可由程式重現 |
| W06 | `evaluation/cases_manifest_v1.json`、`data-freeze.md`、`data/v12-frozen-manifest.json`、`graph-approved.json` | ✅ | 30＝10＋20；來源 hash 齊；保留答案不作 prompt；無來源關係剔除 | ✅ 三方簽核 |
| W07 | `research/forward-batch-1-sources.json`、`evidence-audit-w07.md`、`data/v12-report-audit.csv` | ✅ | 引用 100% 可解析；不以最新值覆蓋歷史；口徑不混用；PDF 無假資料；只 2454 用比較組 | ✅ 39 項全 pass（11/01 重核新版報告） |
| W08 | `data/storage-and-safety-w08.md`、batch-2 來源、`data/v12-capacity-and-graph-audit.md` | ✅（來源檔名為 `research/forward-batch-2-sources.json`，與第 1 批同命名） | 80% 停止閾值；不自動刪資料；外部文字不成指令；無全文外流；新增資料不覆寫舊快照 | 🟡 80% 門檻：組長 11/02「原則採用」，程式未實作（組長檔案）；其餘 ✅ |
| W09 | `research/forward-manifest-9.json`、`evaluation/source-audit-final.md`、`evaluation/v12-forward-manifest.csv` | ❌ 尚未 push | 9 份或如實記缺失；未到 20 交易日不填績效；不補回測當前瞻；9 筆全入清單 | 🟡 進行中：第 1、2 批已稽核，第 3 批 11/13 |

## 與工作包規則的差異或未完成

1. **W08「過期資料有標記」**：財報快照有（超過 150 天標 stale）；關係圖的 `graph-source-register.csv` 已凍結（W06 manifest），不能加欄位。改在 `data/v12-capacity-and-graph-audit.md` 第二節記錄兩條關係的過期條件（115 年度年報上傳後需重核）。F06 已延後，不影響網站。
2. **W08 80% 門檻程式**：屬組長的 `agents/publication.py`，待 Supabase 方案確定後實作；B 已在 `data/storage-and-safety-w08.md` 第六節提出 CR。
3. **W09**：三個產物在使用者電腦上待 push；第 3 批快照 11/13 21:10 產生後補齊第 3 批三列與總稽核定稿。
4. **成果備份**：工作包要求每週另存 `E:\專題\2026秋季成果\Wxx\B\`。B 這邊無法讀取 E 槽，請使用者自行確認 W01–W09 九個資料夾都在。
5. **工作包文字與現況不同（以組長核定為準，不是 B 的缺漏）**：工作包寫「Render 2GB 為計畫」，實際維持 Free 512 MB（C 11/03 已更新文稿）；Agent v2 單次輸入上限已由 3,000 改為 6,000（decisions 第 14 節）。

## 附錄：W10–W14 後續工作（併入原 `docs/B-W07-W14-工具藍圖.md`，2026-11-08 更新狀態）

原藍圖 10/22 擬定，W07–W09 項目已完成或改由他人負責，該檔併入本節後刪除（沒有其他文件引用它）。

| 週 | 需求 | 工具／產物 | 狀態 |
|---|---|---|---|
| W07–W09 | 前瞻快照、截止防護、ID 白名單、價格口徑防護 | `scripts/build_snapshot_finmind.py` V1.8、`agents/tools.py`、`tests/test_forward_guard.py` | ✅ 完成 |
| W07 | 報告稽核 | `scripts/audit_report.py`（`--baseline`／`--report`／`--find`／`--snapshot`） | ✅ 完成 |
| W09 | 9 份前瞻總表 | `scripts/build_forward_manifest.py`（原規劃名 `forward_manifest.py`） | ✅ 完成，第 3 批 11/13 後補齊 |
| W09 | 1／5／20 日報酬、除權息註記 | 原規劃 `scripts/forward_prices.py`；**改由 D 的 `scripts/forward_eval.py` 負責**，B 不另寫 | 由 D 執行 |
| W10–W11 | 盲評：季度／TTM／參照角色與引用；metric 分母稽核 | `scripts/audit_report.py --report` 對 run 輸出重算數字 | 📅 W10 |
| W12 | 資料交接包、新電腦可重建 | `build_freeze.py` 擴充交接 manifest（含前瞻快照與授權註記） | 📅 W12 |
| W13 | 交易日、價格調整口徑、成熟窗口 | 與 D 的 `forward_eval.py` 對照 | 📅 W13 |
| W14 | 問到數據能找到原文 | `scripts/audit_report.py --find` 原文定位；`handoff/source-signoff.md`、`handoff/v12-source-qa.md` | 📅 W14 |