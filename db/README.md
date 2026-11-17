# Database

Aplikasi memakai **PostgreSQL** (di produksi: Supabase, region Singapura) — **bukan MySQL**.
Kode memakai driver `psycopg` (Postgres); untuk pengembangan lokal tanpa Postgres, aplikasi
otomatis memakai **SQLite** (`app/instance/kpsp.db`) bila `DATABASE_URL` tidak diisi.

## Isi folder

| File | Fungsi |
|---|---|
| `migrations/001_skema_awal.sql` | Membuat schema `kpsp` + 5 tabel (kelurahan, paud, pengguna, anak, skrining) dan index |
| `migrations/002_profil_pengguna.sql` | Kolom profil & foto pengguna (email, jabatan, nip, foto) |
| `migrations/003_seed_kelurahan.sql` | Mengisi 6 kelurahan wilayah kerja (tetap) |
| `004_role_aplikasi.sql` | Role `kpsp_app` yang dipakai aplikasi (hak akses hanya ke schema `kpsp`) |
| `../tools/buat_admin.py` | Membuat SQL akun admin Puskesmas dengan password ter-hash |

## Menyiapkan database Postgres/Supabase dari nol

1. Buat project Supabase (region terdekat, mis. `ap-southeast-1` Singapura).
2. Buka **SQL Editor**, jalankan berurutan: `001` → `002` → `003`.
3. Buka `004_role_aplikasi.sql`, ganti `GANTI_DENGAN_PASSWORD_KUAT` dengan password acak, jalankan.
   **Jangan commit password tersebut.**
4. Buat akun admin pertama: `python tools/buat_admin.py`, salin SQL keluarannya ke SQL Editor.
5. Susun `DATABASE_URL` (pooler, transaction mode, port 6543):

   ```
   postgresql://kpsp_app.<PROJECT_REF>:<PASSWORD>@aws-0-<REGION>.pooler.supabase.com:6543/postgres
   ```
   `<PROJECT_REF>` ada di URL dashboard Supabase (`https://supabase.com/dashboard/project/<PROJECT_REF>`).
   Isi variabel ini di Vercel (lihat README utama).

## Catatan desain

- Tabel di schema `kpsp`, bukan `public`, dan hak `anon`/`authenticated` dicabut → data tidak bisa
  dibaca lewat API REST Supabase walau anon key bocor. Hanya aplikasi (role `kpsp_app`) yang mengakses.
- Login dikelola aplikasi sendiri (tabel `pengguna`, hash scrypt werkzeug), **bukan** Supabase Auth.
- Tanggal disimpan sebagai teks ISO (`YYYY-MM-DD`) agar sama di SQLite & Postgres.
- Hasil perhitungan (umur, z-score, status gizi, hasil KPSP) disimpan saat skrining agar riwayat
  tidak berubah walau rumus/tabel diperbarui di kemudian hari.
- Menambah kolom/tabel baru: buat file `migrations/00X_nama.sql`, jalankan di Supabase, dan
  tambahkan juga ke skema SQLite di `app/app.py` (`SKEMA` + bagian `init_db`) agar mode lokal sama.
