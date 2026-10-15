"""agents/register_tools.py
W03-B / W06 重構版: 工具實作與 tools 註冊器的掛接入口。
使用 lambda args: fn(**args) 封裝，相容 tools.py 的 impl(args) 字典分發機制。
"""
from __future__ import annotations

try:
    from agents.tools import register_tool
    from agents.tools_impl import (
        search_evidence,
        read_evidence,
        get_financial_snapshot,
        get_macro_snapshot,
        get_price_window,
        calculate_metrics,
    )
except ImportError:
    from tools import register_tool  # type: ignore
    from tools_impl import (  # type: ignore
        search_evidence,
        read_evidence,
        get_financial_snapshot,
        get_macro_snapshot,
        get_price_window,
        calculate_metrics,
    )


def init_tools() -> None:
    """將 6 大工具具體實作掛載至 agents.tools._REGISTRY"""
    register_tool("search_evidence", lambda args: search_evidence(**args))
    register_tool("read_evidence", lambda args: read_evidence(**args))
    register_tool("get_financial_snapshot", lambda args: get_financial_snapshot(**args))
    register_tool("get_macro_snapshot", lambda args: get_macro_snapshot(**args))
    register_tool("get_price_window", lambda args: get_price_window(**args))
    register_tool("calculate_metrics", lambda args: calculate_metrics(**args))


# 模組載入時自動完成註冊
init_tools()
