"""W08-A: the production app (web_app:app) with counters, for the read-only load test.

    W08_COUNTS=path.json gunicorn scripts.w08_counted_wsgi:app --workers 1 --timeout 120

Same app and same gunicorn settings as render.yaml; the only difference is that a few call sites are
wrapped to count calls (they still run normally):
* model requests: google.genai Client creation and models.generate_content, agents.provider.GeminiAdapter
* full-statement fetches of the old homepage: report_downloader.download_financial_report (as used by web_app)
* any outbound network connection that is not loopback (FinMind, Supabase, Gemini, …), by host:port
* report-store database queries and Storage reads (each one is a ~1 s round trip on Render → Supabase)

Counts are rewritten to $W08_COUNTS on every increment, so a run that never increments keeps the zeros.
Not used in production.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

COUNTS_PATH = Path(os.environ.get("W08_COUNTS") or ROOT / "tmp" / "w08-counts.json")
_lock = threading.Lock()
counts: dict[str, object] = {"model_client_created": 0, "model_generate_content": 0, "gemini_adapter_created": 0,
                             "full_statement_fetch": 0, "outbound_connections": 0, "outbound_hosts": {},
                             "report_db_queries": 0, "storage_reads": 0}


def _save() -> None:
    COUNTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    COUNTS_PATH.write_text(json.dumps(counts, ensure_ascii=False, indent=1), encoding="utf-8")


def bump(key: str, host: str | None = None) -> None:
    with _lock:
        counts[key] = int(counts[key]) + 1
        if host:
            hosts = counts["outbound_hosts"]
            hosts[host] = hosts.get(host, 0) + 1
        _save()


_save()

# -- outbound network -----------------------------------------------------------------------------------------
_connect = socket.socket.connect


def _counted_connect(self, address):  # noqa: ANN001
    host = address[0] if isinstance(address, tuple) else str(address)
    if self.family in (socket.AF_INET, socket.AF_INET6) and host not in ("127.0.0.1", "::1", "localhost"):
        bump("outbound_connections", f"{host}:{address[1]}")
    return _connect(self, address)


socket.socket.connect = _counted_connect

# -- model requests -------------------------------------------------------------------------------------------
try:
    from google import genai  # noqa: E402

    _client_init = genai.Client.__init__

    def _counted_client_init(self, *a, **k):  # noqa: ANN001
        bump("model_client_created")
        _client_init(self, *a, **k)
        models = self.models
        _generate = models.generate_content

        def _counted_generate(*ga, **gk):  # noqa: ANN001
            bump("model_generate_content")
            return _generate(*ga, **gk)

        models.generate_content = _counted_generate

    genai.Client.__init__ = _counted_client_init
except ImportError:  # Render does not install google-genai; then no model call is possible at all
    counts["genai_installed"] = False
    _save()

try:
    from agents import provider  # noqa: E402

    _adapter_init = provider.GeminiAdapter.__init__

    def _counted_adapter_init(self, *a, **k):  # noqa: ANN001
        bump("gemini_adapter_created")
        _adapter_init(self, *a, **k)

    provider.GeminiAdapter.__init__ = _counted_adapter_init
except ImportError:
    pass

# -- report store round trips -------------------------------------------------------------------------------
from agents import publication  # noqa: E402

for _cls in (publication._SQLite, publication._Postgres):
    def _wrap(orig):
        def rows(self, *a, **k):  # noqa: ANN001
            bump("report_db_queries")
            return orig(self, *a, **k)
        return rows
    _cls.rows = _wrap(_cls.rows)
_local_get = publication.LocalStorage.get


def _counted_get(self, key):  # noqa: ANN001
    bump("storage_reads")
    return _local_get(self, key)


publication.LocalStorage.get = _counted_get

# -- the app, with the old homepage's full-statement fetch counted ------------------------------------------------
import web_app  # noqa: E402

_download = web_app.download_financial_report


def _counted_download(*a, **k):  # noqa: ANN001
    bump("full_statement_fetch")
    return _download(*a, **k)


web_app.download_financial_report = _counted_download
app = web_app.app
