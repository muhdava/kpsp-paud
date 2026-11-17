"""Uji alur lengkap aplikasi memakai database SQLite sementara (tidak menyentuh Supabase).

Alur: admin login -> guru daftar -> admin aktifkan -> guru tambah anak & skrining ->
admin dashboard/data/CSV/tindak lanjut -> kelola PAUD/TK -> profil & foto.

    python -m pytest tests -q        # atau: python tests/test_alur.py
"""
import base64
import os
import sqlite3
import sys
import tempfile

_TMP = tempfile.mkdtemp(prefix="kpsp-uji-")
os.environ["KPSP_DB"] = os.path.join(_TMP, "uji.db")
os.environ["ADMIN_PASSWORD"] = "admin-uji-123"
os.environ.pop("DATABASE_URL", None)
os.environ.pop("VERCEL", None)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import app as A  # noqa: E402

# JPEG 1x1 piksel (untuk uji upload foto profil)
JPEG_KECIL = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAMCAgICAgMCAgIDAwMDBAYEBAQEBAgGBgUGCQgKCgkICQkKDA8MCgsOCwkJDRENDg8QEBEQCgwS"
    "ExIQEw8QEBD/yQALCAABAAEBAREA/8wABgAQEAX/2gAIAQEAAD8A0s8g/9k=")


class Klien:
    def __init__(self):
        self.c = A.app.test_client()
        self.c.get("/login")

    def csrf(self):
        with self.c.session_transaction() as s:
            return s.get("csrf")

    def get(self, url):
        return self.c.get(url)

    def post(self, url, **data):
        if not self.csrf():
            self.c.get("/login")
        data["_csrf"] = self.csrf()
        return self.c.post(url, data=data)

    def login(self, u, pw):
        self.c.get("/logout")
        self.c.get("/login")
        return self.post("/login", username=u, password=pw)


def db():
    return sqlite3.connect(os.environ["KPSP_DB"])


def test_alur_lengkap():
    k = Klien()
    assert k.login("admin", "admin-uji-123").status_code == 302
    assert db().execute("select count(*) from kelurahan").fetchone()[0] == 6  # 6 kelurahan tetap otomatis

    # guru mendaftar -> belum aktif -> diaktifkan admin
    k.c.get("/logout")
    kel_id = db().execute("select id from kelurahan where nama='Lagoa'").fetchone()[0]
    k.post("/daftar", nama="Bu Ani", hp="0812", paud="TK Melati", kelurahan_id=str(kel_id),
           username="ani", password="rahasia1")
    assert k.login("ani", "rahasia1").status_code == 200  # ditolak: belum aktif
    k.login("admin", "admin-uji-123")
    uid = db().execute("select id from pengguna where username='ani'").fetchone()[0]
    k.post("/pengguna", aksi="aktifkan", id=str(uid))
    assert k.login("ani", "rahasia1").status_code == 302

    # guru: tambah anak & skrining
    r = k.post("/anak/baru", nama="Budi", jk="L", tgl_lahir="2022-05-10", nama_ortu="Pak Joko")
    assert r.status_code == 302
    aid = r.headers["Location"].split("/")[2]
    assert k.get(f"/anak/{aid}/skrining").status_code == 200
    jaw = {f"q{i}": "Y" for i in range(1, 9)}
    jaw.update(q9="T", q10="T")
    r = k.post(f"/anak/{aid}/skrining", tgl_periksa="2026-11-08", bb="11", tb="95", cara_ukur="berdiri",
               lk="49", lila="12", **jaw)
    assert r.status_code == 302
    sid = r.headers["Location"].split("/")[2]
    assert b"Meragukan" in k.get(f"/skrining/{sid}").data
    for p in ["/guru", f"/anak/{aid}", "/profil"]:
        assert k.get(p).status_code == 200, p
    assert k.get("/dashboard").status_code == 403  # guru tidak boleh ke dashboard

    # admin: dashboard, data, csv, tindak lanjut
    k.login("admin", "admin-uji-123")
    for p in ["/dashboard", "/data", "/data?format=csv", "/data?terakhir=0&kpsp=Meragukan", "/pengguna",
              "/paud", f"/paud?kel={kel_id}", f"/skrining/{sid}"]:
        assert k.get(p).status_code == 200, p
    assert "Budi" in k.get("/data?format=csv").data.decode("utf-8-sig")
    k.post(f"/skrining/{sid}", tindak_lanjut="Evaluasi ulang 2 minggu", catatan_puskesmas="Stimulasi di rumah")
    assert db().execute("select tindak_lanjut from skrining where id=?", (sid,)).fetchone()[0] == "Evaluasi ulang 2 minggu"


def test_kelola_paud_dan_kelurahan_tetap():
    k = Klien()
    k.login("admin", "admin-uji-123")
    assert k.get("/wilayah").status_code == 302  # menu lama dialihkan
    k.post("/paud", aksi="tambah_paud", nama="TK Uji Baru", kelurahan_id="2")
    k.post("/paud", aksi="tambah_kel", nama="Kelurahan Liar")  # harus diabaikan
    assert db().execute("select count(*) from kelurahan").fetchone()[0] == 6
    pid = db().execute("select id from paud where nama='TK Uji Baru'").fetchone()[0]
    k.post("/paud", aksi="ubah_paud", id=str(pid), nama="TK Uji Ganti", kelurahan_id="3")
    assert db().execute("select nama, kelurahan_id from paud where id=?", (pid,)).fetchone() == ("TK Uji Ganti", 3)
    k.post("/paud", aksi="hapus_paud", id=str(pid))
    assert db().execute("select count(*) from paud where id=?", (pid,)).fetchone()[0] == 0


def test_profil_dan_foto():
    k = Klien()
    k.login("admin", "admin-uji-123")
    uid = db().execute("select id from pengguna where username='admin'").fetchone()[0]
    assert k.get("/akun").status_code == 302 and k.get("/profil").status_code == 200
    k.post("/profil", aksi="info", nama="Petugas  Uji", hp="0811", email="uji@contoh.com", jabatan="Bidan", nip="")
    assert db().execute("select nama, jabatan from pengguna where id=?", (uid,)).fetchone() == ("Petugas Uji", "Bidan")
    k.post("/profil", aksi="foto", foto_data="data:image/jpeg;base64," + base64.b64encode(JPEG_KECIL).decode())
    f = k.get(f"/foto/{uid}?v=1")
    assert f.status_code == 200 and f.mimetype == "image/jpeg"
    k.post("/profil", aksi="foto", foto_data="data:image/svg+xml;base64," + base64.b64encode(b"<svg/>").decode())
    assert k.get(f"/foto/{uid}").data[:3] == JPEG_KECIL[:3]  # SVG ditolak, foto lama tetap
    k.post("/profil", aksi="hapus_foto")
    assert k.get(f"/foto/{uid}").status_code == 404


if __name__ == "__main__":
    test_alur_lengkap()
    test_kelola_paud_dan_kelurahan_tetap()
    test_profil_dan_foto()
    print("OK semua uji alur")
