# Monitoring KPSP PAUD

Web app untuk **skrining perkembangan (KPSP) dan status gizi anak PAUD/TK**. Guru PAUD/TK mencatat
hasil skrining, petugas **Puskesmas** memantau rekap per kelurahan/PAUD dan mengisi tindak lanjut.

- **Produksi:** https://kpsp-paud.vercel.app
- **Wilayah kerja:** 6 kelurahan tetap — Koja, Lagoa, Tugu Utara, Tugu Selatan, Rawa Badak Selatan, Rawa Badak Utara
- **Acuan:** Buku Bagan SDIDTK (revisi 2022) & Permenkes No. 2 Tahun 2020 tentang Standar Antropometri Anak

---

## Daftar isi
1. [Arsitektur](#1-arsitektur)
2. [Struktur folder](#2-struktur-folder)
3. [Menjalankan di komputer sendiri](#3-menjalankan-di-komputer-sendiri)
4. [Database (Supabase / PostgreSQL)](#4-database-supabase--postgresql)
5. [Deploy ke Vercel](#5-deploy-ke-vercel)
6. [Environment variables](#6-environment-variables)
7. [Peran pengguna & alur aplikasi](#7-peran-pengguna--alur-aplikasi)
8. [Aturan perhitungan](#8-aturan-perhitungan)
9. [Pengujian](#9-pengujian)
10. [Membangun ulang data & aset](#10-membangun-ulang-data--aset)
11. [Keamanan](#11-keamanan)
12. [Catatan untuk pengembang berikutnya](#12-catatan-untuk-pengembang-berikutnya)

---

## 1. Arsitektur

```
Browser (guru / puskesmas, HP atau laptop)
        │
        ▼
┌───────────────────────── Vercel ─────────────────────────┐
│ CDN           : public/static (CSS, JS, gambar KPSP, ikon) │
│ Fungsi Python : api/index.py → Flask (app/app.py)          │
│                 login & sesi, hitung umur/KPSP/z-score,    │
│                 render HTML (Jinja), dashboard, ekspor CSV │
│ Region        : sin1 (Singapura) — dekat database          │
└───────────────────────────┬──────────────────────────────┘
                            │ psycopg, DATABASE_URL (role kpsp_app)
                            ▼
┌──────────────────────── Supabase ────────────────────────┐
│ PostgreSQL, schema `kpsp` (tidak diekspos ke API publik)   │
│ Tidak memakai Supabase Auth / Storage / REST API           │
└──────────────────────────────────────────────────────────┘
```

- **Satu aplikasi Flask** melayani halaman (server-side rendering dengan Jinja) sekaligus logika.
  Tidak ada framework frontend (React dsb.); interaksi memakai JavaScript biasa di `public/static/app.js`.
- **Database:** PostgreSQL bila `DATABASE_URL` diisi; jika kosong otomatis **SQLite** lokal
  (`app/instance/kpsp.db`) — memudahkan pengembangan tanpa Postgres. Kode SQL yang sama berjalan di keduanya
  (kelas `Koneksi` di `app/app.py` mengubah placeholder `?` → `%s` untuk Postgres).
- **Bahasa:** Python 3.12+ (Vercel memakai 3.12), Flask 3, psycopg 3.

## 2. Struktur folder

```
api/index.py              Entry point Vercel → memuat Flask app (menampilkan error start bila gagal)
app/
  app.py                  Seluruh route, akses database, autentikasi, dashboard
  gizi.py                 Hitung umur (cara SDIDTK), pilih KPSP, z-score & klasifikasi gizi
  data/kpsp.json          15 set KPSP (6–72 bulan), 10 pertanyaan + domain + halaman PDF
  data/who_lms.json       Tabel LMS WHO (0–60 bln: WHO 2006; >60 bln: WHO 2007)
  templates/              Halaman Jinja (base.html = layout, sidebar, navigasi bawah HP)
  instance/               (tidak di-commit) SQLite lokal, secret key, password admin lokal
public/
  favicon.ico             Ikon tab browser (dilayani CDN Vercel di /favicon.ico)
  static/                 style.css, nav.css, app.js, ikon, manifest, kpsp/hal_*.png
db/                       Skrip SQL PostgreSQL (migrasi, seed kelurahan, role aplikasi) + README
tools/                    Skrip bantu: buat admin, bangun ulang tabel WHO, gambar KPSP, ikon
tests/                    Uji otomatis (pytest)
vercel.json               Region, fungsi Python, rewrite semua URL ke api/index
requirements.txt          Dependensi produksi (dipakai Vercel)
requirements-dev.txt      Dependensi pengembangan & pengujian
.env.example              Contoh environment variables
```

## 3. Menjalankan di komputer sendiri

```bash
git clone https://github.com/muhdava/kpsp-paud.git
cd kpsp-paud
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python app/app.py
```

Buka http://127.0.0.1:5000. Pada jalan pertama dibuat database SQLite `app/instance/kpsp.db` berisi
6 kelurahan dan akun **admin** — passwordnya tertulis di `app/instance/admin_awal.txt`.

- Agar bisa dibuka dari HP di WiFi yang sama: `HOST=0.0.0.0 python app/app.py`.
- Agar perubahan template langsung terlihat tanpa restart: `DEBUG=1 python app/app.py`
  (tanpa debug, Flask menyimpan template di cache — restart server setelah mengubah HTML).
- Mencoba terhadap database Supabase dari lokal: isi `DATABASE_URL` sebelum menjalankan
  (hati-hati, itu database produksi).

## 4. Database (Supabase / PostgreSQL)

Database produksi: Supabase project **`kpsp-paud`** (region `ap-southeast-1`). Detail skema & cara
menyiapkan dari nol ada di **[db/README.md](db/README.md)**. Ringkasnya, jalankan di Supabase SQL Editor:

1. `db/migrations/001_skema_awal.sql` — schema `kpsp` + tabel
2. `db/migrations/002_profil_pengguna.sql` — kolom profil & foto
3. `db/migrations/003_seed_kelurahan.sql` — 6 kelurahan
4. `db/004_role_aplikasi.sql` — role `kpsp_app` (ganti password dulu, jangan di-commit)
5. `python tools/buat_admin.py` → jalankan SQL keluarannya untuk membuat admin pertama

Tabel: `kelurahan` → `paud` → `pengguna` (guru terikat 1 PAUD) & `anak` → `skrining`.

## 5. Deploy ke Vercel

Repo ini terhubung ke project Vercel **kpsp-paud**: **setiap push ke `main` otomatis deploy ke produksi**.

Untuk project Vercel baru:
1. Vercel → *Add New Project* → import repo ini. Framework preset: biarkan terdeteksi / *Other*.
2. *Settings → Environment Variables*: isi `DATABASE_URL` dan `SECRET_KEY` (tipe **Secret**).
3. Deploy. Bila variabel diubah setelahnya, lakukan **Redeploy** agar terbaca.

Hal teknis yang perlu diketahui (sudah ditangani di kode):
- `vercel.json` me-rewrite semua URL ke `/api/index?__path=/…`; middleware `_PathAsliVercel` di `app/app.py`
  memulihkan path asli. Tanpa ini semua halaman 404.
- File statis harus di `public/` agar dilayani CDN (bukan lewat Python).
- Sistem file Vercel read-only: tanpa `DATABASE_URL` aplikasi menampilkan pesan "Konfigurasi belum lengkap".
- Region fungsi `sin1` agar dekat database Singapura (jauh lebih cepat).
- Koneksi Postgres dipakai ulang per-thread selama fungsi "hangat"; pooler Supabase mode transaksi
  (port 6543) sehingga `prepare_threshold=None`.

## 6. Environment variables

| Nama | Wajib di Vercel | Keterangan |
|---|---|---|
| `DATABASE_URL` | ya | `postgresql://kpsp_app.<ref>:<password>@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres` |
| `SECRET_KEY` | ya | Teks acak panjang untuk cookie sesi (`python -c "import secrets;print(secrets.token_hex(32))"`) |
| `KPSP_DB` | – | Lokasi SQLite lokal (default `app/instance/kpsp.db`) |
| `ADMIN_PASSWORD` | – | Password admin awal SQLite lokal (default acak) |
| `HOST`, `PORT`, `DEBUG` | – | Server lokal |

Contoh lengkap: [.env.example](.env.example). Nilai asli **tidak pernah** di-commit.

## 7. Peran pengguna & alur aplikasi

| Peran | Akses |
|---|---|
| **Guru PAUD/TK** | Data anak PAUD-nya sendiri, tambah/ubah anak, skrining (KPSP + antropometri), melihat tindak lanjut Puskesmas, profil |
| **Puskesmas** | Dashboard rekap, data skrining semua PAUD (filter + ekspor CSV), tindak lanjut, aktivasi guru, kelola PAUD/TK, profil |

Alur: guru **daftar** (`/daftar`, pilih kelurahan & ketik PAUD/TK) → Puskesmas **aktifkan** di menu Pengguna →
guru tambah anak → **skrining** (umur & form KPSP otomatis, status gizi langsung tampil) →
Puskesmas melihat di Dashboard/Data Skrining → isi **tindak lanjut** (terlihat oleh guru).

Halaman utama (`app/app.py`): `/login`, `/daftar`, `/profil`, `/guru`, `/anak/baru`, `/anak/<id>`,
`/anak/<id>/skrining`, `/skrining/<id>`, `/dashboard`, `/data` (`?format=csv`), `/pengguna`, `/paud`,
API pratinjau `/api/hitung` dan `/api/kpsp/<umur>`, foto `/foto/<id>`.

## 8. Aturan perhitungan

Semua di `app/gizi.py`:
- **Umur:** cara Buku Bagan SDIDTK (kurangkan tahun/bulan/hari, pinjam 1 bulan = 30 hari);
  sisa **> 16 hari** dibulatkan 1 bulan.
- **Pilih KPSP:** kelompok 6, 9, 12, 15, 18, 21, 24, 30, 36, 42, 48, 54, 60, 66, 72 bulan; bila umur tidak pas
  dipakai **kelompok lebih muda**; > 72 bulan memakai KPSP 72.
- **Interpretasi KPSP:** 9–10 *Sesuai umur*, 7–8 *Meragukan*, ≤ 6 *Penyimpangan*.
- **Status gizi** (z-score LMS WHO, metode WHO untuk |z| > 3 pada indeks berbasis berat):
  BB/U, PB/U–TB/U, BB/PB–BB/TB, IMT/U dengan kategori Permenkes 2/2020.
  Koreksi ±0,7 cm bila cara ukur tidak sesuai umur (< 24 bln diukur terlentang).
  **Status gizi utama** = BB/PB–BB/TB (≤ 60 bln) atau IMT/U (> 60 bln; BB/U & LK/U tidak dinilai).
- **LiLA** (6–59 bln): < 11,5 gizi buruk; 11,5–12,4 gizi kurang; ≥ 12,5 normal.
- **Lingkar kepala:** < −2 SD mikrosefali, > +2 SD makrosefali.

Hasil perhitungan disimpan bersama data skrining, jadi riwayat tidak berubah bila rumus diperbarui.

## 9. Pengujian

```bash
python -m pytest tests -q
```

- `tests/test_gizi.py` — umur (termasuk contoh resmi buku SDIDTK), pemilihan KPSP, z-score median WHO ≈ 0, klasifikasi.
- `tests/test_alur.py` — alur lengkap memakai SQLite sementara (tidak menyentuh Supabase):
  daftar/aktivasi guru, skrining, dashboard, CSV, tindak lanjut, kelola PAUD, kelurahan tetap, profil & foto.

Jalankan uji sebelum push ke `main` (karena push = langsung produksi).

## 10. Membangun ulang data & aset

| Kebutuhan | Perintah |
|---|---|
| Tabel WHO (`app/data/who_lms.json`) | `python tools/buat_who_lms.py` |
| Gambar halaman KPSP (`public/static/kpsp/`) | `python tools/ekstrak_gambar_kpsp.py BUKU-BAGAN-SDIDTK-revisi-22082022.pdf` |
| Ikon PNG/ICO dari `favicon.svg` | `python tools/buat_ikon.py` |
| Akun admin Puskesmas di Postgres | `python tools/buat_admin.py` |

PDF Buku Bagan SDIDTK tidak disimpan di repo (7,7 MB); teks pertanyaan sudah ada di `app/data/kpsp.json`.

## 11. Keamanan

- Password di-hash (scrypt, werkzeug). Guru baru tidak aktif sampai disetujui Puskesmas.
- Semua form POST memakai token CSRF; cookie sesi `HttpOnly`, `SameSite=Lax`, `Secure` di Vercel.
- Guru hanya bisa melihat/mengubah anak di PAUD-nya; halaman Puskesmas dibatasi peran.
- Foto profil: dikecilkan di browser, server hanya menerima JPEG/PNG/WebP (cek *magic bytes*, maks 400 KB),
  dilayani dengan `X-Content-Type-Options: nosniff` dan hanya untuk pengguna yang login.
- Database: schema `kpsp` tidak diekspos ke API Supabase; aplikasi memakai role `kpsp_app` berhak minimal.
- Rahasia (`DATABASE_URL`, `SECRET_KEY`, password) hanya di Vercel / `app/instance/` (di-ignore Git).
- File Excel/CSV diabaikan Git karena bisa berisi data pribadi anak.

## 12. Catatan untuk pengembang berikutnya

- **Belum ada lingkungan staging:** push ke `main` langsung produksi & memakai database produksi.
  Disarankan: kerja di branch lain (Vercel otomatis membuat Preview URL) dan database terpisah untuk preview.
- **Menambah kolom/tabel:** tulis migrasi baru di `db/migrations/`, jalankan di Supabase, dan perbarui
  `SKEMA`/`init_db` di `app/app.py` agar SQLite lokal ikut sama.
- **Mengubah CSS/JS:** naikkan angka versi `?v=` di `app/templates/base.html` agar browser & CDN mengambil yang baru.
- **Daftar kelurahan** tetap: ubah di `db/migrations/003_seed_kelurahan.sql` dan `KELURAHAN_TETAP` di `app/app.py`.
- Tampilan HP: tabel otomatis menjadi kartu (`public/static/app.js` bagian "Tabel -> kartu"), menu bawah di `nav.css`.
- Ide lanjutan: notifikasi WhatsApp tindak lanjut, grafik pertumbuhan per anak, jadwal skrining ulang
  (meragukan → 2 minggu), ekspor PDF hasil per anak, impor data anak dari Excel.
