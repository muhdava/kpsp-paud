# app/

Kode aplikasi Flask. Dokumentasi lengkap (arsitektur, setup, database, deploy, aturan perhitungan,
pengujian) ada di **[README utama](../README.md)**.

| File | Isi |
|---|---|
| `app.py` | Route, autentikasi & peran, akses database (SQLite lokal / Postgres), dashboard, ekspor CSV, profil & foto |
| `gizi.py` | Hitung umur cara SDIDTK, pilih KPSP, z-score LMS WHO & klasifikasi Permenkes 2/2020, LiLA, LK |
| `data/kpsp.json` | 15 set KPSP (6–72 bulan): 10 pertanyaan + domain + halaman PDF petunjuk |
| `data/who_lms.json` | Tabel LMS WHO (dibangun oleh `tools/buat_who_lms.py`) |
| `templates/` | Halaman Jinja; `base.html` = layout, sidebar, navigasi bawah HP |
| `instance/` | Tidak di-commit: SQLite lokal, `secret_key`, `admin_awal.txt` |

Menjalankan lokal: `python app/app.py` → http://127.0.0.1:5000
