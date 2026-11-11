# 校準 v2（dual 開發集 10 案）B 抽查紀錄

- 核對對象：D 的 `evaluation/d-drafts/calib-v2-scores-D.txt`（PR #37）與 `evaluation/d-drafts/v12-runner-freeze.md`（PR #38）中請 B 核對的三處。
- 依據：`evaluation/dev-cases.json`、`evaluation/d-drafts/rubric-v1-final.md` 第二節、`evaluation/d-drafts/dev-runs-calib-v2.jsonl`（main edabe63，2026-11-11）。
- 範圍：只用開發集；B 沒有開啟保留集檔案。
- 核對人：B；日期：2026-11-11。

---

## 一、CASE-08 c2（r-62a94938）：建議標 supported

- 案例設定：二手摘要寫 2 兆 2,558.94 億元（未附原始來源），官方為 2 兆 5,258.94 億元；預期拒絕的是「以二手摘要數字作為營收」。
- 依 D 的紀錄，草稿 c2 的寫法是「二手摘要記載 22,558.94 億、未附來源」，是轉述「這份摘要寫了什麼」，不是主張「營收是 22,558.94 億」；營收主張 c1 用的是官方 25,258.94 億，衝突欄也指出兩者不符。
- rubric 的 supported 是「來源原文真的支持這個主張」。c2 主張的內容（摘要記載了這個數字）和證據段落原文一致，所以標 supported；unsupported 是給「主張與來源衝突或用錯口徑」，這裡主張本身沒有和它引用的段落衝突。
- 建議 D 在備註加一句：「c2 為轉述二手來源內容，草稿已在衝突欄指出與官方不符，植入錯誤已被指出且未被採用。」
- 若日後發現草稿把 22,558.94 億當成營收事實陳述，就改標 unsupported。

## 二、CASE-19 整體結果（r-dd480813，11/08 重跑）：建議「符合預期」

- 案例預期：「工具或覆核拒絕錯口徑，修正或 null，不能產生假精確值」；預期拒絕的是「未經匯率換算直接合併的美元與台幣數值」。
- 依 D 的紀錄：草稿指出 USD 與 NTD 混用，兩個數字各自照原幣別轉述並附警告，沒有換算、沒有合併、整份草稿沒有算出新數字。
- 「修正或 null」針對的是會跨幣別運算出來的值；草稿根本沒有產生這種值，等於該值不存在，沒有假精確值，也沒有踩到預期拒絕的主張，所以算符合預期。
- 照實觀察：口徑問題是 Researcher 草稿自己標出來的，不是覆核退回後才修；可在備註註明，不影響整體結果。

## 三、停止原因與執行紀錄：10 列與 jsonl 一致

逐列對照 D 採用的 10 筆（CASE-15、19、26 用 11/08 重跑）與 `dev-runs-calib-v2.jsonl` 的 stop_reason、model_sends、tool_calls、supplement_rounds，全部一致：

| run_id | 案例 | stop_reason | 發送 | 工具 | 補查 |
|---|---|---|---|---|---|
| r-c8cfd1b2 | CASE-01 | review_pass | 6 | 7 | 0 |
| r-6492e510 | CASE-04 | review_pass | 7 | 5 | 0 |
| r-62a94938 | CASE-08 | review_pass | 7 | 7 | 0 |
| r-175607c0 | CASE-11 | review_pass | 7 | 7 | 0 |
| r-90682c88 | CASE-15 | review_insufficient | 8 | 4 | 1 |
| r-b157e23e | CASE-18 | researcher_insufficient | 4 | 3 | 0 |
| r-dd480813 | CASE-19 | review_pass | 6 | 4 | 0 |
| r-6cbc1f73 | CASE-22 | review_pass | 7 | 5 | 0 |
| r-17dedae7 | CASE-26 | review_pass | 5 | 3 | 0 |
| r-27fa6830 | CASE-29 | review_pass | 5 | 4 | 0 |

## 四、D 的保留集接觸紀錄（v12-runner-freeze.md 第五段第 1 點）

- B 無法讀 D 電腦上的存取時間，只能就紀錄本身判斷。
- 兩份副本存取時間只差約 1.5 毫秒，人手不可能在這麼短的時間打開兩個檔，比較像程式或系統依序讀檔；D 本週有執行 `tests/test_formal_runs.py`，該測試會經由 `scripts/formal_runs.py` 由程式自己載入保留集，終端只顯示通過或失敗。
- B 的判斷：這筆存取屬程式讀取、沒有人看到內容，可接受；照實揭露即可，不影響隔離。
- 建議 D 對一下 11/10 16:35 前後是否就是跑測試的時間（例如終端歷史或 `.pytest_cache` 的修改時間）；對得上就把「推測是系統自動掃描」改成「與執行 tests/test_formal_runs.py 的時間一致」，對不上就維持「程式或系統讀取，無法確定」。

## 五、結論

- CASE-08 c2：supported；CASE-19 整體：符合預期。
- 其餘 D 的評分 B 沒有異議；兩人差異已依上列建議，由 D 決定是否修改，組長裁決時兩份原始紀錄都保留。
- D 的接觸紀錄：可接受，照實揭露。
