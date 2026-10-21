"""Valuation-gap status and data-quality risk (W05-A), handbook ch.04 F03.

Pure functions, no I/O. Both outputs are *display rules of this project*:

* valuation_status: d = (DCF per share − same-day price) / same-day price.
  d ≥ +15 %  → below_model   「市價低於模型估值」
  d ≤ −15 %  → above_model   「市價高於模型估值」
  otherwise  → near_model    「接近模型估值」
  any key input missing      → undeterminable 「無法判定」
  ±15 % is the project's display threshold, not a validated investment rule.

* data_quality_risk: about the *data*, never about the share price.
  high   — a key item is missing, an unresolved conflict exists, or the
           availability time cannot be shown
  medium — data is marked stale, or only a secondary item is missing
  low    — every predefined check ran and passed
  unassessed — no checks were run (missing data must never look like "low")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

GAP_THRESHOLD = 0.15
METHOD_VERSION = "valuation-gap-v1 (±15%) / data-quality-v1"

VALUATION_LABELS = {
    "below_model": "市價低於模型估值",
    "above_model": "市價高於模型估值",
    "near_model": "接近模型估值",
    "undeterminable": "無法判定",
}
RISK_LABELS = {
    "high": "資料品質風險：高",
    "medium": "資料品質風險：中",
    "low": "資料品質風險：低",
    "unassessed": "資料品質風險：未評估",
}
RISK_FOOTNOTE = "資料品質風險只代表既定資料檢查的結果；「低」不代表股價風險低。"
VALUATION_FOOTNOTE = "±15% 是本專題的顯示門檻，不是經驗證的投資規則；DCF 結果取決於 WACC、g 與 FCF 假設。"

DCF_KEYS = ("free_cash_flows", "wacc", "terminal_growth", "net_debt", "shares_outstanding")
DCF_KEY_NAMES = {"free_cash_flows": "FCF", "wacc": "WACC", "terminal_growth": "g",
                 "net_debt": "淨負債", "shares_outstanding": "流通股數"}


def _num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def valuation_status(dcf_per_share: float | None, price: float | None,
                     dcf_inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return {status, label, gap, reason, missing}. Never guesses a missing input."""

    missing = [DCF_KEY_NAMES[k] for k in DCF_KEYS if dcf_inputs is not None and dcf_inputs.get(k) is None]
    if missing:
        return {"status": "undeterminable", "label": VALUATION_LABELS["undeterminable"], "gap": None,
                "reason": f"缺 DCF 關鍵參數：{'、'.join(missing)}", "missing": missing}
    if not _num(price) or price <= 0:
        return {"status": "undeterminable", "label": VALUATION_LABELS["undeterminable"], "gap": None,
                "reason": "沒有同日收盤價", "missing": ["同日收盤價"]}
    if not _num(dcf_per_share):
        return {"status": "undeterminable", "label": VALUATION_LABELS["undeterminable"], "gap": None,
                "reason": "DCF 每股價值無法計算", "missing": ["DCF 每股價值"]}
    if dcf_per_share <= 0:
        return {"status": "undeterminable", "label": VALUATION_LABELS["undeterminable"], "gap": None,
                "reason": "DCF 每股價值非正（FCF 為負時持平情境不適用）", "missing": []}
    gap = (dcf_per_share - price) / price
    if gap >= GAP_THRESHOLD - 1e-12:
        status = "below_model"
    elif gap <= -GAP_THRESHOLD + 1e-12:
        status = "above_model"
    else:
        status = "near_model"
    return {"status": status, "label": VALUATION_LABELS[status], "gap": round(gap, 4), "reason": None, "missing": []}


@dataclass
class Check:
    """One predefined data check.

    key=True marks a key item (price, TTM EPS, source traceability...).
    result: pass | missing | conflict | time_unknown | stale | not_run
    """

    check_id: str
    label: str
    key: bool
    result: str
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"check_id": self.check_id, "label": self.label, "key": self.key,
                "result": self.result, "detail": self.detail}


@dataclass
class RiskResult:
    level: str
    label: str
    reasons: list[str] = field(default_factory=list)
    checks: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"level": self.level, "label": self.label, "reasons": self.reasons,
                "checks": self.checks, "footnote": RISK_FOOTNOTE}


VALID_RESULTS = ("pass", "missing", "conflict", "time_unknown", "stale", "not_run")


def data_quality_risk(checks: Iterable[Check]) -> RiskResult:
    checks = list(checks)
    for c in checks:
        if c.result not in VALID_RESULTS:
            raise ValueError(f"unknown check result {c.result!r}")
    as_dicts = [c.as_dict() for c in checks]
    ran = [c for c in checks if c.result != "not_run"]
    if not ran:
        return RiskResult("unassessed", RISK_LABELS["unassessed"], ["尚未執行任何資料檢查"], as_dicts)

    high = [c for c in checks if (c.key and c.result in ("missing", "not_run"))
            or c.result in ("conflict", "time_unknown")]
    if high:
        reasons = [f"{c.label}：{c.detail or _RESULT_TEXT[c.result]}" for c in high]
        return RiskResult("high", RISK_LABELS["high"], reasons, as_dicts)

    medium = [c for c in checks if c.result == "stale" or (not c.key and c.result in ("missing", "not_run"))]
    if medium:
        reasons = [f"{c.label}：{c.detail or _RESULT_TEXT[c.result]}" for c in medium]
        return RiskResult("medium", RISK_LABELS["medium"], reasons, as_dicts)

    return RiskResult("low", RISK_LABELS["low"], ["既定資料檢查全部通過"], as_dicts)


_RESULT_TEXT = {
    "missing": "缺值", "conflict": "數字互相矛盾且未解決", "time_unknown": "無法證明可得時間",
    "stale": "資料標示過期", "not_run": "未檢查", "pass": "通過",
}
