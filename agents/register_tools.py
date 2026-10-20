"""agents/register_tools.py
W03-B：把六工具實作掛到 agents.tools._REGISTRY，並加上逾時保護。

- 每次工具呼叫限時 TOOL_TIMEOUT_SECONDS 秒（環境變數可覆寫，預設 15 秒）。
- 逾時拋出 TimeoutError，由 agents.tools.dispatch 包成 status = "tool_error"，
  job 不會崩潰，也不會把未完成的結果當成功（CASE-26）。
- 使用 lambda args: fn(**args)，相容 tools.py 的 impl(args) 字典分發。
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Any, Callable

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

TOOL_TIMEOUT_SECONDS = float(os.environ.get("TOOL_TIMEOUT_SECONDS", "15"))

_IMPLS: dict[str, Callable[..., dict[str, Any]]] = {
    "search_evidence": search_evidence,
    "read_evidence": read_evidence,
    "get_financial_snapshot": get_financial_snapshot,
    "get_macro_snapshot": get_macro_snapshot,
    "get_price_window": get_price_window,
    "calculate_metrics": calculate_metrics,
}


def with_timeout(name: str, fn: Callable[..., dict[str, Any]],
                 seconds: float | None = None) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """包一層逾時；逾時拋 TimeoutError（dispatch 轉 tool_error）。"""
    limit = TOOL_TIMEOUT_SECONDS if seconds is None else seconds

    def run(args: dict[str, Any]) -> dict[str, Any]:
        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"tool-{name}")
        future = pool.submit(fn, **args)
        try:
            return future.result(timeout=limit)
        except FutureTimeout as exc:
            raise TimeoutError(f"{name} 逾時（>{limit:g} 秒）") from exc
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    return run


def init_tools() -> None:
    """將 6 大工具具體實作（含逾時保護）掛載至 agents.tools._REGISTRY"""
    for name, fn in _IMPLS.items():
        register_tool(name, with_timeout(name, fn))


# 模組載入時自動完成註冊
init_tools()
