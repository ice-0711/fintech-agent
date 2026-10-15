# v12-financial-test-results　財務計算手算驗證與年度 DCF 相容（草稿）

任務ID：W03-D
負責人：組員D
驗收人：B 交叉評分，組長核准結論
狀態：草稿，尚未經 B 與組長驗收。AI 協助產出不等於驗收。
更新：2026-10-09
性質：全部是離線的確定性計算，輸入是手冊算例或 D 自編的合成數字（synthetic_fixture），**不是真實公司財報，不是實驗結果**。

## 一、先講結論

- 手算合成例：P/E、成長率、DCF、同業平均、TTM 加總，下面 7 組的手算值和 B 的程式結果**全部一致**。
- 年度 DCF 相容：既有的 valuation_agent/dcf_model.py、新的 agents/calculator.py 的 calculate_dcf_scenario、D 用 Decimal 獨立手算，三者每股內在價值都是 **167.44 元/股**，差 0.00。
- 發現的問題：TTM 沒有檢查四個季度是否連續（詳見 tool-validation.md 的 F3）；累計轉單季、P/B、FCF 等規則在 calculator.py 沒有對應函式，無法驗證（見第四節）。

## 二、手算合成例（先用手算預期值，再比對程式）

| 編號 | 計算 | 手算 | 程式結果 | 結果 |
| --- | --- | --- | --- | --- |
| 1 | P/E = 120 / 6 | 20 | 20.0 | 一致 |
| 2 | P/E = 1005 / 38.2（B 的 CASE-04） | 26.309…，兩位小數 26.31 | 26.31 | 一致 |
| 3 | EPS 小於等於 0 時 P/E | 不適用（NA） | invalid_input（不產生負值） | 一致 |
| 4 | 成長率（120 - 100）/ 100 | 20% | 0.2（比例） | 一致（單位是比例，不是百分比） |
| 5 | 缺基期的成長率 | NA | 不適用 | 一致 |
| 6 | TTM EPS = 9 + 10 + 9.5 + 9.7 | 38.2 | 資料檔與工具以最後四季加總計算，連續時一致 | 一致 |
| 7 | 同業平均 P/E：2379 為 20、3034 為 10，2330（P/E 50）排除 | (20 + 10) / 2 = 15.0；若誤含 2330 會是 26.67 | 15.0 | 一致 |

註：第 6 項用 B 的 data/financial-snapshots.json 中 2454 最後四季 EPS 加總，與 get_financial_snapshot 的 eps_ttm 比對，測試名 test_financial_snapshot_ttm_four_quarters_matches_hand_sum，通過。

## 三、DCF 手算與年度 DCF 相容

### 3.1 兩年期手算例（億元、百萬股）

輸入：FCF = [100, 110]，WACC = 10%，g = 2%，淨負債 = 50，股數 = 100。

- PV1 = 100 / 1.10 = 90.909091
- PV2 = 110 / 1.21 = 90.909091，合計 181.818182
- 終端價值 TV = 110 x 1.02 / (0.10 - 0.02) = 1402.5
- TV 現值 = 1402.5 / 1.21 = 1159.090909
- 企業價值 EV = 1340.909091
- 股權價值 = 1340.909091 - 50 = 1290.909091
- 每股 = 1290.909091 / 100 x 100 = 1290.91 元（億元除以百萬股乘 100 換成元）

程式（calculate_dcf_scenario）：EV 1340.91、股權價值 1290.91、每股 1290.91。**一致**。

### 3.2 年度 DCF 相容（既有 dcf_model.py 的範例）

輸入：FCF = [2000, 2200, 2400, 2600, 2800]，WACC = 9%，g = 3%，淨負債 = -3000（淨現金），股數 = 25,945（百萬股）。

| 來源 | 每股內在價值 |
| --- | --- |
| 既有年度 valuation_agent/dcf_model.py（calculate_dcf） | 167.44 |
| 新 agents/calculator.py（calculate_dcf_scenario） | 167.44 |
| D 用 Decimal 獨立手算（EV 40,441.55） | 167.44 |

三者差 0.00，**相容**。已知差異：既有版本把每年現值先四捨五入到兩位小數再相加，新版本相加後才四捨五入，所以最後一位在別的輸入下可能差 0.01，測試容許 0.01 元。

### 3.3 DCF 防呆（新版）

| 情境 | 預期 | 結果 |
| --- | --- | --- |
| WACC 小於等於 g | 拒絕 | 通過 |
| 淨負債缺失（None） | 拒絕，不補 0 | 通過 |
| 股數為 0 或負 | 拒絕 | 通過 |
| FCF 為空 | 拒絕，不回 0 | 通過 |

與既有版本的差別：既有版本遇到不合法輸入會丟出例外（ValueError），新版本回傳「不適用」並附原因，這是符合 calculate_metrics 契約的設計差異，不是錯誤。

## 四、v12-finance-cases.json 其餘測例：未執行

W02-D 寫的 23 個測例中，能對上 calculator.py 的只有 P/E 與成長率共 5 個（通過）。以下 18 個**目前無法驗證**，原因是 agents/calculator.py 沒有對應函式，也不確定規則放在哪個模組，需要 B 說明：

- 累計轉單季（Q2、Q3、Q4）、缺前期、跨年度或口徑不同不可相減（FIN-01 到 FIN-05）
- 資產負債表存量不可四季相加（FIN-06）
- TTM 四個連續季度（FIN-07、FIN-08；get_financial_snapshot 有 TTM，但不檢查連續，見 F3）
- P/B 與 BVPS 非正數（FIN-12、FIN-13）
- 季營收 YoY 缺基期（FIN-14、FIN-15 已用 calculate_growth_rate 驗證，通過）
- FCF 與 CapEx 符號（FIN-16 到 FIN-18）
- 股數缺失（FIN-19）
- 同日價格、原始與調整價格不可混算（FIN-20、FIN-21）
- 公告時間與 cutoff 排除（FIN-22、FIN-23）

## 五、命令與版本

- 被測 repo：HEAD 4f67d15。
- 環境：雲端工作環境，Python 3.13.16、pytest 9.1.1（不是 D 的 Mac；尚未在本機重跑）。
- 命令：REPO_ROOT=<repo> python -m pytest -q test_adapter_tools.py（DCF 回歸為其中 5 項：test_dcf_*），與 CALCULATOR_PATH=<calculator.py> CASES_PATH=<v12-finance-cases.json> python -m pytest -q test_calculator_against_finance_cases.py（5 passed）。
- Decimal 手算為獨立的 Python 片段，未存成測試檔。

## 六、未完成與誰提供

1. 第四節 18 個測例要接到哪個模組：B 說明。
2. 年度 DCF 之外的報告層（PDF、網站）相容：未測。
3. 以真實公司資料做的實測：未做。
4. 本機重跑與 repo 提交：尚未做，等 B 確認後再處理。
