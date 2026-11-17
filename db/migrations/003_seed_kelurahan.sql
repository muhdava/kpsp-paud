-- 003_seed_kelurahan.sql
-- 6 kelurahan wilayah kerja Puskesmas (tetap; tidak bisa diubah dari aplikasi).
-- Bila wilayah kerja berubah, ubah di sini DAN di app/app.py (KELURAHAN_TETAP).
INSERT INTO kpsp.kelurahan (nama) VALUES
  ('Koja'), ('Lagoa'), ('Tugu Utara'), ('Tugu Selatan'),
  ('Rawa Badak Selatan'), ('Rawa Badak Utara')
ON CONFLICT (nama) DO NOTHING;
