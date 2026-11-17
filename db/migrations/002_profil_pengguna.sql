-- 002_profil_pengguna.sql
-- Kolom profil & foto pengguna (menu Profil). Sama dengan migrasi
-- "kpsp_profil_pengguna" di Supabase produksi.
-- Foto disimpan langsung di database (BYTEA, ±20-40 KB per foto, sudah dikecilkan
-- di browser menjadi JPEG 320x320) sehingga tidak perlu storage terpisah.
ALTER TABLE kpsp.pengguna
  ADD COLUMN IF NOT EXISTS email TEXT,
  ADD COLUMN IF NOT EXISTS jabatan TEXT,
  ADD COLUMN IF NOT EXISTS nip TEXT,
  ADD COLUMN IF NOT EXISTS foto BYTEA,
  ADD COLUMN IF NOT EXISTS foto_tipe TEXT,                       -- image/jpeg | image/png | image/webp
  ADD COLUMN IF NOT EXISTS foto_versi INTEGER NOT NULL DEFAULT 0;  -- naik tiap ganti foto (cache-busting)
