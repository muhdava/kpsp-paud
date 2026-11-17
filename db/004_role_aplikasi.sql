-- 004_role_aplikasi.sql
-- Role database khusus aplikasi: hanya boleh baca/tulis tabel di schema kpsp.
-- JANGAN commit password asli. Ganti GANTI_DENGAN_PASSWORD_KUAT sebelum dijalankan
-- (mis. python -c "import secrets;print(secrets.token_urlsafe(24))"),
-- lalu jalankan file ini sekali lewat Supabase SQL Editor.
-- Koneksi aplikasi (pooler Supabase, transaction mode, port 6543):
--   postgresql://kpsp_app.<PROJECT_REF>:<PASSWORD>@aws-0-<REGION>.pooler.supabase.com:6543/postgres

CREATE ROLE kpsp_app LOGIN PASSWORD 'GANTI_DENGAN_PASSWORD_KUAT';
GRANT USAGE ON SCHEMA kpsp TO kpsp_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA kpsp TO kpsp_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA kpsp TO kpsp_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA kpsp GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO kpsp_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA kpsp GRANT USAGE, SELECT ON SEQUENCES TO kpsp_app;
ALTER ROLE kpsp_app SET search_path = kpsp;   -- query aplikasi tanpa prefix "kpsp."
