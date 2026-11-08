# Monitoring Skrining KPSP PAUD

Web app untuk guru PAUD/TK mencatat skrining KPSP + antropometri anak, dan petugas Puskesmas memantau hasilnya.

## Menjalankan
```
pip install -r app/requirements.txt
python app/app.py
```
Buka http://127.0.0.1:5000. Saat pertama jalan, akun admin Puskesmas dibuat dan password-nya ditulis di
`app/instance/admin_awal.txt` (ganti setelah login lewat menu nama pengguna). Agar bisa diakses HP guru di jaringan
yang sama: `HOST=0.0.0.0 python app/app.py`.

## Alur
1. Puskesmas login → **Kelurahan & PAUD**: isi daftar kelurahan wilayah kerja.
2. Guru buka **Daftar** → isi nama, nama PAUD/TK, kelurahan → Puskesmas mengaktifkan di menu **Pengguna**.
3. Guru: tambah anak (nama, JK, tgl lahir) → **Skrining**: tgl periksa → umur otomatis → BB/TB/LK/LiLA → status gizi
   otomatis → 10 pertanyaan KPSP sesuai umur (dengan gambar halaman buku) → skor & interpretasi.
4. Puskesmas: **Dashboard** (rekap per kelurahan/PAUD, prioritas kasus), **Data Skrining** (filter + unduh CSV),
   isi **tindak lanjut** per anak yang terlihat oleh guru.

## Aturan perhitungan
- Umur: cara SDIDTK (pinjam 1 bulan = 30 hari), sisa >16 hari dibulatkan 1 bulan; KPSP dipilih kelompok umur
  yang sama atau lebih muda (6, 9, 12, 15, 18, 21, 24, 30, 36, 42, 48, 54, 60, 66, 72 bln).
- KPSP: 9–10 Sesuai umur, 7–8 Meragukan, ≤6 Penyimpangan.
- Gizi (Permenkes 2/2020, z-score LMS WHO): BB/U, PB/U–TB/U, BB/PB–BB/TB, IMT/U (WHO 2007 untuk >60 bln).
  Koreksi ±0,7 cm bila cara ukur tidak sesuai umur. Status gizi utama = BB/PB–BB/TB (≤60 bln) atau IMT/U (>60 bln).
- LiLA 6–59 bln: <11,5 gizi buruk, 11,5–12,4 gizi kurang, ≥12,5 normal. LK/U: <-2 SD mikrosefali, >+2 SD makrosefali.

## Berkas
- `app.py` – server Flask + SQLite (`instance/kpsp.db`)
- `gizi.py` – hitung umur, pilih KPSP, z-score & klasifikasi
- `data/kpsp.json` – pertanyaan KPSP dari Buku Bagan SDIDTK 2022; `data/who_lms.json` – tabel LMS WHO
- `static/kpsp/` – gambar halaman KPSP dari PDF

## Deploy (Vercel + Supabase)
- Database: Supabase project `kpsp-paud`, tabel di schema `kpsp`, diakses role `kpsp_app` (hanya schema itu).
- Bila env `DATABASE_URL` (postgresql://…) diisi, app memakai Postgres; tanpa itu memakai SQLite lokal.
- Vercel: `api/index.py` memuat Flask app, `vercel.json` mengarahkan semua URL ke sana.
- Environment Variables di Vercel: `DATABASE_URL` (pooler Supabase, port 6543) dan `SECRET_KEY`.
