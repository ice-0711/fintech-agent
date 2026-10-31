# W07-D 線上 PDF 與前瞻首批檢查（v12-pdf-forward-check）

- 任務：W07-D｜D｜驗證端到端和前瞻觀察規則；線上 PDF 及前瞻首批
- 版本：v0.2（2026-10-31）；初版 v0.1 為 2026-10-29｜撰寫：D；初稿由 AI 協助，D 需逐項核對後才送出
- 驗收人：B 交叉評分（初版通過，2026-10-31，`docs/B-review-W07-D.md`）；組長核准結論（**尚未核准**）
- v0.2 更新依據：`origin/main` 675fa9e；B 指出的過時處只在 `e2e-w07.md`，本檔只更新前瞻狀態與受阻項目
- 搭配文件：`evaluation/e2e-w07.md`（端到端結果與未執行清單）

## 一、線上 PDF 檢查（目前只有 MOCK 版）

| 檢查 | 做法 | 結果 | 範圍 |
|---|---|---|---|
| 三份 PDF 與核准 JSON 一致 | `python scripts/w07_pdf_check.py`（main 9a9516f） | 2330、2317、2454 皆通過；關鍵項目 18/18、17/17、22/22 | MOCK，資料截止 2026-09-30 17:30 |
| PDF 檔案未被改動 | `sha256sum` 重算三份 PDF，與 `reports/v12-online-pdf/manifest.json` 的 pdf_hash 比對前 16 碼 | 5071400a0f76654d、8b4cd30871e66367、7b2928eb8afeb687 皆相符 | MOCK |
| 頁數與大小 | `w07_pdf_check.py` | 3／2／3 頁；398／234／393 KB（上限 10 頁、5 MB） | MOCK |
| 中文與字型 | `w07_pdf_check.py` 檢查內嵌字型 | 內嵌 NotoSansCJKTC 子集 | MOCK |
| PDF 失敗不能假 published | `test_pdf_failure_is_recorded_and_retry_works` | 通過：失敗記為 `pdf_failed`，重試成功才 published | 離線 |
| 已發布不可覆寫 | `test_publish_renders_real_pdf_and_never_overwrites`、`test_new_version_of_same_job_keeps_history_and_old_pdf` | 通過 | 離線 |
| 草稿不公開、核准要比對 hash、核准需組長登入 | `test_draft_is_not_public_until_the_lead_approves_the_seen_hash` 等 | 通過 | 離線 |
| 純讀 0 次 LLM | `test_public_reads_make_no_llm_calls` | 通過 | 離線 |
| 重新部署後仍可下載 | 組長 10/28 在 Supabase 測試專案演練第 9 項（新 ReportStore，不用記憶體與本機磁碟）：PASS（`publication/v12-state-tests.md`） | **組長的結果，D 尚未自行重跑** | Supabase 測試專案 |
| 私有 bucket 與權限 | 組長文件：RLS 開啟、無 policy；bucket 私有 | **D 未驗證**（沒有授權的連線資料） | — |

尚未做：LIVE 報告的 PDF、實機手機下載、Render 上的組長登入核准（組長文件列為 W08）。

## 二、前瞻首批（forward-batch-1）檢查

### 2.1 規則對照（手冊第 06 章與 `forward-batch-1-sources.json` v0.3）

| 規則 | 狀態 |
|---|---|
| 每週五 21:00（台北）三檔各凍結一份，共 9 份；批次 1 為 2026-10-30 21:00 | 我在 675fa9e 看到 `forward-batch-1-sources.json` 為 v0.4-draft（2026-10-31），status 仍是 draft。組長 2026-10-31 決定：第三季選 A（FinMind 未上架則改 B 並記原因）、direction 選 (b)；之後由 B 轉 frozen、組長跑快照。cutoff 10/30 21:00 已過，快照怎麼產生由組長決定，D 不處理 |
| 截止時間與來源可得時間同存；cutoff 後發布的來源不得列入 | 規則在檔案 `evidence_rules`；凍結後由 B 稽核、D 抽查 |
| 價格口徑：raw 未還原；entry 為 cutoff 後下一個交易日開盤；D1／D5／D20 收盤 | runner 已依此實作（見 e2e-w07.md 第四節） |
| 資料不足照收錄，不補造方向、不挑掉失敗樣本 | runner 對每一份訊號都輸出一列，缺價或未成熟標 NA，不會消失 |
| 無方向訊號不計方向命中；9 份是小樣本，不證明預測能力 | runner 只對 up／down 計命中；摘要附分子、分母 |
| 12/11 截取時仍未成熟即 NA | runner 以 `--as-of` 判斷，不填值 |

### 2.2 預期窗口（來自 B 的檔案，以實際交易日曆為準）

| 批次 | 訊號截止 | entry（預期） | D1／D5／D20（預期） |
|---|---|---|---|
| 1 | 2026-10-30 21:00 | 2026-11-02 開盤 | 11/02、11/06、11/27 |
| 2 | 2026-11-06 21:00 | 2026-11-09 開盤 | 11/09、11/13、12/04 |
| 3 | 2026-11-13 21:00 | 2026-11-16 開盤 | 11/16、11/20、12/11（與截取日同日，17:30 前截取則 NA） |

除權息（B 2026-10-31 的口徑）：2330 第二季現金股利 7.0 元，除息日 2026-12-10，只落在批次 3 的 20 日窗內，依規約標記並保留 raw 報酬。2454 上半年現金股利每股 24.5 元，除息交易日 2027-01-05（MOPS 公告 2026-10-30 17:08），不在三批任何觀察窗內。2317 目前沒有。

### 2.3 批次 1 凍結前的來源狀態（v0.1 記錄；B 2026-10-31 已補第三季公告與對帳，D 未獨立核對）

| 項目 | B 記錄的狀態 |
|---|---|
| 2330 9 月營收與 10/15 法說資料 | collected_2026-10-26 |
| 2317 9 月營收；ITC 337 重大訊息 | collected_2026-10-28 |
| 2454 9 月營收 | collected_2026-10-28 |
| 2454 2026Q3 法說（10/30 15:00）與董事會財報 | to_collect；需在 21:00 前查 |
| 總經：CPIAUCSL、FEDFUNDS | collected_2026-10-28 |
| 2454、2379、3034 的 2026Q3 財報是否在 cutoff 前公告 | 10/30 21:00 前確認；若有，要加列並填 MOPS 對帳值 |

### 2.4 10/30 21:00 凍結後 D 要做的檢查（待做）

| # | 檢查 | 依據 | 狀態 |
|---|---|---|---|
| 1 | 快照產生、B 通知凍結後，檢查 `evidence-audit-w07.md` 與 `data/v12-report-audit.csv`（B 在群組要求） | B 10/28 訊息 | 待做（快照尚未產生） |
| 2 | 前瞻快照的 sha256、generated_at、raw_files 是否已記入 `forward-batch-1-sources.json` 的 `snapshot.frozen` | 檔案 `freeze_after_run` | 待做 |
| 3 | 快照內沒有任何 `available_at` 晚於 10/30 21:00 的證據、季別、總經、股價 | `test_forward_guard.py` 的規則；D 另以快照抽查 | 待做 |
| 4 | 3 份研究都有（或如實記缺）：方向訊號欄位、截止時間、來源可得時間 | 手冊 06 章 | 待做 |
| 5 | （方向訊號組長已決定三批全記 `none`，樣板已填好）快照完成後，11/02 起用 runner 算 D1，之後 D5、D20 | `scripts/forward_eval.py` | 待做 |

runner 指令範例（以實際檔名為準，價格與日曆檔放在 `evaluation/` 之下，不要放進 `data/forward`）：

```
python scripts/forward_eval.py \
  --signals evaluation/forward-signals-batch1.json \
  --prices evaluation/forward/prices-2026-11.csv \
  --calendar evaluation/forward/trading-dates-2026.csv \
  --actions evaluation/forward/corporate-actions.json \
  --as-of 2026-11-02T18:00:00+08:00 \
  --out evaluation/forward-eval-batch1.csv \
  --summary-out evaluation/forward-eval-batch1-summary.json
```

## 三、受阻與需要的人

| 項目 | 原因 | 需要誰 |
|---|---|---|
| 批次 1 的方向訊號 | 組長 2026-10-31 已決定選 (b)：三批全記 `none`，只展示 1／5／20 日報酬，不算命中率；`forward-signals-batch1.json` 三筆已改為 `none` | —（已解決） |
| 批次 1 的價格 | 11/02 起才有 | — |
| 真實交易日曆與價格檔 | B 已給口徑（FinMind `TaiwanStockTradingDate`；價格 `TaiwanStockPrice` 未還原，欄位 date、stock_id、open、close、Trading_Volume；只含 2330、2317、2454；放 `evaluation/forward/`）；實際檔案還沒匯出 | 組長或 D 於 11/02 前後依口徑匯出 |
| 零報酬的方向命中規約 | 已解決：組長 2026-10-29 核定，零報酬不計入分子分母、另列筆數（`handoff/decisions-2026-10.md` 第八節） | — |
| Supabase 權限與重啟的 D 自行驗證 | 沒有授權的連線資料 | 組長 |

## 四、交付紀錄

| 欄位 | 內容 |
|---|---|
| 版本 | v0.2（2026-10-31）；v0.1 已隨 PR #11 合併（44dfcb5） |
| 實際工時 | 約 4 小時（D 自己回報，10/29 一天；與 e2e-w07.md 為同一次工時，不重複計算）；10/31 修訂時間待 D 自己補 |
| 成果連結 | v0.1：https://github.com/kk1030-bit/fintech-agent/pull/11（已合併）；v0.2：（待 D 上傳後填） |
| 驗收人與日期 | B 交叉評分：初版通過（2026-10-31）；組長核准：待 |
