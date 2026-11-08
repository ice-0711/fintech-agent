# fintech-agent 多智能體投資分析系統

在有限 Gemini API 預算下，以 Researcher（研究）與 Reviewer（覆核）兩個 Agent 協作，提高台股投資分析的證據完整度與可追溯性。研究標的 2330、2317、2454；2379、3034 只作 2454 的比較參照。

- 專題期間：2026/09/14–12/18（12/11 內部定稿）
- 執行計畫：Notion《fintech-agent｜專題執行手冊 V1.2》（本機副本 `docs/handbook_V1.2/`）
- 分支：**只有 `main` 是正式版**。功能分支合併後即刪除。

## 先看哪裡

| 想知道 | 看這裡 |
|---|---|
| 組長核定過的決定（WACC、口徑、F06…） | `handoff/decisions-2026-10.md` |
| 本週進度與驗收（W06） | `handoff/W06-gate-v12.md` |
| job 狀態與預算規則 | `handoff/state-machine-v1.md` |
| 模型與額度設定 | `handoff/model-config.md`、`handoff/quota-baseline.json` |
| 資料口徑（單季／TTM、淨負債、股數） | `data-contract.md`、`data/v12-finance-fact-sheet.md` |
| B 的檔案總說明 | `docs/B-W01-W06-檔案說明.md` |
| A 的畫面交接 | `design/A-W05-W06-handoff.md` |
| D 的評估草稿 | `evaluation/d-drafts/README.md` |

## 資料夾地圖（依負責人）

### 組長｜Agent 執行器、預算、發布
| 位置 | 內容 |
|---|---|
| `agents/` | 核心程式：`research_graph.py`（LangGraph 研究迴圈＋覆核）、`provider.py`（Gemini）、`budget.py`（8 次／10 工具／token／每日上限）、`store.py`、`worker.py`（持久 job、lease）、`api.py`、`admin.py`（組長登入）、`publication.py`（核准、版本、PDF）、`snapshot.py`（工具綁定 job 快照）、`tools.py`（六工具契約與驗證） |
| `agents/prompts/` | Researcher／Reviewer 系統提示詞（版本化） |
| `agent/` | 開發案例 live／mock 軌跡、覆核契約 |
| `contracts/` | job／報告資料契約、六工具契約 |
| `handoff/` | 每週交接文件與決策紀錄 |
| `supabase_migrations/` | 資料表遷移草案（尚未在正式庫執行） |
| `scripts/dev_traces.py`、`scripts/live_check.py` | live 開發測試（只跑開發集） |

### B｜資料、工具、案例
| 位置 | 內容 |
|---|---|
| `agents/tools_impl.py`、`agents/calculator.py`、`agents/register_tools.py` | 六工具實作與計算 |
| `data/` | 財務快照、同業快照、資料契約、事實清冊、凍結清單；`data/manual/` 人工來源 |
| `fixtures/dev/`、`fixtures/test/` | 10 個開發案例快照／20 個保留案例（**保留集只供 W10–W11 正式評分，組長不讀內容**） |
| `evaluation/dev-cases.json`、`evaluation/cases_manifest_v1.json`、`evaluation/test-cases-sealed.json` | 30 案清單（v1.5） |
| `scripts/build_*.py`、`scripts/check_*.py`、`scripts/verify_fact_sheet.py` | 建快照、凍結、核對 |
| 根目錄 `data-contract.md`、`data-freeze.md`、`source-register.csv`、`graph-*.csv`、`graph-approved.json` | 契約、凍結紀錄、來源登記（凍結清單以這些路徑核對 hash，暫不搬移） |

### A｜網站畫面
| 位置 | 內容 |
|---|---|
| `research_ui/`、`templates/research.html`、`static/` | 研究工作台、收藏、比較面板 |
| `design/`、`ui/` | 畫面規格、截圖、驗收 |

### D｜覆核、測試、評分
| 位置 | 內容 |
|---|---|
| `evaluation/d-drafts/` | W01–W05 驗收矩陣、案例規格、Reviewer prompt 與規則草稿（規則已由組長納入 `agents/review_checks.py`） |

### 共用與舊版網站
| 位置 | 內容 |
|---|---|
| `web_app.py` | Flask 入口（舊站＋V1.2 研究 API＋公開報告） |
| `main.py`、`financial_analyzer.py`、`report_downloader.py`、`report_builder.py`、`valuation_agent/`、`macro_agent/`、`fundamental_agent/`、`fundamental_uploader.py` | 既有分析流程（FinMind、DCF、圖表、PDF） |
| `tests/` | 全專案測試 |
| `docs/handbook_V1.2/` | 專題手冊本機副本 |
| `pdf_parser.py`、`retry_gemini.py`、`gemini_analyzer.py`、`run_fundamental.py`、`seed_fundamental_data.py`、`quality_checker.py`、`*.docx`、`mobile_*.html` | 上學期遺留檔，現行流程不使用；凍結結束後再移到 `legacy/` |

## 執行

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-agent.txt
.venv/bin/python -m pytest -q          # 全專案測試（離線，不呼叫 API）
.venv/bin/python web_app.py            # 本機網站 http://127.0.0.1:5000
```

`.env`（不進版控）需要：`SUPABASE_URL`、`SUPABASE_KEY`、`GEMINI_API_KEY`、`GEMINI_MODEL`、`RESEARCH_API_TOKEN`、`FLASK_SECRET_KEY`、`ADMIN_PASSWORD`。

## 協作規則

- 直接推 `main` 或開 PR 都可以；PR 合併後刪除該分支。
- 保留集（`fixtures/test/`、`test-cases-sealed.json`）不得用於開發或調整 prompt。
- 不把 `.env`、金鑰放進 repo；資料缺值保留 null，不補 0。
