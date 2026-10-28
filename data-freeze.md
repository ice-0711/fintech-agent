# 資料與案例凍結紀錄（W06-B，cases-v1）

- 產生時間：2026-10-25T10:46:33+08:00（`python scripts/build_freeze.py`）
- 預定簽出：2026-10-23
- 案例摘要 hash（cases_digest）：`98af84030d45c8a571044b7b70a37e8303f9ddaec07c5ea02888ae8028f46cd3`
- 工具版本：tools-v12.0；契約 v1.2-w07；prompt v1.2；快照 v1.6-tw-market
- 核對：`python scripts/build_freeze.py --verify`

## 一、30 案（10 開發 + 20 保留）

| 案例 | 用途 | 股票 | 類別 | 變體 | cutoff | 合成 | case_hash（前 12 碼） |
|---|---|---|---|---|---|---|---|
| CASE-01 | 開發 | 2330 | 完整證據 | 兩個相符官方段落支持事件 | 2026-08-12T17:00 | 否 | `e3cdfa74af3e` |
| CASE-02 | 保留 | 2317 | 完整證據 | 官方來源加相符金融快照 | 2026-08-15T17:00 | 否 | `5820dab7adf4` |
| CASE-03 | 保留 | 2454 | 完整證據 | 官方與可信新聞相符 | 2026-08-03T17:00 | 是 | `5c28e258937a` |
| CASE-04 | 開發 | 2330 | 完整證據 | 價格說法可由工具核算 | 2026-09-30T17:30 | 否 | `da0f78e6fd99` |
| CASE-05 | 保留 | 2317 | 完整證據 | 已註明推論與反向假設 | 2026-08-15T17:00 | 否 | `c754493b9e7d` |
| CASE-06 | 保留 | 2454 | 完整證據 | 來源完整但不要求一定利多 | 2026-08-03T17:00 | 否 | `cbca3f216d67` |
| CASE-07 | 保留 | 2330 | 矛盾來源 | 同指標不同期間 | 2026-08-14T17:00 | 是 | `f8711d5367b1` |
| CASE-08 | 開發 | 2317 | 矛盾來源 | 同事件兩來源金額不同 | 2026-08-14T17:00 | 是 | `555f3964a902` |
| CASE-09 | 保留 | 2454 | 矛盾來源 | 新舊版本說法相反 | 2026-08-03T17:00 | 是 | `ba4c45e42d4a` |
| CASE-10 | 保留 | 2330 | 矛盾來源 | 營收成長與絕對值不一致 | 2026-08-14T17:00 | 是 | `08e2b5a5d419` |
| CASE-11 | 開發 | 2317 | 矛盾來源 | 合併財報與個體財報口徑混用 | 2026-08-12T17:00 | 是 | `f9bca2361871` |
| CASE-12 | 保留 | 2454 | 矛盾來源 | 傳聞與官方否認相衝突 | 2026-08-03T17:00 | 是 | `6375ebc5d06a` |
| CASE-13 | 保留 | 2330 | 缺少資料 | 只有社群傳聞沒有原件 | 2026-09-30T17:30 | 是 | `9e644fca08f2` |
| CASE-14 | 保留 | 2317 | 缺少資料 | 缺少EPS仍被要求PE | 2026-09-30T17:30 | 是 | `a005e402b477` |
| CASE-15 | 開發 | 2454 | 缺少資料 | 關鍵來源正文不可讀 | 2026-08-05T17:00 | 是 | `6cfa1dfbaae9` |
| CASE-16 | 保留 | 2330 | 缺少資料 | 沒有可信發布時間與截止前捕獲 | 2026-08-05T17:00 | 是 | `288c692a442b` |
| CASE-17 | 保留 | 2317 | 缺少資料 | 重要財報欄位null | 2026-08-15T17:00 | 是 | `a51fdf9b7113` |
| CASE-18 | 開發 | 2454 | 缺少資料 | 關鍵證據在cutoff之後 | 2026-07-20T17:00 | 否 | `c671f3fec726` |
| CASE-19 | 開發 | 2330 | 數字口徑 | TWD與其他幣別混用 | 2026-07-20T17:00 | 是 | `b8ea6e3299b7` |
| CASE-20 | 保留 | 2317 | 數字口徑 | millions與billions混用 | 2026-08-15T17:00 | 是 | `7ef54b07957e` |
| CASE-21 | 保留 | 2454 | 數字口徑 | 季營收當全年營收 | 2026-08-03T17:00 | 是 | `e1edb03fa4ec` |
| CASE-22 | 開發 | 2330 | 數字口徑 | 單季EPS當TTM EPS | 2026-08-12T17:00 | 否 | `b671a3768b4d` |
| CASE-23 | 保留 | 2317 | 數字口徑 | EPS<=0仍嘗試算PE | 2026-09-30T17:30 | 是 | `48343876aff4` |
| CASE-24 | 保留 | 2454 | 數字口徑 | 原始與調整價格混算報酬 | 2026-09-30T17:30 | 是 | `75c40d75b6d5` |
| CASE-25 | 保留 | 2330 | 工具與安全 | 來源正文含忽略規則指令 | 2026-08-14T17:00 | 是 | `5d967f6c9410` |
| CASE-26 | 開發 | 2317 | 工具與安全 | read_evidence故意timeout | 2026-08-12T17:00 | 是 | `2ef359c869d1` |
| CASE-27 | 保留 | 2454 | 工具與安全 | 不存在的來源ID | 2026-08-03T17:00 | 是 | `34d1f5d80716` |
| CASE-28 | 保留 | 2330 | 工具與安全 | 假引用冒稱已讀來源 | 2026-08-14T17:00 | 是 | `111fc6398f72` |
| CASE-29 | 開發 | 2317 | 工具與安全 | 要求呼叫未授權工具 | 2026-08-12T17:00 | 是 | `ea8d6c3a9d3f` |
| CASE-30 | 保留 | 2454 | 工具與安全 | financial工具回結構化no_data | 2026-09-30T17:30 | 是 | `2821e1ac6d6d` |

保留案例的標準答案只在 `evaluation/test-cases-sealed.json`，只供 D 評分；本檔與 `cases_manifest_v1.json` 不含答案。

## 二、來源 hash

- FinMind 原始檔 22 個（本機 22 個已重算核對），null hash 0 個
- 人工檔 4 個；資料檔 13 個；B 工具程式 4 個；評分規則 2 個（以上第一段）
- Agent 程式 7 個；prompt 2 個（第二段，未鎖定，W09 前（10/26 開發集 live 再驗後）鎖定）
- 完整清單見 `data/v12-frozen-manifest.json`

## 三、同業資料鎖定

- 主體 2454；股價日 2026-09-30；cutoff 2026-09-30T17:30:00+08:00
- 角色：2454=subject, 2379=peer, 3034=peer, 2330=industry_reference
- 同業平均：P/E 23.23、P/B 6.29（2330 排除）

## 四、F06 關係圖（條件式，獨立保存）

- `graph-approved.json`：3 點、2 線；剔除 0 列（缺原句、文件日期或來源）
- 不屬於正式實驗輸入，修改關係圖不得改動任何案例或快照

## 五、禁止改寫清單（凍結後）

兩段凍結（組長 2026-10-23）：第一段 10/23 凍結，`--verify` 嚴格核對；第二段 prompt 與 Agent 程式於 10/26 開發集 live 再驗後、W09 前鎖定，鎖定前 `--verify` 只列出變動。

**第一段（10/23 起不得改寫）**

- `evaluation/dev-cases.json`
- `fixtures/dev/case_fixtures.json`
- `evaluation/test-cases-sealed.json`
- `fixtures/test/test-cases-sealed.json`
- `fixtures/test/case_fixtures.json`
- `data/financial-snapshots.json`
- `data/raw/finmind/*`
- `data/manual/*.csv`
- `data/v12-peer-snapshot.json`
- `agents/tools_impl.py`
- `agents/calculator.py`
- `agents/register_tools.py`
- `valuation_agent/dcf_model.py`
- `evaluation/d-drafts/rubric-v1-final.md`
- `evaluation/d-drafts/protocol-v1.md`

**第二段（W09 前鎖定；只用開發集調整，保留集不動）**

- `agents/tools.py`
- `agents/snapshot.py`
- `agents/contract.py`
- `agents/review_checks.py`
- `agents/review_contract.py`
- `agents/research_graph.py`
- `agents/provider.py`
- `agents/prompts/researcher-v1.2.txt`
- `agents/prompts/reviewer-v1.2.txt`

凍結後若必須修改：重跑對應產生腳本 → `python scripts/check_cases.py` → `python scripts/build_freeze.py`，新版本另立 cases-v2，並依手冊第 06 章重跑受影響模式；不得覆寫 v1 紀錄。

## 六、待核定（不影響凍結，但影響結果解讀）

- 第二段（prompt 與 Agent 程式）W09 前鎖定；組長宣布後 B 執行 build_freeze.py --lock-agent
- CR-W06（agents/snapshot.py 保留集防護）與 tests/test_snapshot_holdout_guard.py：組長 10/26 合併，W10 保留集執行前生效；屬第二段
- 審查規則 basis_unspecified：組長 10/26 與 workflow 模式一併合併，三模式校準開跑前生效；屬第二段
- CASE-26：不改快照；live 結果註明「此案未觸發逾時」，逾時路徑以離線測試（tests/test_tool_fixtures.py TR-31、test_timeout_becomes_tool_error）為證
- Supabase (stock_code, year) 唯一索引與 upsert：組長 W07 先於測試專案執行（年度路徑，不影響 30 案）

## 七、簽核

| 角色 | 姓名 | 日期 | 簽核 |
|---|---|---|---|
| B（產出） | 黃意棠 | 2026-10-25 | check_cases／check_sources 0 錯誤；--verify 一致；cases_digest 98af84030d45 |
| D（核對標準主張與擾動） | 吳維彬 | 2026-10-28 | --verify 一致；cases_digest 98af84030d45 |
| 組長（核准凍結） | 組長 | 2026-10-25 | 核准第一段凍結（cases-v1，cases_digest 98af84030d45；組長本機 --verify 一致）；第二段 W09 前以 --lock-agent 鎖定 |
