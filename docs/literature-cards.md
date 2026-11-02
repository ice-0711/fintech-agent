# W02-C 指定文獻／文件卡（R01–R08）

- 任務 ID：W02-C｜製作：C（AI 協助閱讀與整理）｜狀態：**草稿，待核准**
- 本檔屬 W02-C 進度（依 W01-C 修改要求，自 W01 轉入）。2026-10-31 第二次修訂；**2026-11-01 第三次修訂**（依 11/01 修改要求第 1–6 項：刪 R08 舊稿、改任務 ID、R05 改讀英文頁、R07 讀完全頁、R01–R03 讀正文全文、R04 網址確認、R01 發表狀態查核）。
- 日期說明：入口經組長於 2026/09/13 核對。各卡「查閱日」為 AI 協助閱讀的日期。Google 文件頁面的「最後更新日」晚於 9/13（見各卡），內容可能已與 9/13 版本不同。
- 規則：R01–R03 依 arXiv HTML 版正文全文整理（範圍見下表），**不引用任何效能數字**；HTML 版沒有 PDF 頁碼，因此本檔不標頁碼。
- 本文件不含任何技術成果或測試結果。本專題與文獻的技術對應，需 B／D／組長核准。

## 來源類型分類

| 類型 | 卡號 | 說明 |
|---|---|---|
| 會議論文 | R01 | ICLR 2023（官方頁面確認，見卡片）；arXiv v3 為其 camera-ready 版本 |
| 學術預印本 | R02、R03 | arXiv；R03 作者自稱白皮書（arXiv 註記「FinRobot Whitepaper V1.0」） |
| 工程文件（公司文章） | R04 | 工程觀點，非同儕審查 |
| 官方產品文件 | R05、R06、R07 | Google Gemini API 文件，內容隨時更新 |
| 專題實作基線 | R08 | 不是外部學術證據 |

## 閱讀範圍總表

| 卡 | 實際讀到的內容 | 未讀到 |
|---|---|---|
| R01 | arXiv 摘要頁（含版本紀錄與註記）；arXiv HTML 版 v3 的第 1–6 節全文、致謝、可重現性與倫理聲明；ICLR 2023 官方頁面（2026/11/01） | 附錄 A–E 只看標題，未逐段讀；圖片內容未看；OpenReview 頁面未能直接開啟 |
| R02 | arXiv 摘要頁；arXiv HTML 版 v1 的第 1–8 節全文（含第 7 節限制）（2026/11/01） | 附錄 A–D 只看標題；圖片內容未看 |
| R03 | arXiv 摘要頁；arXiv HTML 版 v2 的摘要與第 1–6 節全文（2026/11/01） | 圖片內容未看；第 5.2 節所說「附錄中的研究報告」在 HTML 版中沒有讀到 |
| R04 | 全文（2026-10-31 讀 /research/ 路徑；組長提供的 /engineering/ 網址會轉到 /research/，2026-11-01 由 C 確認為同一篇） | — |
| R05 | 英文原頁 `/docs/function-calling` 全部文字（2026/11/01；程式範例只看結構，未逐行讀） | — |
| R06 | 整頁（2026-10-31） | 帳戶實際額度（頁面本身未列逐模型數字） |
| R07 | 英文頁全頁：方案、各模型章節標題、工具定價、代理定價與附註（2026/11/01） | 各模型價格表的數字未抄錄（依卡片規則不引用價格） |
| R08 | 固定 commit 53816d4 的檔案清單、PROJECT_STATUS.md、requirements.txt，以及 web_app.py、main.py、report_builder.py 的函式名稱與設定（2026-10-31 以 git 取得該 commit） | 各程式的完整邏輯（C 不判定程式正確性） |

---

## R01｜ReAct: Synergizing Reasoning and Acting in Language Models

| 欄位 | 內容 |
|---|---|
| 作者／機構 | Shunyu Yao、Jeffrey Zhao、Dian Yu、Nan Du、Izhak Shafran、Karthik Narasimhan、Yuan Cao；Princeton University 電腦科學系、Google Research（Brain team）（依 HTML 版作者欄） |
| 年份／查閱日 | arXiv v1 2022-10-06、v2 2022-11-27、v3 2023-03-10；arXiv 註記：v3 是 ICLR camera-ready 版本（修正部分錯字）。ICLR 官方頁面列為 ICLR 2023 論文，形式為 poster，標註 top 5% paper。查閱 2026/11/01 |
| 類型 | 會議論文（ICLR 2023）。官方頁面：https://iclr.cc/virtual/2023/poster/11003 |
| 研究問題 | 大型語言模型的推理（如 chain-of-thought）與行動（如行動計畫生成）過去多被當成分開的主題；兩者能否交錯結合，並比單獨推理或單獨行動更好 |
| 方法摘要 | 把代理的行動空間擴充為「原行動集合加上語言空間」：語言空間中的「思考」不影響環境、也不產生觀察，只用來整理目前脈絡、拆解目標、追蹤進度、處理例外，再支援下一步行動。主要以凍結的 PaLM-540B 搭配少量人工示範軌跡做提示，不另外訓練。知識型任務（HotpotQA、FEVER）讓模型透過只有 search、lookup、finish 三種動作的簡易 Wikipedia API 取得資訊，每步都有思考；決策型任務（ALFWorld、WebShop）只在需要時插入思考。另提出 ReAct 與 CoT-SC 依條件互相切換的組合，以及用 ReAct 產生的正確軌跡微調較小模型。作者自述的限制：交錯結構降低推理的彈性，模型會重複先前的思考與動作而跳不出迴圈；搜尋結果無資訊時會帶偏推理；動作空間大的複雜任務需要更多示範，容易超過輸入長度。倫理聲明提到讓模型連接外部環境有風險，實驗只限 Wikipedia 與 WebShop，且動作設計中沒有危險動作 |
| 本專題採用點 | 作為「以行動取得觀察，再調整研究判斷」的概念參考，用於說明 Researcher 取得工具觀察後更新判斷的動機。論文指出的「重複迴圈」與「無資訊搜尋帶偏推理」，可作為說明為何需要停止條件的背景；本專題預算與停止規則本身的依據是組長的程式與狀態機，不是 R01 |
| 不能據此聲稱的結論 | 不引用其一般任務分數作為股價預測能力；不能說 ReAct 證明本系統較準確或可獲利；ReAct 是提示方法，不等於本專題的雙 Agent、預算與 Reviewer 設計；其實驗用 PaLM 與 Wikipedia／ALFWorld／WebShop，不能類推到 Gemini 或財報工具；本專題實作是否採用其格式，待 B／組長確認 |
| 原始 URL | https://arxiv.org/abs/2210.03629（OpenReview 頁面依 ICLR 官方頁面所列為 https://openreview.net/forum?id=WE_vluYUL-X，本次未能直接開啟） |

## R02｜Toolformer: Language Models Can Teach Themselves to Use Tools

| 欄位 | 內容 |
|---|---|
| 作者／機構 | Timo Schick、Jane Dwivedi-Yu、Roberto Dessì、Roberta Raileanu、Maria Lomeli、Luke Zettlemoyer、Nicola Cancedda、Thomas Scialom；Meta AI Research，Roberto Dessì 另屬 Universitat Pompeu Fabra（依 HTML 版作者欄） |
| 年份／查閱日 | arXiv v1 2023-02-09（只有一個版本；摘要頁未列 Comments 與 Journal ref）；查閱 2026/11/01 |
| 類型 | arXiv 預印本（cs.CL）。是否另有正式發表版本，本次未查 |
| 研究問題 | 語言模型在少樣本任務上表現強，卻在算術、事實查詢等基本功能上不穩；模型能否以自監督方式自己學會何時、如何使用外部工具 |
| 方法摘要 | 要求每個工具的輸入與輸出都能寫成文字。流程分三步：先用少量人工示範提示模型，在大量語料中標出可能的 API 呼叫位置與參數；再實際執行這些呼叫；最後只保留「加上呼叫與結果後，能讓模型更容易預測後續文字」的呼叫，用這份資料微調模型本身。推論時，模型產生呼叫符號就暫停解碼、執行 API、把結果插回後繼續。基底模型為 GPT-J（6.7B 參數）。第 3 節列出五種工具：問答系統（Atlas）、Wikipedia 搜尋（BM25）、計算機（只支援四則運算，結果取到小數兩位）、日曆（回傳當天日期）、機器翻譯（NLLB）；摘要則寫作「計算機、問答系統、兩種搜尋引擎、翻譯系統與日曆」。實驗中每個輸入最多只呼叫一次 API。作者自述的限制（第 7 節）：不能串接工具（把一個工具的輸出當另一個的輸入）；不能互動式使用工具（例如改寫查詢、瀏覽多筆結果）；是否呼叫 API 對輸入措辭敏感；有些工具的資料效率很低；決定是否呼叫時沒有考慮呼叫成本 |
| 本專題採用點 | 比較「模型自行決定是否用工具」的設計思想，說明本專題與訓練式方法的差異。R02 自述的限制（不能串接、不能互動補查、不考慮呼叫成本），可作為說明本專題為何以提示加程式預算處理多步工具使用的背景；兩者的對應須 B／組長確認後才寫進正文 |
| 不能據此聲稱的結論 | 本專題沒有做其訓練程序，**不宣稱重現 Toolformer**；不引用其零樣本分數；其工具是輸入輸出皆為文字的簡單 API，不能直接類推到財報資料工具；不能說本專題已解決 R02 所列的限制 |
| 原始 URL | https://arxiv.org/abs/2302.04761 |

## R03｜FinRobot: An Open-Source AI Agent Platform for Financial Applications using Large Language Models

| 欄位 | 內容 |
|---|---|
| 作者／機構 | Hongyang Yang、Boyu Zhang、Neng Wang、Cheng Guo、Xiaoli Zhang、Likun Lin、Junlin Wang、Tianyu Zhou、Mao Guan、Runjia Zhang、Christina Dan Wang，共 11 位；作者欄列有 AI4Finance Foundation、Columbia University、華東師範大學上海 AI 金融學院（Shanghai AI-Finance School ECNU）、NYU Shanghai 等機構（依 HTML 版作者欄；各作者與機構的逐一對應未核對） |
| 年份／查閱日 | arXiv v1 2024-05-23、v2 2024-05-27；arXiv 註記「FinRobot Whitepaper V1.0」；查閱 2026/11/01 |
| 類型 | arXiv 預印本（q-fin.ST），作者自稱白皮書 |
| 研究問題 | 金融業導入 LLM 時，專有資料與專業知識形成障礙；能否以開源的金融專用 Agent 平台降低門檻。引言另列四個待解問題：決策透明度、適應全球市場的多語環境、單一模型的限制、即時資料處理 |
| 方法摘要 | 提出四層平台：金融 AI Agents 層（感知、大腦、行動三個模組；以 Financial CoT 把金融問題拆成步驟；多 Agent 工作流程分 Director、Assistant、LLM Analyst、Financial Analysts 等角色；工具使用分 Text2Params 與 Text2Code）、金融 LLM 演算法層（FinGPT、FinRL、FinML、多模態模型）、LLMOps 與 DataOps 層（以 Smart Scheduler 依評分選擇模型與 Agent；DataOps 含 RAG）、多來源基礎模型層（可插拔多種 LLM）。第 5 節示範兩個應用：Market Forecaster（以新聞與財務資料預測下週股價漲跌，模型為以 LoRA 微調的 Llama-2-7b）與文件分析與報告產生。作者稱其為首個專用於金融分析的 AI Agent 平台（**作者自述**）。引言說第 5 節是兩個示範應用的「效能評估」，但第 5 節內容只有提示範本與兩則示例輸出，沒有讀到量化評估 |
| 本專題採用點 | 金融 Agent 平台的相關工作，作為研究定位參考；可用來對照「多角色、多層架構的平台」與本專題「固定三檔、雙角色、有預算上限」的範圍差異 |
| 不能據此聲稱的結論 | 不以其架構證明本系統可獲利；「首個」為作者自述，引用時須標明；其股價漲跌預測等用途不是本專題範圍，本專題不預測股價；論文沒有量化評估，不能引用為「金融 Agent 已被證明有效」；不比較兩者效能 |
| 原始 URL | https://arxiv.org/abs/2405.14767 |

## R04｜Building effective agents

| 欄位 | 內容 |
|---|---|
| 作者／機構 | Anthropic（頁面載明由 Erik S. 與 Barry Zhang 撰寫） |
| 年份／查閱日 | 2024-12-19 發布；頁面中繼資料顯示 2026-10-09 曾修改；查閱 2026/10/31 |
| 類型 | 公司工程文章，非同儕審查 |
| 研究問題 | 如何建構有效的 LLM Agent，何時該用、何時不該用 |
| 方法摘要 | 把 agentic system 分成兩類：workflow 是 LLM 與工具由預先寫好的程式路徑編排；agent 是 LLM 動態主導自己的流程與工具使用。以「增強型 LLM」（含檢索、工具、記憶）為基本單元，介紹五種 workflow 模式（提示串接、路由、平行化、協調者—工作者、評估者—優化者）。agent 需在每一步從環境取得工具結果等真實回饋，可在檢查點暫停請人判斷，並常設停止條件（如最大迭代次數）。建議先用最簡單的方案，確有成效才增加複雜度；附錄談工具介面設計 |
| 本專題採用點 | 區分 workflow 與 agent，說明「功能多」不等於 Agent；工具設計與停止條件的描述依據 |
| 不能據此聲稱的結論 | 這是工程觀點，不當作嚴格統一的學術定義；不能據此說本系統最佳；頁面自註 2024 年底描述的工具生態已有變化；本專題 Reviewer 與其「評估者—優化者」模式的對應，須 B／D 核准後才寫 |
| 原始 URL | https://www.anthropic.com/engineering/building-effective-agents（組長提供；此網址會轉到 https://www.anthropic.com/research/building-effective-agents，兩者為同一篇，2026-11-01 由 C 確認） |

## R05｜Function calling with the Gemini API

| 欄位 | 內容 |
|---|---|
| 作者／機構 | Google（Gemini API 官方文件） |
| 年份／查閱日 | 頁面標示最後更新 2026-09-23 UTC；查閱 2026/11/01（英文原頁） |
| 類型 | 官方產品文件。分頁標題標示為 Interactions API 版本 |
| 研究問題 | 如何讓模型連接外部工具與 API。頁面列出三種用途：採取行動、擴充知識、延伸能力（如計算或製圖） |
| 方法摘要 | 流程四步：定義函式宣告（名稱、說明、參數）；把使用者提示連同宣告送給模型；**由應用程式自己執行函式**（模型不執行）；把結果送回模型，產生給使用者的回覆。可多輪重複，支援同一輪平行呼叫多個獨立函式，也支援依序串接（組合式呼叫）。函式宣告需有 type、name、description、parameters。呼叫模式以 tool_choice 設定：auto（預設，模型自行決定）、any（一定要呼叫函式）、none（禁止呼叫）、validated（確保符合 schema）。無狀態模式須每次送完整對話歷史，且模型回傳的思考與函式呼叫步驟要原樣送回；範例中，函式結果以 call_id 對應模型的函式呼叫 id。Gemini 3 系列的思考簽章由 SDK 自動處理。最佳實務：說明清楚具體、名稱不含空白與特殊字元、參數用明確型別、同時啟用的工具以 10–20 個為上限、提供脈絡與指示、執行前先驗證函式呼叫、做好錯誤處理、外部 API 使用適當驗證。限制：只支援 OpenAPI schema 的子集；過大或巢狀過深的 schema 可能被拒；Python 支援的參數型別有限。另有遠端 MCP、串流工具呼叫等章節 |
| 本專題採用點 | 說明「模型提出工具呼叫、由程式執行並回傳結果」的分工，以及函式 schema、呼叫模式與錯誤處理的文件依據。實際 SDK 與 API 版本由組長鎖定 |
| 不能據此聲稱的結論 | 範例中的模型名稱不代表本專題採用；文件不證明工具選擇的正確性。英文頁的範例使用 Interactions API（`client.interactions.create`）；本專題程式 `agents/provider.py` 使用 google-genai SDK 的 `models.generate_content`（C 只讀函式名稱，不判定程式）。兩者不是同一套 API 呼叫方式，正文引用時不能把英文頁的步驟寫成本專題的實作細節，**引用哪一版文件待組長決定**。10/31 讀到的日文頁（標題含「Generate Content API (Legacy)」）不再作為本卡依據 |
| 原始 URL | https://ai.google.dev/gemini-api/docs/function-calling |

## R06｜Gemini API rate limits

| 欄位 | 內容 |
|---|---|
| 作者／機構 | Google（Gemini API 官方文件） |
| 年份／查閱日 | 頁面標示最後更新 2026-10-28；查閱 2026/10/31 |
| 類型 | 官方產品文件 |
| 研究問題 | 說明 API 請求如何受速率限制管理 |
| 方法摘要 | 限制以每分鐘請求數（RPM）、每分鐘輸入 token（TPM）、每日請求數（RPD）衡量，任一超限即報錯；以專案而非 API key 計算；每日額度於太平洋時間午夜重置。用量分 Free 與 Tier 1–3，依帳單與累計付款升級。另有以 10 分鐘滾動視窗計算的花費型限制。頁面註明限制不保證，實際額度須在 AI Studio 查看，**頁面本身沒有逐模型的 RPM／TPM 數字** |
| 本專題採用點 | 配額治理的背景；說明為何專題預算要有上限。帳戶實際數字由組長於 W01 保存脫敏紀錄 |
| 不能據此聲稱的結論 | 不能把頁面通則當作本專案帳戶額度；「每 job 8 次發送、10 工具、2 補查輪」是專案內部預算，不是 Google 規定；紀錄不得含 API key |
| 原始 URL | https://ai.google.dev/gemini-api/docs/rate-limits |

## R07｜Gemini Developer API pricing

| 欄位 | 內容 |
|---|---|
| 作者／機構 | Google（Gemini API 官方文件） |
| 年份／查閱日 | 頁面標示最後更新 2026-10-30 UTC；查閱 2026/11/01（英文頁全頁） |
| 類型 | 官方產品文件 |
| 研究問題 | 說明 Gemini Developer API 的方案與計價 |
| 方法摘要 | 分 Free、Paid、Enterprise 三種方案。Free 限部分模型、提供免費 token，內容可能用於改進產品；Paid 提供較高限額、context caching、Batch API，內容不用於改進產品；Enterprise 經 Gemini Enterprise Agent Platform 提供專屬支援等。頁面依模型分節（含本專題使用的 Gemini 3.5 Flash-Lite 一節），各模型分 Standard、Batch、Flex、Priority 計價，部分模型另有僅限受邀的 Contributor 層；部分模型不提供免費層，部分模型標示將於 2026-12-01 或 2027-01-01 調價。後段有工具定價（Google 搜尋與地圖基礎、程式碼執行、網址背景資訊、電腦使用、檔案搜尋等，各自計費）、代理定價與附註（例如 PDF 等文件的 token 以圖片 token 費率計算、頻率限制可能變動、價格可能與 Enterprise 平台不同） |
| 本專題採用點 | 區分免費與付費的使用條件，作為方案選擇的背景；說明工具（如搜尋基礎）可能另外計費 |
| 不能據此聲稱的結論 | 不預測未來價格；論文不抄錄價格數字（易過期）；未經組長提供實際模型、方案與用量，不據此估算專案成本，也不判斷本專題是否適用免費層 |
| 原始 URL | https://ai.google.dev/gemini-api/docs/pricing |

## R08｜fintech-agent 固定版本程式

| 欄位 | 內容 |
|---|---|
| 作者／機構 | GitHub 帳號 kk1030-bit（專案組長） |
| 年份／查閱日 | commit `53816d4fb7d178d309cb556bd55fe9f49533e7e5`，提交於 2026-06-15；其中 PROJECT_STATUS.md 標示最後更新 2026-05-30；查閱 2026/10/31（以 git 取得該 commit，非 main 分支） |
| 類型 | 本專題實作基線，**不是外部學術證據** |
| 研究問題 | 不適用（程式基線）。PROJECT_STATUS.md 的描述是：使用者輸入台股代號後，系統串接 FinMind 與 Supabase，執行財務分析與 DCF 估值，在網頁輸出每股內在價值、財務摘要、優勢、風險與三張圖表 |
| 方法摘要 | 檔案清單包含 PROJECT_STATUS.md、web_app.py、main.py、requirements.txt、report_builder.py、macro_agent／（fred_scraper.py、tw_market_scraper.py、uploader.py 等）、valuation_agent／、fundamental_agent／。requirements.txt 列有 pandas、matplotlib、fpdf2、Flask、gunicorn、supabase、FinMind、fredapi 等套件。web_app.py 是 Flask 入口（首頁、股票清單、分析、輸出檔案路由）；main.py 串接 Supabase、DCF 與報告流程，DCF 的 WACC 預設讀環境變數，未設定時為 0.09；report_builder.py 以 fpdf2 與思源黑體產生 PDF。PROJECT_STATUS.md 記載公開網站部署於 Render Free（512MB），為避免記憶體不足預設略過 PDF，PDF 只在本機產出 |
| 本專題採用點 | 描述「學期初基線」與既有系統限制的依據。V1.2 沿用其中的 Python／Flask、FinMind／FRED、Supabase、DCF、matplotlib、fpdf2（工作包） |
| 不能據此聲稱的結論 | 不是外部學術證據；不代表目前系統現況（現況以 main 分支程式與當週實測為準）；不以檔名推斷功能存在；C 不判定其程式是否正確 |
| 原始 URL | https://github.com/kk1030-bit/fintech-agent/tree/53816d4fb7d178d309cb556bd55fe9f49533e7e5 |

---

## 附加運維連結（不計入 8 筆卡）

- Google Developer Program：https://developers.google.com/program/plans-and-pricing（**未讀**）
- Render Compute：https://render.com/pricing#compute（**未讀**）
- 用途與核對由組長負責。依工作包，Render 2GB 為計畫，不得寫成已部署。

---

## workflow／single agent／dual agent 比較文稿

本節比較三種設計，供方法章與實驗設計章引用。本專題的三種模式在程式中稱為 workflow、single 與 dual（組長 2026-10-24 核定的三模式校準計畫，handoff/calibration-plan-v1.md）。以下用 R01、R02、R04 的概念說明差異，不引用任何效能數字。

**workflow。** R04 把 workflow 定義為由預先寫好的程式路徑編排 LLM 與工具的系統。每一步做什麼由程式決定，模型不決定下一個動作。這類設計的步驟固定，行為較容易預測，也較容易逐步檢查。R04 指出，對任務明確的情境，workflow 能提供可預測性與一致性。本專題的 workflow 模式，是由程式先執行固定的工具，模型只撰稿一次，不自行選工具（組長，agents/research_graph.py）。

**single agent。** R04 把 agent 定義為由 LLM 動態主導自己的流程與工具使用的系統。R01 說明模型交錯產生思考與行動，並用行動取得的觀察更新後續判斷；R02 說明模型可以自行決定呼叫哪個工具、何時呼叫、傳入什麼參數。本專題的 single 模式，是由單一 Researcher 依目前證據選擇工具、取得觀察並決定何時停止，草稿不經 Reviewer 覆核（組長，handoff/state-machine-v1.md）。R04 提醒，agent 常以延遲與成本換取彈性，並可能累積錯誤，需要停止條件與防護。

**dual agent。** 在 single agent 之外，另設一個覆核角色。本專題的 dual 模式，是 Researcher 負責選工具與取得證據，Reviewer 只能使用讀取、財報、總經與計算四類工具，需要查價或搜尋時退回 Researcher（B 核對；agents/prompts/reviewer-v1.2.txt）。只有 dual 模式的草稿會經過覆核。R04 的「評估者—優化者」模式由一個 LLM 產生、另一個提供評估與回饋，與此結構相似，但兩者是否等同，**須 B／D 核准後才能在正文寫成對應**。

**不能據此宣稱的結論。** 三種設計各有取捨，本節不主張任何一種較準確、較省或可帶來獲利。哪一種在本專題表現較好，只能由 D 的正式實驗（20 保留案 × 3 模式 = 60 次執行）回答。

## 待處理事項

| 問題 | 提供人 |
|---|---|
| R05 正文引用英文頁（Interactions API 版本）或 generateContent 版本 | 組長 |
| R01–R03 附錄與圖片內容（目前只讀正文文字；如方法章需引用附錄再補讀） | C |
| R02 是否另有正式發表版本 | C |
| R01 OpenReview 頁面直接核對（目前依 ICLR 官方頁面確認） | C |
| 本專題與 R01、R02、R04 概念的對應是否成立 | B／D |
