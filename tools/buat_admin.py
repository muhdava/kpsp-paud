"""Buat SQL untuk menambah akun admin / petugas Puskesmas di database Postgres (Supabase).

Password diketik saat dijalankan (tidak tampil di layar), lalu di-hash dengan
werkzeug (sama seperti aplikasi). Salin SQL keluaran ke Supabase SQL Editor.

    python tools/buat_admin.py

Untuk database SQLite lokal tidak perlu skrip ini: akun admin dibuat otomatis saat
`python app/app.py` pertama kali dijalankan (password di app/instance/admin_awal.txt).
"""
import getpass
import re

from werkzeug.security import generate_password_hash


def sql_teks(s):
    return "'" + s.replace("'", "''") + "'"


def main():
    username = input("Username (huruf/angka, mis. admin): ").strip().lower()
    if not re.fullmatch(r"[a-z0-9_.]{3,30}", username):
        raise SystemExit("Username harus 3-30 karakter huruf kecil/angka/titik/garis bawah.")
    nama = input("Nama lengkap: ").strip() or "Petugas Puskesmas"
    pw = getpass.getpass("Password (min. 6, tidak tampil): ")
    if len(pw) < 6 or pw != getpass.getpass("Ulangi password: "):
        raise SystemExit("Password kurang dari 6 karakter atau tidak sama.")
    print("\n-- Jalankan di Supabase SQL Editor:")
    print("INSERT INTO kpsp.pengguna (username, password_hash, nama, peran, aktif)\n"
          f"VALUES ({sql_teks(username)}, {sql_teks(generate_password_hash(pw))}, {sql_teks(nama)}, 'puskesmas', 1);")


if __name__ == "__main__":
    main()
