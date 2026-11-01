# CR-W08：覆核程式辨識中文金額單位（億、萬、仟、佰、兆）

- 提出：組員 B｜日期：2026-11-01｜檔案：`agents/review_checks.py`（組長，第二段，W09 鎖定前）
- 依據：前瞻第 1 批稽核 `research/forward-batch-1-audit.md` 第三節
- B 只在本機驗證，**沒有修改組長檔案**

## 一、問題

MOPS 第51款新聞稿的金額是中文單位寫法：

| 原文 | 實際金額（元） |
|---|---|
| 5,118億5,700萬元（2330 9 月營收） | 511,857,000,000 |
| 553億9仟9佰萬元（2454 9 月營收） | 55,399,000,000 |
| 1兆4,942億4千萬元（2330 Q3 營收） | 1,494,240,000,000 |
| 1,680億5仟8佰萬元（2454 Q3 營收） | 168,058,000,000 |

現行程式有兩個問題：
1. `paragraph_contains()` 只找完整數字字串，`numbers_in()` 只抓阿拉伯數字。「5,118億5,700萬」會被拆成 5,118 和 5,700，所以不論主張寫 511,857,000,000（元）還是 5,118.57（億元），都會被判「來源不支持」（critical）。第 1 批 2330、2454 都發生了。
2. `find_conflicts()` 把同一關鍵字後的第一個數字拿來比，不分單位：「營收…5,118 億」和「營收增加了 50.9%」被當成衝突。

## 二、建議修改

```python
_BIG = {"兆": 1e12, "億": 1e8, "萬": 1e4}
_SMALL = {"仟": 1e3, "千": 1e3, "佰": 1e2, "百": 1e2}
CN_AMOUNT_RE = re.compile(r"(?:\d[\d,]*(?:\.\d+)?[兆億萬仟千佰百]+)+(?:\d[\d,]*(?:\.\d+)?)?")
_TOKEN = re.compile(r"\d[\d,]*(?:\.\d+)?|[兆億萬仟千佰百]")


def chinese_amounts(text: str) -> list[float]:
    """中文單位金額換成元：5,118億5,700萬 → 511,857,000,000；553億9仟9佰萬 → 55,399,000,000。"""
    out = []
    for m in CN_AMOUNT_RE.finditer(text or ""):
        total, section, last = 0.0, 0.0, None
        for tok in _TOKEN.findall(m.group(0)):
            if tok in _SMALL:
                section += (last or 0) * _SMALL[tok]; last = None
            elif tok in _BIG:
                section += last or 0; last = None
                total += section * _BIG[tok]; section = 0.0
            else:
                last = float(tok.replace(",", ""))
        out.append(total + section + (last or 0))
    return out


def paragraph_contains(paragraph: str, value: float) -> bool:
    for s in num_variants(value):
        if re.search(rf"(?<![\d,.]){re.escape(s)}(?![\d,]|\.\d)", paragraph):
            return True
    # 新增：中文單位金額換算後相符（允許元／千元／萬／億等 UNIT_SCALES 與主張位數的四捨五入）
    return value_matches(value, chinese_amounts(paragraph))
```

`find_conflicts()` 建議只比較**同單位**（億對億、% 對 %）。月營收與季營收屬不同期間，建議只列 minor，或以證據標題的期間區分；這一點請組長決定。

## 三、測試案例（建議加進 `tests/test_review_numbers.py`）

| 輸入 | 預期 |
|---|---|
| `chinese_amounts("合併營收約為新台幣5,118億5,700萬元")` | `[511857000000.0]` |
| `chinese_amounts("553億9仟9佰萬元，較前月641億8仟3佰萬元")` | `[55399000000.0, 64183000000.0]` |
| `chinese_amounts("約新台幣1兆4,942億4千萬元")` | `[1494240000000.0]` |
| `chinese_amounts("稅後純益約新台幣7,630億6千萬元")` | `[763060000000.0]` |
| `chinese_amounts("營業利益為新台幣271億2佰萬元")` | `[27102000000.0]` |
| `chinese_amounts("EPS 29.43元，增加50.9%")` | `[]`（不誤抓） |
| `chinese_amounts("營業收入合計 2,525,894,433 千元")` | `[]`（千元表格維持原路徑） |
| `paragraph_contains("…553億9仟9佰萬元", 55399000000)` | True |
| `paragraph_contains("…553億9仟9佰萬元", 553.99)`（億元） | True |
| `paragraph_contains("…553億9仟9佰萬元", 55300000000)` | **False**（錯的數字仍擋） |
| 第 1 批 2330、2454 草稿 `check_draft` | 不再有 not_supported critical |

B 在 ee7462b 上以 monkeypatch 驗證上表全部成立；30 案凍結資料與 B 的工具都不用改。