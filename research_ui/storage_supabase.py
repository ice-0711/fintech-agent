"""Supabase Storage adapter for published report PDFs (W07-A).

Same write-once contract as agents.publication.LocalStorage (put / get / exists). The bucket is
private: the website never hands the browser a Supabase key or a storage URL — PDFs are read on
the server and streamed by /reports/<rv>.pdf and /api/ui/reports/<rv>/download.

Switched on only when all three are set on the server:
    SUPABASE_URL, SUPABASE_SERVICE_KEY (server-side key; never in the frontend), REPORT_STORAGE_BUCKET
Otherwise the local folder is used — and a local folder on Render is NOT permanent storage.

Status: tested with a fake client only. Not verified against a live Supabase project yet
(the lead has not created the test project; decisions-2026-10.md).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from agents.publication import LocalStorage, PublicationError


class SupabaseStorage:
    def __init__(self, client: Any, bucket: str):
        self.bucket = client.storage.from_(bucket)
        self.bucket_name = bucket

    def exists(self, key: str) -> bool:
        folder, _, name = key.rpartition("/")
        rows = self.bucket.list(folder, {"search": name}) or []
        return any(r.get("name") == name for r in rows)

    def put(self, key: str, data: bytes) -> None:
        if self.exists(key):  # write-once, like LocalStorage
            raise PublicationError(f"{key} 已存在，不覆寫")
        self.bucket.upload(key, data, {"content-type": "application/pdf", "upsert": "false"})

    def get(self, key: str) -> bytes:
        return bytes(self.bucket.download(key))


def storage_from_env(local_root: str | Path):
    # REPORT_SUPABASE_* (lead, 10/28) lets reports live in another project than the old site's SUPABASE_URL
    # (on Render that is production; W07 reports go to the test project). Falls back to A's original names.
    url = os.getenv("REPORT_SUPABASE_URL") or os.getenv("SUPABASE_URL")
    key = os.getenv("REPORT_SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    bucket = os.getenv("REPORT_STORAGE_BUCKET")
    if url and key and bucket:
        from supabase import create_client  # noqa: PLC0415

        return SupabaseStorage(create_client(url, key), bucket)
    return LocalStorage(local_root)


def storage_kind(storage: Any) -> str:
    return "supabase" if isinstance(storage, SupabaseStorage) else "local"
