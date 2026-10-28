-- Rollback for 20261028_report_versions_store.sql. Deletes every stored report version: run only on the TEST project
-- or after exporting the rows. PDFs in Storage are not touched.
drop table if exists public.report_versions;
