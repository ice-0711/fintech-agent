#!/usr/bin/env python3
"""
scripts/build_snapshot_finmind.py  (組員 B) — V1.5 完整版

從 FinMind 抓 5 檔股票的財報與股價，搭配人工填寫的公告時間、總經與負債覆寫，
產生 data/financial-snapshots.json。

股數與每股淨值口徑（與 data-contract.md V1.3 一致）：
  shares_issued       = 資產負債表 OrdinaryShare（普通股股本，元）÷ 10 元面額 = 發行股數（股）
  treasury_shares     = 資產負債表 NumberOfSharesInEntityHeldByEntityAndByItsSubsidiaries（股）
  shares_outstanding  = shares_issued − treasury_shares（流通在外股數，股）
  bvps                = 歸屬於母公司業主之權益 ÷ shares_outstanding

計息負債（淨負債口徑）：
  計息總負債 = LongtermBorrowings + ShorttermBorrowings + BondsPayable + NotesPayable（應付短期票券）
  淨負債     = 計息總負債 − CashAndCashEquivalents（不含租賃負債）
  NotesPayable 為人工覆寫代號（FinMind 無此科目），來源為 MOPS 原文。

單季 EPS 來源（data-contract.md 第二節第 2-1 條）：
  mops_direct        ：該季有 MOPS 本期原文對帳值，且已通過比對
  finmind_quarterly  ：2025Q4，FinMind 單季值，且通過「全年 − 1–9 月」驗證
  unverified         ：其他情況，尚未有原文比對，不得宣告為已驗證

原則：
- 抓不到、對不上、缺欄位 -> 中止，不補 0、不猜值。
- 人工輸入（公告時間、總經、證據、負債覆寫）都必須通過檢查才會寫入。
- 負債覆寫只能在 FinMind 完全缺值時使用，且必須有 MOPS 來源與說明。
- 原始 FinMind 回應全部存檔並記錄 SHA-256。
- 輸出先寫暫存檔，成功後才取代正式檔，舊檔備份為 .bak。

用法（在 repo 根目錄，Windows CMD）：
  set FINMIND_TOKEN=你的token
  python scripts/build_snapshot_finmind.py --list-types 2317   # 列出科目
  python scripts/build_snapshot_finmind.py                     # 正式產生
  python scripts/build_snapshot_finmind.py --no-control        # 略過 MOPS 對帳（不建議）
  python scripts/build_snapshot_finmind.py --tw-market-only    # 沿用現有快照，只補台股加權指數

人工輸入（必備）：
  data/manual/announce_times.csv
      ticker,period,available_at,source_url
  data/manual/macro.csv
      series_id,observation_date,value,unit,available_at,source

人工輸入（可選）：
  data/manual/evidence.csv
      evidence_version_id,source_id,ticker,title,published_at,captured_at,available_at,source_url,paragraph,abstract
  若不存在，沿用舊版 financial-snapshots.json 內的 evidences，並逐筆驗證 hash。

  data/manual/balance_overrides.csv
      ticker,period,type,value_twd,source_url,note
  僅在 FinMind 完全缺少該科目時使用；FinMind 已有值就會中止。
"""
import argparse
import csv
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

# ============================================================
# 路徑與常數
# ============================================================
API = "https://api.finmindtrade.com/api/v4/data"
TZ = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "finmind"        # 授權：不可轉散布，請加入 .gitignore
MANUAL_DIR = ROOT / "data" / "manual"
OUT = ROOT / "data" / "financial-snapshots.json"
ANNOUNCE_CSV = MANUAL_DIR / "announce_times.csv"
MACRO_CSV = MANUAL_DIR / "macro.csv"
EVIDENCE_CSV = MANUAL_DIR / "evidence.csv"
OVERRIDE_CSV = MANUAL_DIR / "balance_overrides.csv"

COMPANIES = {
    "2330": "台積電",
    "2317": "鴻海",
    "2454": "聯發科技",
    "2379": "瑞昱半導體",
    "3034": "聯詠科技",
}
TICKERS = list(COMPANIES)
PERIODS = ["2025Q2", "2025Q3", "2025Q4", "2026Q1", "2026Q2"]   # 2025Q2 為 YoY 基期
FS_START = "2025-01-01"          # 含 2025Q1，供現金流量差分使用
PRICE_START = "2026-09-10"
CUTOFF = "2026-09-30"
CUTOFF_DT = datetime(2026, 9, 30, 23, 59, 59, tzinfo=TZ)
N_SESSIONS = 5
MACRO_SERIES = {"CPIAUCSL", "FEDFUNDS"}          # macro.csv 人工序列
TW_MARKET_ID = "TAIEX"                           # 台股市場指標：FinMind TaiwanStockPrice data_id=TAIEX
TW_MARKET_START = "2026-01-01"
MACRO_INDICATOR = {"CPIAUCSL": "CPI (美國消費者物價指數)",
                   "FEDFUNDS": "聯邦基金有效利率（月平均）"}
PERIOD_END_MD = {"1": "03-31", "2": "06-30", "3": "09-30", "4": "12-31"}
EVIDENCE_COLS = ["evidence_version_id", "source_id", "ticker", "title", "published_at",
                 "captured_at", "available_at", "source_url", "paragraph", "abstract"]

# ============================================================
# FinMind 科目（已由 --list-types 於 2330、2317、2454、3034、2379 確認）
# ============================================================
FS_TYPES = {                                   # 損益表（單季）
    "revenue": "Revenue",
    "operating_income": "OperatingIncome",
    "net_income": "EquityAttributableToOwnersOfParent",   # 歸屬母公司業主淨利
    "eps": "EPS",
}
BS_EQUITY = "EquityAttributableToOwnersOfParent"    # 歸屬母公司業主權益
BS_CASH = "CashAndCashEquivalents"
BS_ORDINARY = "OrdinaryShare"                       # 普通股股本（元），不含債券換股權利證書
BS_TREASURY = "NumberOfSharesInEntityHeldByEntityAndByItsSubsidiaries"   # 庫藏股股數（股）
PAR_VALUE_TWD = 10                                  # 普通股面額（元）

# 計息負債：LongtermBorrowings 每家必須有；其餘為「公司資料中存在者每季必須有值」
BS_DEBT_REQUIRED = ["LongtermBorrowings"]
BS_DEBT_OPTIONAL = ["ShorttermBorrowings", "BondsPayable", "NotesPayable"]
# NotesPayable（應付短期票券）：FinMind 未提供，僅能以 balance_overrides.csv 人工覆寫

CF_OCF = "CashFlowsFromOperatingActivities"         # 累計值
CF_CAPEX = "PropertyAndPlantAndEquipment"           # 累計值，流出為負

# ============================================================
# 對帳用控制值（MOPS 原文）
# ============================================================
# 營收（億元）與 EPS（元）。有 "eps" 的季別，其 EPS 來源標記為 mops_direct。
CONTROL = {
    # ---- 2026Q2（115 年第 2 季合併綜合損益表，本季欄）----
    ("2330", "2026Q2"): {"revenue": 12703.8025, "eps": 27.25},
    ("2454", "2026Q2"): {"revenue": 1521.8261, "eps": 15.28},
    ("2379", "2026Q2"): {"revenue": 375.5320, "eps": 7.42},
    ("3034", "2026Q2"): {"revenue": 286.6010, "eps": 10.40},     # 銷貨收入淨額＝營業收入合計
    ("2317", "2026Q2"): {"revenue": 25258.9443, "eps": 4.27},

    # ---- 2026Q1（115 年第 1 季合併綜合損益表，本期欄）----
    ("2330", "2026Q1"): {"revenue": 11341.0344, "eps": 22.08},
    ("2454", "2026Q1"): {"revenue": 1491.5051, "eps": 15.17},
    ("2379", "2026Q1"): {"revenue": 364.2257, "eps": 8.44},
    ("3034", "2026Q1"): {"revenue": 231.4530, "eps": 6.19},     # 銷貨收入淨額
    ("2317", "2026Q1"): {"revenue": 21195.3339, "eps": 3.56},

    # ---- 2025Q2、2025Q3（114 年本季欄，或 115 年報表比較欄）----
    ("2330", "2025Q2"): {"eps": 15.36},
    ("2330", "2025Q3"): {"eps": 17.44},
    ("2317", "2025Q2"): {"eps": 3.19},
    ("2317", "2025Q3"): {"eps": 4.15},  
    ("2454", "2025Q2"): {"eps": 17.50},
    ("2454", "2025Q3"): {"eps": 15.84},
    ("2379", "2025Q2"): {"eps": 7.62},
    ("2379", "2025Q3"): {"eps": 6.69},
    ("3034", "2025Q2"): {"eps": 6.14},
    ("3034", "2025Q3"): {"eps": 6.01},
}
# 2025Q4 單季 EPS 驗證：全年 EPS − 1–9 月 EPS 須等於 FinMind 2025Q4 EPS（data-contract 第二節第 2-1 條）
# 來源：MOPS 114 年度與 114 年第 3 季綜合損益表（本期欄）
EPS_FY_CHECK = {
    ("2330", "2025"): {"fy": 66.26, "ytd9": 46.75},
    ("2317", "2025"): {"fy": 13.61, "ytd9": 10.38},
    ("2454", "2025"): {"fy": 66.16, "ytd9": 51.76},
    ("2379", "2025"): {"fy": 28.77, "ytd9": 23.59},
    ("3034", "2025"): {"fy": 26.87, "ytd9": 20.80},
}
EPS_FY_TOL = 0.01        # 允許四捨五入誤差（元）
EPS_SOURCE_MOPS = "mops_direct"
EPS_SOURCE_FINMIND_Q = "finmind_quarterly"
EPS_SOURCE_UNVERIFIED = "unverified"

# 發行股數（百萬股）= MOPS 普通股股本（千元）÷ 10 ÷ 1000，2026Q2（115 年第 2 季報表）
CONTROL_ISSUED_M = {
    ("2330", "2026Q2"): 25932.3701,    # 普通股股本 259,323,701 千元
    ("2454", "2026Q2"): 1603.8954,     # 普通股股本 16,038,954 千元
    ("2379", "2026Q2"): 515.5126,      # 普通股股本 5,155,126 千元
    ("3034", "2026Q2"): 608.5115,      # 普通股股本 6,085,115 千元
    ("2317", "2026Q2"): 14028.6486,    # 普通股股本 140,286,486 千元
}
# 庫藏股股數（股），2026Q2（MOPS 母公司暨子公司所持有之母公司庫藏股股數）
CONTROL_TREASURY = {
    ("2330", "2026Q2"): 0,
    ("2454", "2026Q2"): 7794085,
    ("2379", "2026Q2"): 0,
    ("3034", "2026Q2"): 0,
    ("2317", "2026Q2"): 1483078,
}
SHARE_TOL_M = 0.0001     # 股數對帳容許誤差：100 股（百萬股單位）

RAW_LOG = []


# ============================================================
# 共用工具
# ============================================================
def die(msg):
    sys.exit(f"[中止] {msg}")


def sha256_text(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def parse_ts(s, where):
    try:
        ts = datetime.fromisoformat(s)
    except (ValueError, TypeError):
        die(f"{where}：時間格式錯誤 '{s}'，應為 2026-07-16T14:00:00+08:00")
    if ts.tzinfo is None:
        die(f"{where}：時間缺少時區 '{s}'")
    return ts


def read_csv(path, cols):
    """讀取人工 CSV，回傳 [(行號, dict), ...]；缺欄位、含 '...' 即中止。"""
    if not path.exists():
        die(f"缺少 {path.relative_to(ROOT)}")
    with path.open(encoding="utf-8-sig", newline="") as f:
        rdr = csv.DictReader(f)
        missing = [c for c in cols if c not in (rdr.fieldnames or [])]
        if missing:
            die(f"{path.name} 缺少欄位：{missing}")
        rows = []
        for i, r in enumerate(rdr, start=2):
            clean = {k: (v or "").strip() for k, v in r.items() if k}
            for k, v in clean.items():
                if "..." in v:
                    die(f"{path.name} 第 {i} 列欄位 {k} 含有 '...'，請填入實際值")
            rows.append((i, clean))
    return rows


def fetch(dataset, data_id=None, start=None, end=None):
    """呼叫 FinMind，保存原始回應並記錄 SHA-256。"""
    params = {"dataset": dataset}
    if data_id:
        params["data_id"] = data_id
    if start:
        params["start_date"] = start
    if end:
        params["end_date"] = end
    token = os.environ.get("FINMIND_TOKEN")
    if not token:
        die("未設定 FINMIND_TOKEN（請先執行 set FINMIND_TOKEN=你的token）")
    r = requests.get(API, headers={"Authorization": f"Bearer {token}"},
                     params=params, timeout=60)
    if r.status_code != 200:
        die(f"HTTP {r.status_code}：{dataset} {data_id}")
    js = r.json()
    if js.get("status") != 200:
        die(f"FinMind 回應異常：{dataset} {data_id} -> {js.get('msg')}")
    sha = hashlib.sha256(r.content).hexdigest()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"{dataset}_{data_id or 'ALL'}_{sha[:12]}.json"
    path.write_bytes(r.content)
    RAW_LOG.append({
        "dataset": dataset,
        "data_id": data_id,
        "start": start,
        "end": end,
        "captured_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "sha256": sha,
        "file": f"data/raw/finmind/{path.name}",
    })
    return pd.DataFrame(js.get("data", [])), sha


def to_period(date_str):
    y = date_str[:4]
    m = int(date_str[5:7])
    q = {3: 1, 6: 2, 9: 3, 12: 4}.get(m)
    return f"{y}Q{q}" if q else None


def period_end(period):
    return f"{period[:4]}-{PERIOD_END_MD[period[-1]]}"


def period_end_date(period):
    return datetime.strptime(period_end(period), "%Y-%m-%d").date()


def prev_period(period):
    y, q = int(period[:4]), int(period[-1])
    return None if q == 1 else f"{y}Q{q - 1}"


def wide(df):
    """長表 -> {period: {type: value}}"""
    out = {}
    for _, row in df.iterrows():
        p = to_period(str(row["date"]))
        if p is None:
            continue
        out.setdefault(p, {})[str(row["type"])] = float(row["value"])
    return out


def get(w, period, name, ctx="", required=True):
    v = w.get(period, {}).get(name)
    if v is None and required:
        die(f"{ctx}找不到 {period} 的科目 {name}（請用 --list-types 確認 type 名稱）")
    return v


def single_quarter_cf(cf_w, period, name, ctx=""):
    """現金流量為累計值：Q1 直接用，其餘為本季累計減上一季累計。"""
    cur = get(cf_w, period, name, ctx)
    prev = prev_period(period)
    if prev is None:
        return cur
    return cur - get(cf_w, prev, name, ctx)


# ============================================================
# 人工輸入：公告時間、總經、證據、負債覆寫
# ============================================================
def load_announce():
    out = {}
    for i, r in read_csv(ANNOUNCE_CSV, ["ticker", "period", "available_at", "source_url"]):
        if r["ticker"] not in COMPANIES or r["period"] not in PERIODS:
            continue
        where = f"announce_times.csv 第 {i} 列"
        if not r["available_at"]:
            die(f"{where} 缺 available_at")
        ts = parse_ts(r["available_at"], where)
        if ts > CUTOFF_DT:
            die(f"{where} 公告時間 {ts} 晚於 cutoff {CUTOFF}（防前視）")
        if ts.date() < period_end_date(r["period"]):
            die(f"{where} 公告時間早於期末日 {period_end(r['period'])}，請檢查")
        out[(r["ticker"], r["period"])] = ts
    missing = [(t, p) for t in TICKERS for p in PERIODS if (t, p) not in out]
    if missing:
        die(f"announce_times.csv 缺少 {len(missing)} 列，例如 {missing[:3]}")
    return out


def load_macro():
    out = []
    for i, r in read_csv(MACRO_CSV, ["series_id", "observation_date", "value",
                                     "unit", "available_at", "source"]):
        where = f"macro.csv 第 {i} 列"
        if r["series_id"] not in MACRO_SERIES:
            die(f"{where} series_id 必須是 {sorted(MACRO_SERIES)} 之一")
        if not r["available_at"]:
            die(f"{where} {r['series_id']} 缺 available_at：請到 FRED 或 BLS 查發布日")
        ts = parse_ts(r["available_at"], where)
        if ts > CUTOFF_DT:
            die(f"{where} 發布時間晚於 cutoff，不可使用")
        try:
            val = float(r["value"])
        except ValueError:
            die(f"{where} value 不是數字：'{r['value']}'")
        out.append({
            "series_id": r["series_id"],
            "indicator": MACRO_INDICATOR[r["series_id"]],
            "observation_date": r["observation_date"],
            "available_at": ts.isoformat(timespec="seconds"),
            "value": val,
            "unit": r["unit"],
            "source": r["source"],
        })
    have = {m["series_id"] for m in out}
    if have != MACRO_SERIES:
        die(f"macro.csv 缺少序列：{sorted(MACRO_SERIES - have)}")
    return out


def load_evidence(old):
    if EVIDENCE_CSV.exists():
        out = []
        cols = list(EVIDENCE_COLS)
        for i, r in read_csv(EVIDENCE_CSV, cols):
            where = f"evidence.csv 第 {i} 列"
            if r["ticker"] not in COMPANIES:
                die(f"{where} ticker 不在範圍內")
            if not r["paragraph"]:
                die(f"{where} paragraph 為空")
            ts = parse_ts(r["available_at"], where)
            if ts > CUTOFF_DT:
                die(f"{where} available_at 晚於 cutoff")
            e = {c: r[c] for c in cols}
            e["content_hash"] = sha256_text(r["paragraph"])
            out.append(e)
        return out

    out = []
    for e in old.get("evidences", []):
        if sha256_text(e["paragraph"]) != e.get("content_hash"):
            die(f"{e.get('evidence_version_id')} 的 content_hash 與 paragraph 不符，"
                "請檢查原文或 hash，本程式不會自動改寫")
        out.append(e)
    if not out:
        print("[警告] 沒有證據原文（evidence.csv 不存在，舊檔也沒有 evidences）")
    return out


def load_overrides():
    """
    人工負債覆寫。只在 FinMind 完全缺值時使用，必須有 MOPS 來源與說明。
    回傳 {(ticker, period, type): {...}}
    """
    out = {}
    if not OVERRIDE_CSV.exists():
        return out
    allowed = BS_DEBT_REQUIRED + BS_DEBT_OPTIONAL
    for i, r in read_csv(OVERRIDE_CSV,
                         ["ticker", "period", "type", "value_twd", "source_url", "note"]):
        where = f"balance_overrides.csv 第 {i} 列"
        if r["ticker"] not in COMPANIES or r["period"] not in PERIODS:
            continue
        if r["type"] not in allowed:
            die(f"{where} type 必須是 {allowed} 之一")
        if not r["source_url"].startswith("https://mops.twse.com.tw/"):
            die(f"{where} source_url 必須是 MOPS 網址")
        if not r["note"]:
            die(f"{where} 必須填寫 note")
        try:
            v = float(r["value_twd"])
        except ValueError:
            die(f"{where} value_twd 不是數字：'{r['value_twd']}'")
        if v < 0:
            die(f"{where} value_twd 為負值，負債不可為負")
        key = (r["ticker"], r["period"], r["type"])
        if key in out:
            die(f"{where} 與前面列重複：{key}")
        out[key] = {"value_twd": v, "source_url": r["source_url"], "note": r["note"]}
    return out


# ============================================================
# 單季 EPS 來源判定（data-contract.md 第二節第 2-1 條）
# ============================================================
def eps_source_for(ticker, period, eps, use_control):
    """
    判定單季 EPS 的來源標記。
    - mops_direct：該季有 MOPS 原文對帳值；對帳失敗時 check_control 已中止。
                   使用 --no-control 時不得標為 mops_direct，改為 unverified。
    - finmind_quarterly：2025Q4，FinMind 單季值須通過「全年 − 1–9 月」驗證，否則中止。
    - unverified：其他季別尚無原文比對，不得宣告為已驗證。
    """
    if use_control and "eps" in CONTROL.get((ticker, period), {}):
        return EPS_SOURCE_MOPS

    if period == "2025Q4":
        chk = EPS_FY_CHECK.get((ticker, "2025"))
        if chk is None:
            die(f"[{ticker}] 2025Q4 EPS 缺少全年與 1–9 月驗證值（EPS_FY_CHECK），不得標註來源")
        derived = round(chk["fy"] - chk["ytd9"], 2)
        if abs(eps - derived) > EPS_FY_TOL:
            die(f"[{ticker}] 2025Q4 EPS FinMind {eps} ≠ 全年 {chk['fy']} − 1–9 月 {chk['ytd9']} "
                f"= {derived}，依 data-contract 第二節第 2-1 條須改為 null 並附 missing_reason，請人工確認")
        return EPS_SOURCE_FINMIND_Q

    return EPS_SOURCE_UNVERIFIED


# ============================================================
# FinMind 財報建構
# ============================================================
def debt_value(bs_w, p, name, ctx, ticker, overrides, used):
    """
    取得單一負債科目的值（TWD）。
    - FinMind 有值：直接使用；若同時有覆寫則中止（避免兩個來源衝突）。
    - FinMind 缺值且有覆寫：使用覆寫並記錄。
    - FinMind 缺值且無覆寫：中止。
    """
    v = bs_w.get(p, {}).get(name)
    key = (ticker, p, name)
    if key in overrides:
        if v is not None:
            die(f"{ctx}{p} {name} FinMind 已有值 {v}，覆寫檔不可覆蓋，請刪除該覆寫列")
        used.append({"period": p, "type": name, **overrides[key]})
        return overrides[key]["value_twd"]
    return get(bs_w, p, name, ctx)


def build_company(ticker, announce, overrides, use_control):
    ctx = f"[{ticker}] "
    fs, h1 = fetch("TaiwanStockFinancialStatements", ticker, FS_START, CUTOFF)
    bs, h2 = fetch("TaiwanStockBalanceSheet", ticker, FS_START, CUTOFF)
    cf, h3 = fetch("TaiwanStockCashFlowsStatement", ticker, FS_START, CUTOFF)

    for name, df in (("損益表", fs), ("資產負債表", bs), ("現金流量表", cf)):
        if df.empty:
            die(f"{ctx}{name} 無資料")

    fs_w, bs_w, cf_w = wide(fs), wide(bs), wide(cf)

    # 選用負債科目：FinMind 資料中存在、或有人工覆寫者，每一季都必須有值（或有覆寫）
    present_opt = [t for t in BS_DEBT_OPTIONAL
                   if any(t in row for row in bs_w.values())
                   or any(k[0] == ticker and k[2] == t for k in overrides)]
    absent_opt = [t for t in BS_DEBT_OPTIONAL if t not in present_opt]
    debt_items = BS_DEBT_REQUIRED + present_opt
    raw_hash = hashlib.sha256((h1 + h2 + h3).encode()).hexdigest()

    used_overrides = []
    quarters = []
    for p in PERIODS:
        ts = announce[(ticker, p)]

        # ---- 發行股數：資產負債表普通股股本（元）÷ 10 元面額 ----
        ordinary_twd = get(bs_w, p, BS_ORDINARY, ctx)
        if not (1e9 <= ordinary_twd <= 1e12):
            die(f"{ctx}{p} {BS_ORDINARY}={ordinary_twd} 不在合理範圍，請確認 FinMind 單位為元")
        shares_issued = ordinary_twd / PAR_VALUE_TWD            # 股

        # ---- 庫藏股股數（股）：必填，缺值中止，不補 0 ----
        treasury = get(bs_w, p, BS_TREASURY, ctx)
        if treasury < 0:
            die(f"{ctx}{p} 庫藏股股數為負值（{treasury}），請檢查")
        if treasury >= shares_issued:
            die(f"{ctx}{p} 庫藏股（{treasury}）不可大於或等於發行股數（{shares_issued}）")
        shares_outstanding = shares_issued - treasury           # 股（流通在外）

        # ---- 損益 ----
        revenue = get(fs_w, p, FS_TYPES["revenue"], ctx) / 1e8
        op_raw = get(fs_w, p, FS_TYPES["operating_income"], ctx, required=False)
        net = get(fs_w, p, FS_TYPES["net_income"], ctx) / 1e8
        eps = get(fs_w, p, FS_TYPES["eps"], ctx)
        eps_source = eps_source_for(ticker, p, eps, use_control)

        # ---- 現金流量（累計差分為單季）----
        ocf = single_quarter_cf(cf_w, p, CF_OCF, ctx) / 1e8
        capex_raw = single_quarter_cf(cf_w, p, CF_CAPEX, ctx)
        if capex_raw > 0:
            die(f"{ctx}{p} CapEx 單季為正值（{capex_raw}），請確認現金流量符號")
        capex = -capex_raw / 1e8

        # ---- 資產負債 ----
        equity = get(bs_w, p, BS_EQUITY, ctx)                   # TWD
        cash = get(bs_w, p, BS_CASH, ctx)                       # TWD
        debt = sum(debt_value(bs_w, p, t, ctx, ticker, overrides, used_overrides)
                   for t in debt_items)                         # TWD

        quarters.append({
            "period": p,
            "period_basis": "single_quarter",
            "available_at": ts.isoformat(timespec="seconds"),
            "revenue": round(revenue, 2),
            "operating_income": None if op_raw is None else round(op_raw / 1e8, 2),
            "net_income": round(net, 2),
            "operating_cash_flow": round(ocf, 2),
            "capital_expenditure": round(capex, 2),
            "free_cash_flow": round(ocf - capex, 2),
            "eps": round(eps, 2),
            "eps_source": eps_source,
            "shares_issued": round(shares_issued / 1e6, 4),            # 百萬股
            "treasury_shares": round(treasury / 1e6, 4),               # 百萬股
            "shares_outstanding": round(shares_outstanding / 1e6, 4),  # 百萬股（流通）
            "bvps": round(equity / shares_outstanding, 2),             # 元/股（TWD ÷ 股）
            "net_debt": round((debt - cash) / 1e8, 2),
            "debt_items": debt_items,
            "source_id": f"src-finmind-{ticker}-fs",
            "snapshot_id": f"snap-{ticker}-{p}",
            "content_hash": raw_hash,
        })

    # 覆寫檔中該公司的每一列都必須被實際使用，否則表示填錯期別或科目
    for (t, p, name), _ in overrides.items():
        if t == ticker and name in debt_items and not any(
                u["period"] == p and u["type"] == name for u in used_overrides):
            die(f"{ctx}覆寫檔的 {p} {name} 未被使用，請檢查 period 或 type")

    meta = {
        "debt_items": debt_items,
        "absent_optional_debt": absent_opt,
        "overrides": used_overrides,
        "raw_sha256": {"fs": h1, "bs": h2, "cf": h3},
    }
    return quarters, meta


def check_control(ticker, quarters):
    """營收、EPS、發行股數、庫藏股的 MOPS 對帳。"""
    for q in quarters:
        key = (ticker, q["period"])
        ctl = CONTROL.get(key)
        if ctl:
            if "revenue" in ctl:
                diff = abs(q["revenue"] - ctl["revenue"]) / ctl["revenue"]
                if diff > 0.005:
                    die(f"對帳失敗 {ticker} {q['period']} 營收 {q['revenue']} ≠ 公開值 "
                        f"{ctl['revenue']}（檢查單位、單季或累計、合併或個體）")
            if "eps" in ctl and abs(q["eps"] - ctl["eps"]) > 0.02:
                die(f"對帳失敗 {ticker} {q['period']} EPS {q['eps']} ≠ 公開值 {ctl['eps']}")

        if key in CONTROL_ISSUED_M:
            exp = CONTROL_ISSUED_M[key]
            if abs(q["shares_issued"] - exp) > SHARE_TOL_M:
                die(f"股數對帳失敗 {ticker} {q['period']} 發行股數 {q['shares_issued']} 百萬股 ≠ "
                    f"MOPS 普通股股本換算 {exp}（請檢查 {BS_ORDINARY} 的單位與期別）")

        if key in CONTROL_TREASURY:
            exp_t = CONTROL_TREASURY[key] / 1e6
            if abs(q["treasury_shares"] - exp_t) > SHARE_TOL_M:
                die(f"庫藏股對帳失敗 {ticker} {q['period']} {q['treasury_shares']} 百萬股 ≠ "
                    f"MOPS {exp_t} 百萬股（請檢查 {BS_TREASURY}）")

    if (ticker, "2026Q2") in CONTROL or (ticker, "2026Q2") in CONTROL_ISSUED_M:
        print(f"  對帳通過：{ticker} 2026Q2")
    else:
        print(f"  {ticker} 無對帳值")


# ============================================================
# 股價
# ============================================================
def build_prices(trading_dates):
    prices = {}
    for t in TICKERS:
        df, _ = fetch("TaiwanStockPrice", t, PRICE_START, CUTOFF)
        if df.empty:
            die(f"[{t}] 股價無資料")
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df[(df["close"] > 0) & (df["date"].isin(trading_dates))].sort_values("date")
        rows = df.tail(N_SESSIONS)
        if len(rows) < N_SESSIONS:
            die(f"[{t}] 有效交易日不足 {N_SESSIONS} 天")
        if rows.iloc[-1]["date"] != CUTOFF:
            die(f"[{t}] 最後交易日為 {rows.iloc[-1]['date']}，應為 {CUTOFF}")
        prices[t] = [{"trade_date": r["date"], "close": float(r["close"])}
                     for _, r in rows.iterrows()]
    return prices


# ============================================================
# 台股市場指標（手冊第 02 章白名單：CPI、政策利率、台股市場指標）
# ============================================================
def build_tw_market():
    """每月最後一個交易日之加權指數收盤（未還原），可得時間 = 交易日 17:30 +08:00。"""
    df, sha = fetch("TaiwanStockPrice", TW_MARKET_ID, TW_MARKET_START, CUTOFF)
    if df.empty:
        die(f"FinMind TaiwanStockPrice data_id={TW_MARKET_ID} 無資料")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df[df["close"] > 0].sort_values("date")
    if df.empty:
        die(f"{TW_MARKET_ID} 收盤價皆無效")
    if str(df.iloc[-1]["date"]) != CUTOFF:
        die(f"{TW_MARKET_ID} 最後交易日為 {df.iloc[-1]['date']}，應為 {CUTOFF}")
    df["month"] = df["date"].astype(str).str[:7]
    month_end = df.groupby("month").tail(1)
    rows = []
    for _, r in month_end.iterrows():
        d = str(r["date"])
        rows.append({
            "series_id": TW_MARKET_ID,
            "indicator": "台股加權指數（TAIEX）月底收盤",
            "observation_date": d,
            "available_at": f"{d}T17:30:00+08:00",
            "available_at_basis": "rule_close_1730",
            "value": float(r["close"]),
            "unit": "指數點",
            "source": f"FinMind TaiwanStockPrice data_id={TW_MARKET_ID}（未還原收盤）",
            "source_id": "finmind_tw_market",
            "content_hash": sha,
        })
    print(f"台股市場指標 {TW_MARKET_ID}：{len(rows)} 個月底觀察值（{rows[0]['observation_date']} 至 {rows[-1]['observation_date']}）")
    return rows


def add_tw_market_only():
    """只補 TAIEX：不重抓財報（FinMind 2026-10-20 起 2330 2026Q2 損益表改為 1–6 月累計值，
    整份重抓會被 CONTROL 對帳擋下；已核對之 10/19 快照保持不變）。"""
    if not OUT.exists():
        die("找不到現有 data/financial-snapshots.json，無法只補台股指標")
    snap = json.loads(OUT.read_text(encoding="utf-8"))
    rows = build_tw_market()
    snap["macro"] = [m for m in snap.get("macro", []) if m.get("series_id") != TW_MARKET_ID] + rows
    raw = [r for r in snap["source_manifest"]["raw_files"]
           if not (r["dataset"] == "TaiwanStockPrice" and r["data_id"] == TW_MARKET_ID)]
    snap["source_manifest"]["raw_files"] = raw + RAW_LOG
    snap["source_manifest"]["provider"] = (
        "FinMind（財報、股價、交易日、台股加權指數）；MOPS（公告時間、證據原文、負債覆寫、對帳值，人工）；FRED（總經，人工）")
    snap["manifest_version"] = "v1.6-tw-market"
    snap["tw_market_added_at"] = datetime.now(TZ).isoformat(timespec="seconds")
    snap["tw_market_note"] = ("財報、股價、證據沿用原快照（generated_at 不變）；僅加入 TAIEX 月底收盤。"
                              "FinMind 於 2026-10-20 將 2330 2026Q2 損益表改為 1–6 月累計值，故未重抓財報")
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(OUT, OUT.with_suffix(".json.bak"))
    os.replace(tmp, OUT)
    print(f"已寫入 {OUT.relative_to(ROOT)}（沿用原快照，加入 {len(rows)} 筆 TAIEX；舊檔備份為 .bak）")


# ============================================================
# 科目檢視
# ============================================================
def list_types(ticker):
    for ds in ("TaiwanStockFinancialStatements", "TaiwanStockBalanceSheet",
               "TaiwanStockCashFlowsStatement"):
        df, _ = fetch(ds, ticker, FS_START, CUTOFF)
        print(f"\n== {ds} ==")
        if df.empty:
            print("（無資料）")
            continue
        print(df[["type", "origin_name"]].drop_duplicates().to_string(index=False))


# ============================================================
# 主流程
# ============================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-types", metavar="TICKER")
    ap.add_argument("--no-control", action="store_true", help="略過 MOPS 對帳（不建議）")
    ap.add_argument("--tw-market-only", action="store_true",
                    help="沿用現有已核對快照，只抓台股加權指數 TAIEX 加入 macro；財報、股價、證據不重抓")
    ap.add_argument("--cutoff", help="前瞻快照用（組長 2026-10-21 加入）：YYYY-MM-DDTHH:MM（台北時間），"
                                     "例如 2026-10-30T21:00；預設沿用 2026-09-30")
    ap.add_argument("--out", help="輸出檔（相對 repo 根目錄）。指定 --cutoff 時必填，避免覆蓋實驗用的凍結快照")
    args = ap.parse_args()

    global CUTOFF, CUTOFF_DT, OUT
    if args.cutoff:
        if not args.out:
            die("指定 --cutoff 時必須同時指定 --out（不可覆蓋 data/financial-snapshots.json）")
        CUTOFF_DT = datetime.fromisoformat(args.cutoff).replace(tzinfo=TZ)
        CUTOFF = CUTOFF_DT.date().isoformat()
    if args.out:
        OUT = (ROOT / args.out).resolve()
        if OUT == (ROOT / "data" / "financial-snapshots.json").resolve() and args.cutoff:
            die("--out 不可為 data/financial-snapshots.json")
        OUT.parent.mkdir(parents=True, exist_ok=True)

    if args.list_types:
        list_types(args.list_types)
        return
    if args.tw_market_only:
        add_tw_market_only()
        return

    use_control = not args.no_control

    # 1) 讀取人工輸入（任何一項不合格都會在抓 FinMind 之前中止）
    announce = load_announce()
    macro = load_macro()
    overrides = load_overrides()
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    evidences = load_evidence(old)
    if overrides:
        print(f"載入負債覆寫 {len(overrides)} 列")

    # 2) 抓財報並建構
    financials, meta = {}, {}
    eps_source_count = {EPS_SOURCE_MOPS: 0, EPS_SOURCE_FINMIND_Q: 0, EPS_SOURCE_UNVERIFIED: 0}
    for t in TICKERS:
        print(f"抓取 {t} {COMPANIES[t]} ...")
        qs, m = build_company(t, announce, overrides, use_control)
        if use_control:
            check_control(t, qs)
        else:
            print(f"  [警告] {t} 略過對帳")
        for q in qs:
            eps_source_count[q["eps_source"]] += 1
        financials[t] = {
            "company_name": COMPANIES[t],
            "statement_basis": "consolidated",
            "currency": "TWD",
            "quarters": qs,
        }
        meta[t] = m

    unverified = [(t, q["period"]) for t in TICKERS
                  for q in financials[t]["quarters"] if q["eps_source"] == EPS_SOURCE_UNVERIFIED]
    print(f"單季 EPS 來源統計：{eps_source_count}")
    if unverified:
        print(f"[提醒] 以下 {len(unverified)} 個季別 EPS 為 unverified，尚未有原文比對：{unverified}")

    # 3) 股價
    td, _ = fetch("TaiwanStockTradingDate", start=PRICE_START, end=CUTOFF)
    if td.empty:
        die("TaiwanStockTradingDate 無資料")
    prices = build_prices(set(td["date"]))

    # 3-1) 台股市場指標（加入總經清單；工具白名單由組長於 agents/tools.py 核定）
    macro = macro + build_tw_market()

    # 4) 組合輸出
    out = {
        "manifest_version": "v1.6-tw-market",
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "cutoff": CUTOFF,
        "source_manifest": {
            "provider": "FinMind（財報、股價、交易日、台股加權指數）；MOPS（公告時間、證據原文、負債覆寫、"
                        "對帳值，人工）；FRED（總經，人工）",
            "hash_algorithm": "sha256",
            "statement_basis": "consolidated",
            "statement_basis_note": "假設 FinMind 回傳為合併報表，請以抽查確認",
            "units": {
                "revenue / operating_income / net_income / operating_cash_flow / "
                "capital_expenditure / free_cash_flow / net_debt": "億元 TWD",
                "shares_issued / treasury_shares / shares_outstanding": "百萬股",
                "eps / bvps / prices": "元 TWD",
            },
            "share_definition": {
                "shares_issued": f"資產負債表 {BS_ORDINARY}（普通股股本，元）÷ {PAR_VALUE_TWD} 元面額；"
                                 "不含債券換股權利證書",
                "treasury_shares": f"資產負債表 {BS_TREASURY}",
                "shares_outstanding": "shares_issued − treasury_shares（流通在外股數）",
                "bvps": "歸屬於母公司業主之權益 ÷ shares_outstanding",
            },
            "debt_definition": "計息總負債 = LongtermBorrowings + 公司資料中存在的 ShorttermBorrowings、"
                               "BondsPayable、NotesPayable（應付短期票券，FinMind 無此科目，以 MOPS 人工覆寫）；"
                               "淨負債 = 計息總負債 − CashAndCashEquivalents；不含租賃負債",
            "debt_path_note": "年度 DCF（Supabase 路徑）不計入應付短期票券，與本快照定義不同，"
                              "詳見 data-contract.md 第五節",
            "eps_source_rule": (
                "單季 EPS 依來源標記：mops_direct = 有 MOPS 原文對帳值且已通過比對；"
                "finmind_quarterly = 2025Q4 FinMind 單季值，經全年減 1–9 月驗證；"
                "unverified = 尚無原文比對，不得宣告為已驗證。見 data-contract.md 第二節第 2-1 條"
            ),
            "eps_source_summary": eps_source_count,
            "raw_files": RAW_LOG,
        },
        "debt_items_by_company": {
            t: {"used": meta[t]["debt_items"],
                "absent_optional": meta[t]["absent_optional_debt"]}
            for t in TICKERS
        },
        "debt_overrides": {t: meta[t]["overrides"] for t in TICKERS},
        "evidences": evidences,
        "financials": financials,
        "macro": macro,
        "prices": prices,
    }

    # 5) 原子寫入：先寫暫存檔，成功後替換，舊檔備份為 .bak
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    if OUT.exists():
        os.replace(OUT, OUT.with_suffix(".json.bak"))
    os.replace(tmp, OUT)
    print(f"已寫入 {OUT.relative_to(ROOT)}（原始回應 {len(RAW_LOG)} 份，存於 {RAW_DIR.relative_to(ROOT)}）")


if __name__ == "__main__":
    main()