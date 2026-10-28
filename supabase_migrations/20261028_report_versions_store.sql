-- W07-L: report versions in Supabase Postgres so they survive a Render redeploy (decision 2026-10-28).
-- Same columns as agents/publication.py SCHEMA (SQLite), so agents/publication.ReportStore runs the same SQL.
-- job_id is text without a foreign key: research jobs are still stored in SQLite (Supabase job store is later).
-- report_json stays text: the stored string is what report_hash (canonical_hash of its parsed JSON) is checked against.
-- Apply to the TEST project first: scripts/apply_migration.py --env SUPABASE_TEST_DB_URL <this file>

create table if not exists public.report_versions (
    report_version_id text primary key,
    job_id text not null,
    version_no integer not null,
    status text not null check (status in ('draft', 'approved', 'pdf_failed', 'published')),
    report_json text not null,
    report_hash text not null,
    pdf_hash text,
    storage_key text,
    approved_by text,
    approved_at text,
    published_at text,
    failure text,
    created_at text not null,
    unique (job_id, version_no)
);

create index if not exists report_versions_status_published_idx
    on public.report_versions (status, published_at desc);

-- Server-only table: RLS on and no policies, so the anon/authenticated API roles read nothing.
-- The Flask server connects as the database owner through the pooler, which is not subject to RLS.
alter table public.report_versions enable row level security;
