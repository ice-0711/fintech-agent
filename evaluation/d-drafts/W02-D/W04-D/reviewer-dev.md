# W04-D Reviewer dev 評估（草稿，離線、mock、非真模型）

## 做了什麼
- 寫 Reviewer runtime prompt（約 1,000 字）與輸出 schema，輸出只含 decision / issues / checked_refs / checked_metric_ids / decision_summary，沒有發布欄位。
- 寫離線核對器 reviewer_checks.py：依手冊規則檢查草稿（缺引用、數字無來源、TTM 不連續、YTD 當單季、混幣別、同業含 2330、WACC<=g、available_at 晚於 cutoff、P/E 分母非正、證據衝突未揭露、投資建議、注入文字等）。
- 針對 B 的 10 個 dev 案例，各寫 good / flawed 兩份 mock 草稿，共 20 份（預期 pass 7 / revise 8 / insufficient 5）。
- 測試：64 passed（prompt 規則、schema 與 jsonschema 對照、決定一致性、規則單元測試、20 份草稿比對、工具清單與 repo 對照）。

## 結果（20 份 mock 草稿，核對器輸出 = 預期）
| 案例 | good | flawed |
|---|---|---|
| 01 | pass | revise（ref_missing） |
| 04 | pass | revise（pe_math） |
| 07 | pass | revise（unverified_source, conflict_undisclosed） |
| 08 | pass | revise（同上） |
| 13 | insufficient | insufficient（missing_key_data） |
| 14 | insufficient | insufficient |
| 19 | pass | revise（currency_mixed） |
| 20 | pass | revise（ytd_as_single） |
| 25 | pass | revise（injection_text, recommendation） |
| 26 | insufficient（待 B 確認） | revise（bad_tool_result） |

## 限制（要誠實講）
1. 預期答案是 D 自己依手冊寫的，不是 B 或組長給的標準答案；核對器是規則程式，不是 Gemini。這只證明「規則與 schema 寫得一致」，不證明真模型會照做。
2. 20 份草稿是 D 造的 mock，不是 Researcher 實際輸出。
3. CASE-26 good 的預期結果要看 B 的 allow_insufficient=false 怎麼解讀，未確認。
4. 2317 資料缺，相關案例不能真跑。
5. 全部是草稿，沒有驗收。

## 需要讀來源才答得出的問題（交付要求至少 3 題）
Q1. CASE-07 與 CASE-08 的兩份證據數字不同時，哪一份有 available_at 且不晚於 cutoff？該以哪份為準？（要讀 fixtures/dev/case_fixtures.json 的 evidences）
Q2. CASE-20 的 YTD 數字要拆成單季，需要哪個前期數字？fixture 內有沒有？（要讀 snapshot 的 financial 欄位與 prior period）
Q3. CASE-19 的營收單位與幣別在各證據中如何標示？草稿混用了什麼？（要讀 evidence paragraph）
Q4. CASE-25 的注入文字出現在哪份證據？Reviewer 應當作資料還是指令？（要讀該 evidence 與 prompt 規則）
