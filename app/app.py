"""Web app monitoring skrining KPSP PAUD/TK oleh guru, dipantau petugas Puskesmas."""
import csv
import io
import json
import os
import secrets
import sqlite3
from datetime import date, datetime
from functools import wraps

from flask import (Flask, Response, abort, flash, g, jsonify, redirect,
                   render_template, request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import gizi

BASE = os.path.dirname(os.path.abspath(__file__))
INSTANCE = os.path.join(BASE, "instance")
DB_PATH = os.environ.get("KPSP_DB", os.path.join(INSTANCE, "kpsp.db"))
# Bila DATABASE_URL diisi (mis. Supabase/Postgres) dipakai Postgres; jika tidak, SQLite lokal.
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
PAKAI_PG = DATABASE_URL.startswith(("postgres://", "postgresql://"))
if PAKAI_PG:
    import psycopg
    from psycopg.rows import dict_row
    IntegrityError = (sqlite3.IntegrityError, psycopg.IntegrityError)
else:
    IntegrityError = (sqlite3.IntegrityError,)
    os.makedirs(INSTANCE, exist_ok=True)


def _secret_key():
    os.makedirs(INSTANCE, exist_ok=True)
    p = os.path.join(INSTANCE, "secret_key")
    if not os.path.exists(p):
        with open(p, "w") as f:
            f.write(secrets.token_hex(32))
    return open(p).read().strip()


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or _secret_key()

SKEMA = """
CREATE TABLE IF NOT EXISTS kelurahan (
  id INTEGER PRIMARY KEY, nama TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS paud (
  id INTEGER PRIMARY KEY, nama TEXT NOT NULL, kelurahan_id INTEGER NOT NULL REFERENCES kelurahan(id),
  UNIQUE(nama, kelurahan_id));
CREATE TABLE IF NOT EXISTS pengguna (
  id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
  nama TEXT NOT NULL, hp TEXT, peran TEXT NOT NULL CHECK (peran IN ('guru','puskesmas')),
  paud_id INTEGER REFERENCES paud(id), aktif INTEGER NOT NULL DEFAULT 0,
  dibuat TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS anak (
  id INTEGER PRIMARY KEY, paud_id INTEGER NOT NULL REFERENCES paud(id), nama TEXT NOT NULL,
  jk TEXT NOT NULL CHECK (jk IN ('L','P')), tgl_lahir TEXT NOT NULL, nama_ortu TEXT,
  dibuat_oleh INTEGER REFERENCES pengguna(id), dibuat TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS skrining (
  id INTEGER PRIMARY KEY, anak_id INTEGER NOT NULL REFERENCES anak(id) ON DELETE CASCADE,
  tgl_periksa TEXT NOT NULL, umur_teks TEXT, umur_bulan INTEGER, kpsp_umur INTEGER,
  jawaban TEXT, skor INTEGER, hasil_kpsp TEXT,
  bb REAL, tb REAL, cara_ukur TEXT, lk REAL, lila REAL, imt REAL,
  z_bbu REAL, z_tbu REAL, z_bbtb REAL, z_imtu REAL, z_lku REAL,
  st_bbu TEXT, st_tbu TEXT, st_bbtb TEXT, st_imtu TEXT, st_lku TEXT, st_lila TEXT,
  status_gizi TEXT, masalah_gizi INTEGER, catatan_guru TEXT,
  tindak_lanjut TEXT, catatan_puskesmas TEXT, diverifikasi_oleh INTEGER REFERENCES pengguna(id),
  diverifikasi_pada TEXT, dibuat_oleh INTEGER REFERENCES pengguna(id),
  dibuat TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS ix_skr_anak ON skrining(anak_id);
"""

TINDAK_LANJUT = ["Belum ditindaklanjuti", "Edukasi / stimulasi", "Evaluasi ulang 2 minggu",
                 "Dirujuk ke Puskesmas", "Dirujuk ke RS", "Selesai"]


# ---------------------------------------------------------------- db
class Koneksi:
    """Pembungkus tipis agar kode yang sama jalan di SQLite (lokal) dan Postgres (Supabase)."""

    def __init__(self):
        if PAKAI_PG:
            self.con = psycopg.connect(DATABASE_URL, row_factory=dict_row, prepare_threshold=None,
                                       connect_timeout=10)
        else:
            self.con = sqlite3.connect(DB_PATH)
            self.con.row_factory = lambda c, r: {d[0]: v for d, v in zip(c.description, r)}
            self.con.execute("PRAGMA foreign_keys = ON")

    def execute(self, sql, args=()):
        if PAKAI_PG:
            sql = sql.replace("?", "%s")
        return self.con.execute(sql, args)

    def sisip(self, sql, args=()):
        """INSERT dan kembalikan id baris baru."""
        return self.execute(sql + " RETURNING id", args).fetchone()["id"]

    def commit(self):
        self.con.commit()

    def close(self):
        self.con.close()


def db():
    if "db" not in g:
        g.db = Koneksi()
    return g.db


@app.teardown_appcontext
def _tutup(_):
    d = g.pop("db", None)
    if d:
        d.close()


def q(sql, args=(), satu=False):
    cur = db().execute(sql, args)
    rows = cur.fetchall()
    return (rows[0] if rows else None) if satu else rows


def init_db():
    if PAKAI_PG:  # skema & admin awal Postgres dibuat lewat migrasi Supabase
        return
    con = sqlite3.connect(DB_PATH)
    con.executescript(SKEMA)
    if not con.execute("SELECT 1 FROM pengguna WHERE peran='puskesmas'").fetchone():
        pw = os.environ.get("ADMIN_PASSWORD") or secrets.token_urlsafe(9)
        con.execute("INSERT INTO pengguna (username, password_hash, nama, peran, aktif) "
                    "VALUES ('admin', ?, 'Petugas Puskesmas', 'puskesmas', 1)",
                    (generate_password_hash(pw),))
        with open(os.path.join(INSTANCE, "admin_awal.txt"), "w") as f:
            f.write(f"username: admin\npassword: {pw}\n"
                    "Segera ganti password setelah login (menu Akun).\n")
        print(f"* Akun admin dibuat. Lihat {os.path.join(INSTANCE, 'admin_awal.txt')}")
    con.commit()
    con.close()


# ---------------------------------------------------------------- auth
@app.before_request
def _muat_user():
    g.user = None
    if "uid" in session:
        g.user = q("SELECT p.*, pa.nama AS paud_nama, k.nama AS kelurahan_nama FROM pengguna p "
                   "LEFT JOIN paud pa ON pa.id=p.paud_id LEFT JOIN kelurahan k ON k.id=pa.kelurahan_id "
                   "WHERE p.id=? AND p.aktif=1", (session["uid"],), satu=True)
        if not g.user:
            session.clear()
    if request.method == "POST" and not request.path.startswith("/api/"):
        if request.form.get("_csrf") != session.get("csrf"):
            abort(400, "Token formulir tidak valid, muat ulang halaman.")


@app.context_processor
def _ctx():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return {"user": g.user, "csrf": session["csrf"], "TINDAK_LANJUT": TINDAK_LANJUT}


def perlu_login(peran=None):
    def dec(fn):
        @wraps(fn)
        def w(*a, **kw):
            if not g.user:
                return redirect(url_for("login", next=request.path))
            if peran and g.user["peran"] != peran:
                abort(403)
            return fn(*a, **kw)
        return w
    return dec


@app.route("/")
def index():
    if not g.user:
        return redirect(url_for("login"))
    return redirect(url_for("dashboard" if g.user["peran"] == "puskesmas" else "guru"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = q("SELECT * FROM pengguna WHERE username=?", (request.form["username"].strip().lower(),), satu=True)
        if u and check_password_hash(u["password_hash"], request.form["password"]):
            if not u["aktif"]:
                flash("Akun Anda belum diaktifkan petugas Puskesmas.", "warn")
            else:
                session.clear()
                session["uid"] = u["id"]
                nxt = request.args.get("next", "")
                return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("index"))
        else:
            flash("Username atau password salah.", "err")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/daftar", methods=["GET", "POST"])
def daftar():
    kel = q("SELECT * FROM kelurahan ORDER BY nama")
    if request.method == "POST":
        f = request.form
        username = f["username"].strip().lower()
        nama_paud = " ".join(f["paud"].split())
        if len(f["password"]) < 6:
            flash("Password minimal 6 karakter.", "err")
        elif q("SELECT 1 FROM pengguna WHERE username=?", (username,), satu=True):
            flash("Username sudah dipakai.", "err")
        elif not nama_paud or not f.get("kelurahan_id"):
            flash("Nama PAUD/TK dan kelurahan wajib diisi.", "err")
        else:
            paud = q("SELECT id FROM paud WHERE lower(nama)=lower(?) AND kelurahan_id=?",
                     (nama_paud, f["kelurahan_id"]), satu=True)
            if paud:
                pid = paud["id"]
            else:
                pid = db().sisip("INSERT INTO paud (nama, kelurahan_id) VALUES (?,?)",
                                 (nama_paud, f["kelurahan_id"]))
            db().execute("INSERT INTO pengguna (username,password_hash,nama,hp,peran,paud_id,aktif) "
                         "VALUES (?,?,?,?, 'guru', ?, 0)",
                         (username, generate_password_hash(f["password"]), f["nama"].strip(),
                          f.get("hp", "").strip(), pid))
            db().commit()
            flash("Pendaftaran berhasil. Tunggu aktivasi dari petugas Puskesmas, lalu login.", "ok")
            return redirect(url_for("login"))
    return render_template("daftar.html", kelurahan=kel)


@app.route("/akun", methods=["GET", "POST"])
@perlu_login()
def akun():
    if request.method == "POST":
        if not check_password_hash(g.user["password_hash"], request.form["lama"]):
            flash("Password lama salah.", "err")
        elif len(request.form["baru"]) < 6:
            flash("Password baru minimal 6 karakter.", "err")
        else:
            db().execute("UPDATE pengguna SET password_hash=? WHERE id=?",
                         (generate_password_hash(request.form["baru"]), g.user["id"]))
            db().commit()
            flash("Password diganti.", "ok")
            return redirect(url_for("index"))
    return render_template("akun.html")


# ---------------------------------------------------------------- helpers
def _tgl(s):
    try:
        return date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def boleh_akses_anak(anak):
    if not anak:
        abort(404)
    if g.user["peran"] == "guru" and anak["paud_id"] != g.user["paud_id"]:
        abort(403)


def ambil_anak(aid):
    a = q("SELECT a.*, p.nama AS paud_nama, k.nama AS kelurahan_nama FROM anak a "
          "JOIN paud p ON p.id=a.paud_id JOIN kelurahan k ON k.id=p.kelurahan_id WHERE a.id=?",
          (aid,), satu=True)
    boleh_akses_anak(a)
    return a


def hitung(data):
    """Dipakai oleh API (pratinjau langsung) dan saat menyimpan."""
    lahir, periksa = _tgl(data.get("tgl_lahir")), _tgl(data.get("tgl_periksa"))
    if not lahir or not periksa or periksa < lahir:
        return {"error": "Tanggal lahir / tanggal periksa tidak valid."}
    umur = gizi.hitung_umur(lahir, periksa)
    ku = gizi.pilih_kpsp(umur["bulan_bulat"])
    hasil = {"umur": umur, "kpsp_umur": ku}
    if ku is None:
        hasil["kpsp_info"] = "Umur di bawah 6 bulan: belum ada KPSP pada rentang ini."
    elif umur["bulan_bulat"] > 72:
        hasil["kpsp_info"] = "Umur di atas 72 bulan: digunakan KPSP 72 bulan (kelompok terakhir)."
    if data.get("jk") in ("L", "P"):
        hasil["gizi"] = gizi.status_gizi(data["jk"], umur["bulan_desimal"], data.get("bb"),
                                         data.get("tb"), data.get("cara_ukur"), data.get("lk"),
                                         data.get("lila"))
    return hasil


@app.route("/api/hitung", methods=["POST"])
@perlu_login()
def api_hitung():
    return jsonify(hitung(request.get_json(force=True) or {}))


@app.route("/api/kpsp/<int:umur>")
@perlu_login()
def api_kpsp(umur):
    if umur not in gizi.KPSP:
        abort(404)
    return jsonify(gizi.KPSP[umur])


@app.template_filter("tgl")
def f_tgl(s):
    d = _tgl(str(s)[:10]) if s else None
    if not d:
        return s or "-"
    bln = "Jan Feb Mar Apr Mei Jun Jul Agu Sep Okt Nov Des".split()
    return f"{d.day} {bln[d.month - 1]} {d.year}"


@app.template_filter("warna")
def f_warna(s):
    if not s:
        return "abu"
    if s in ("Sesuai umur", "Normal", "Gizi baik", "Berat badan normal", "Selesai"):
        return "hijau"
    if s in ("Meragukan", "Berisiko gizi lebih", "Risiko berat badan lebih", "Gizi kurang",
             "Pendek", "Berat badan kurang", "Gizi lebih", "Tinggi") or s.startswith("Edukasi") \
            or s.startswith("Evaluasi"):
        return "kuning"
    if s.startswith("Tidak dinilai") or s.startswith("Di luar") or s == "Belum ditindaklanjuti":
        return "abu"
    return "merah"


# ---------------------------------------------------------------- guru
@app.route("/guru")
@perlu_login("guru")
def guru():
    anak = q("""SELECT a.*, s.id AS sid, s.tgl_periksa, s.hasil_kpsp, s.skor, s.status_gizi,
                       s.tindak_lanjut, s.catatan_puskesmas
                FROM anak a LEFT JOIN skrining s ON s.id = (
                  SELECT id FROM skrining WHERE anak_id=a.id ORDER BY tgl_periksa DESC, id DESC LIMIT 1)
                WHERE a.paud_id=? ORDER BY a.nama""", (g.user["paud_id"],))
    hari_ini = date.today()
    daftar = []
    for a in anak:
        u = gizi.hitung_umur(_tgl(a["tgl_lahir"]), hari_ini)
        daftar.append({**dict(a), "umur": u["teks"], "kpsp_sekarang": gizi.pilih_kpsp(u["bulan_bulat"])})
    return render_template("guru.html", anak=daftar)


@app.route("/anak/baru", methods=["GET", "POST"])
@app.route("/anak/<int:aid>/ubah", methods=["GET", "POST"])
@perlu_login("guru")
def anak_form(aid=None):
    a = ambil_anak(aid) if aid else None
    if request.method == "POST":
        f = request.form
        lahir = _tgl(f.get("tgl_lahir"))
        if not f.get("nama", "").strip() or f.get("jk") not in ("L", "P") or not lahir or lahir > date.today():
            flash("Lengkapi nama, jenis kelamin, dan tanggal lahir yang valid.", "err")
        else:
            val = (f["nama"].strip(), f["jk"], lahir.isoformat(), f.get("nama_ortu", "").strip())
            if a:
                db().execute("UPDATE anak SET nama=?, jk=?, tgl_lahir=?, nama_ortu=? WHERE id=?", (*val, a["id"]))
                new_id = a["id"]
            else:
                new_id = db().sisip("INSERT INTO anak (nama,jk,tgl_lahir,nama_ortu,paud_id,dibuat_oleh) "
                                    "VALUES (?,?,?,?,?,?)", (*val, g.user["paud_id"], g.user["id"]))
            db().commit()
            flash("Data anak disimpan.", "ok")
            return redirect(url_for("skrining_baru", aid=new_id) if not a else url_for("anak_detail", aid=new_id))
    return render_template("anak_form.html", a=a)


@app.route("/anak/<int:aid>")
@perlu_login()
def anak_detail(aid):
    a = ambil_anak(aid)
    riwayat = q("SELECT * FROM skrining WHERE anak_id=? ORDER BY tgl_periksa DESC, id DESC", (aid,))
    return render_template("anak_detail.html", a=a, riwayat=riwayat,
                           umur=gizi.hitung_umur(_tgl(a["tgl_lahir"]), date.today()))


@app.route("/anak/<int:aid>/hapus", methods=["POST"])
@perlu_login("guru")
def anak_hapus(aid):
    ambil_anak(aid)
    db().execute("DELETE FROM skrining WHERE anak_id=?", (aid,))
    db().execute("DELETE FROM anak WHERE id=?", (aid,))
    db().commit()
    flash("Data anak dihapus.", "ok")
    return redirect(url_for("guru"))


@app.route("/anak/<int:aid>/skrining", methods=["GET", "POST"])
@perlu_login("guru")
def skrining_baru(aid):
    a = ambil_anak(aid)
    if request.method == "POST":
        f = request.form
        data = {k: f.get(k) for k in ("tgl_periksa", "bb", "tb", "cara_ukur", "lk", "lila")}
        data.update(tgl_lahir=a["tgl_lahir"], jk=a["jk"])
        h = hitung(data)
        if "error" in h:
            flash(h["error"], "err")
            return redirect(request.url)
        if _tgl(data["tgl_periksa"]) > date.today():
            flash("Tanggal periksa tidak boleh di masa depan.", "err")
            return redirect(request.url)
        ku = h["kpsp_umur"]
        jawaban = "".join("Y" if f.get(f"q{i}") == "Y" else ("T" if f.get(f"q{i}") == "T" else "-")
                          for i in range(1, 11)) if ku else ""
        if ku and "-" in jawaban:
            flash("Semua 10 pertanyaan KPSP harus dijawab Ya/Tidak.", "err")
            return redirect(request.url)
        skor = jawaban.count("Y") if ku else None
        hasil = gizi.interpretasi_kpsp(skor) if ku else None
        gz = h.get("gizi", {})
        z = lambda k: (gz.get(k) or {}).get("z")
        st = lambda k: (gz.get(k) or {}).get("status")
        num = lambda k: gizi._f(f.get(k))
        sid = db().sisip(
            """INSERT INTO skrining (anak_id,tgl_periksa,umur_teks,umur_bulan,kpsp_umur,jawaban,skor,hasil_kpsp,
               bb,tb,cara_ukur,lk,lila,imt,z_bbu,z_tbu,z_bbtb,z_imtu,z_lku,st_bbu,st_tbu,st_bbtb,st_imtu,st_lku,
               st_lila,status_gizi,masalah_gizi,catatan_guru,tindak_lanjut,dibuat_oleh)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (aid, data["tgl_periksa"], h["umur"]["teks"], h["umur"]["bulan_bulat"], ku, jawaban, skor, hasil,
             num("bb"), num("tb"), f.get("cara_ukur"), num("lk"), num("lila"), gz.get("imt"),
             z("bbu"), z("tbu"), z("bbtb"), z("imtu"), z("lku"),
             st("bbu"), st("tbu"), st("bbtb"), st("imtu"), st("lku"), st("lila"),
             gz.get("status_gizi"), int(gizi.ada_masalah_gizi(gz)) if gz else 0,
             f.get("catatan_guru", "").strip(), "Belum ditindaklanjuti", g.user["id"]))
        db().commit()
        flash("Hasil skrining disimpan.", "ok")
        return redirect(url_for("skrining_detail", sid=sid))
    return render_template("skrining_form.html", a=a, hari_ini=date.today().isoformat())


@app.route("/skrining/<int:sid>", methods=["GET", "POST"])
@perlu_login()
def skrining_detail(sid):
    s = q("SELECT * FROM skrining WHERE id=?", (sid,), satu=True)
    if not s:
        abort(404)
    a = ambil_anak(s["anak_id"])
    if request.method == "POST":
        if g.user["peran"] != "puskesmas":
            abort(403)
        tl = request.form.get("tindak_lanjut")
        if tl not in TINDAK_LANJUT:
            abort(400)
        db().execute("UPDATE skrining SET tindak_lanjut=?, catatan_puskesmas=?, diverifikasi_oleh=?, "
                     "diverifikasi_pada=? WHERE id=?",
                     (tl, request.form.get("catatan_puskesmas", "").strip(), g.user["id"],
                      datetime.now().isoformat(timespec="minutes"), sid))
        db().commit()
        flash("Tindak lanjut disimpan.", "ok")
        return redirect(url_for("skrining_detail", sid=sid))
    soal = gizi.KPSP.get(s["kpsp_umur"]) if s["kpsp_umur"] else None
    verif = q("SELECT nama FROM pengguna WHERE id=?", (s["diverifikasi_oleh"],), satu=True) \
        if s["diverifikasi_oleh"] else None
    guru_ = q("SELECT nama FROM pengguna WHERE id=?", (s["dibuat_oleh"],), satu=True)
    return render_template("skrining_detail.html", s=s, a=a, soal=soal, verif=verif, guru=guru_,
                           tindakan=gizi.TINDAKAN_KPSP.get(s["hasil_kpsp"]))


@app.route("/skrining/<int:sid>/hapus", methods=["POST"])
@perlu_login()
def skrining_hapus(sid):
    s = q("SELECT * FROM skrining WHERE id=?", (sid,), satu=True)
    if not s:
        abort(404)
    ambil_anak(s["anak_id"])
    db().execute("DELETE FROM skrining WHERE id=?", (sid,))
    db().commit()
    flash("Data skrining dihapus.", "ok")
    return redirect(url_for("anak_detail", aid=s["anak_id"]))


# ---------------------------------------------------------------- puskesmas
def _filter():
    f = request.args
    w, p = ["1=1"], []
    if f.get("kelurahan"):
        w.append("k.id=?"); p.append(f["kelurahan"])
    if f.get("paud"):
        w.append("pa.id=?"); p.append(f["paud"])
    if f.get("dari"):
        w.append("s.tgl_periksa>=?"); p.append(f["dari"])
    if f.get("sampai"):
        w.append("s.tgl_periksa<=?"); p.append(f["sampai"])
    if f.get("kpsp"):
        w.append("s.hasil_kpsp=?"); p.append(f["kpsp"])
    if f.get("gizi"):
        w.append("s.status_gizi=?"); p.append(f["gizi"])
    if f.get("tl"):
        w.append("s.tindak_lanjut=?"); p.append(f["tl"])
    if f.get("cari"):
        w.append("lower(a.nama) LIKE lower(?)"); p.append(f"%{f['cari']}%")
    if f.get("terakhir", "1") == "1":
        w.append("s.id = (SELECT id FROM skrining WHERE anak_id=a.id ORDER BY tgl_periksa DESC, id DESC LIMIT 1)")
    return " AND ".join(w), p


BASE_SQL = """FROM skrining s JOIN anak a ON a.id=s.anak_id JOIN paud pa ON pa.id=a.paud_id
              JOIN kelurahan k ON k.id=pa.kelurahan_id"""


@app.route("/dashboard")
@perlu_login("puskesmas")
def dashboard():
    w, p = _filter()
    rows = q(f"SELECT s.*, a.nama AS anak, a.jk, pa.nama AS paud, k.nama AS kelurahan {BASE_SQL} WHERE {w}", p)
    total = len(rows)

    def hitung_by(key, urutan=None):
        d = {}
        for r in rows:
            d[r[key] or "Tidak ada data"] = d.get(r[key] or "Tidak ada data", 0) + 1
        if urutan:
            return [(k, d.get(k, 0)) for k in urutan] + [(k, v) for k, v in d.items() if k not in urutan]
        return sorted(d.items(), key=lambda x: -x[1])

    kpsp = hitung_by("hasil_kpsp", ["Sesuai umur", "Meragukan", "Penyimpangan"])
    gz = hitung_by("status_gizi", ["Gizi buruk", "Gizi kurang", "Gizi baik", "Berisiko gizi lebih",
                                   "Gizi lebih", "Obesitas"])
    tbu = hitung_by("st_tbu", ["Sangat pendek", "Pendek", "Normal", "Tinggi"])
    tl = hitung_by("tindak_lanjut", TINDAK_LANJUT)

    per_kel = {}
    for r in rows:
        k = per_kel.setdefault(r["kelurahan"], {"total": 0, "Sesuai umur": 0, "Meragukan": 0,
                                                 "Penyimpangan": 0, "gizi": 0, "pendek": 0, "paud": set()})
        k["total"] += 1
        k["paud"].add(r["paud"])
        if r["hasil_kpsp"] in k:
            k[r["hasil_kpsp"]] += 1
        k["gizi"] += 1 if r["masalah_gizi"] else 0
        k["pendek"] += 1 if r["st_tbu"] in ("Pendek", "Sangat pendek") else 0
    per_paud = {}
    for r in rows:
        k = per_paud.setdefault((r["paud"], r["kelurahan"]), {"total": 0, "Sesuai umur": 0, "Meragukan": 0,
                                                                "Penyimpangan": 0, "gizi": 0})
        k["total"] += 1
        if r["hasil_kpsp"] in k:
            k[r["hasil_kpsp"]] += 1
        k["gizi"] += 1 if r["masalah_gizi"] else 0

    prioritas = [r for r in rows if (r["hasil_kpsp"] in ("Penyimpangan", "Meragukan") or r["masalah_gizi"])
                 and r["tindak_lanjut"] in (None, "Belum ditindaklanjuti")]
    prioritas.sort(key=lambda r: (r["hasil_kpsp"] != "Penyimpangan", r["tgl_periksa"]))
    menunggu = q("SELECT COUNT(*) c FROM pengguna WHERE aktif=0 AND peran='guru'", satu=True)["c"]
    jml = {
        "paud": q("SELECT COUNT(*) c FROM paud", satu=True)["c"],
        "anak": q("SELECT COUNT(*) c FROM anak", satu=True)["c"],
        "guru": q("SELECT COUNT(*) c FROM pengguna WHERE peran='guru' AND aktif=1", satu=True)["c"],
    }
    return render_template("dashboard.html", total=total, kpsp=kpsp, gz=gz, tbu=tbu, tl=tl,
                           per_kel=sorted(per_kel.items()), per_paud=sorted(per_paud.items()),
                           prioritas=prioritas[:15], jml_prioritas=len(prioritas), menunggu=menunggu, jml=jml,
                           **_opsi_filter())


def _opsi_filter():
    return {"opsi_kel": q("SELECT * FROM kelurahan ORDER BY nama"),
            "opsi_paud": q("SELECT pa.*, k.nama AS kel FROM paud pa JOIN kelurahan k ON k.id=pa.kelurahan_id "
                           "ORDER BY pa.nama"),
            "args": request.args}


@app.route("/data")
@perlu_login("puskesmas")
def data():
    w, p = _filter()
    rows = q(f"SELECT s.*, a.nama AS anak, a.jk, a.tgl_lahir, pa.nama AS paud, k.nama AS kelurahan "
             f"{BASE_SQL} WHERE {w} ORDER BY s.tgl_periksa DESC, s.id DESC", p)
    if request.args.get("format") == "csv":
        buf = io.StringIO()
        kol = ["tgl_periksa", "kelurahan", "paud", "anak", "jk", "tgl_lahir", "umur_teks", "umur_bulan",
               "kpsp_umur", "jawaban", "skor", "hasil_kpsp", "bb", "tb", "cara_ukur", "lk", "lila", "imt",
               "z_bbu", "st_bbu", "z_tbu", "st_tbu", "z_bbtb", "st_bbtb", "z_imtu", "st_imtu", "z_lku", "st_lku",
               "st_lila", "status_gizi", "catatan_guru", "tindak_lanjut", "catatan_puskesmas"]
        wr = csv.writer(buf, delimiter=";")
        wr.writerow(kol)
        for r in rows:
            wr.writerow([r[k] if r[k] is not None else "" for k in kol])
        return Response("﻿" + buf.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": f"attachment; filename=skrining_kpsp_{date.today()}.csv"})
    return render_template("data.html", rows=rows, **_opsi_filter())


@app.route("/pengguna", methods=["GET", "POST"])
@perlu_login("puskesmas")
def pengguna():
    if request.method == "POST":
        f = request.form
        aksi = f.get("aksi")
        if aksi in ("aktifkan", "nonaktifkan"):
            if int(f["id"]) == g.user["id"]:
                flash("Tidak bisa menonaktifkan akun sendiri.", "err")
            else:
                db().execute("UPDATE pengguna SET aktif=? WHERE id=?", (1 if aksi == "aktifkan" else 0, f["id"]))
        elif aksi == "reset":
            pw = secrets.token_urlsafe(6)
            db().execute("UPDATE pengguna SET password_hash=? WHERE id=?", (generate_password_hash(pw), f["id"]))
            flash(f"Password baru untuk pengguna tersebut: {pw} (sampaikan langsung ke pengguna).", "ok")
        elif aksi == "tambah_petugas":
            un = f["username"].strip().lower()
            if q("SELECT 1 FROM pengguna WHERE username=?", (un,), satu=True) or len(f["password"]) < 6:
                flash("Username sudah dipakai atau password kurang dari 6 karakter.", "err")
            else:
                db().execute("INSERT INTO pengguna (username,password_hash,nama,peran,aktif) "
                             "VALUES (?,?,?, 'puskesmas', 1)", (un, generate_password_hash(f["password"]), f["nama"]))
                flash("Akun petugas ditambahkan.", "ok")
        db().commit()
        return redirect(url_for("pengguna"))
    rows = q("SELECT p.*, pa.nama AS paud, k.nama AS kel FROM pengguna p LEFT JOIN paud pa ON pa.id=p.paud_id "
             "LEFT JOIN kelurahan k ON k.id=pa.kelurahan_id ORDER BY p.aktif, p.peran DESC, p.nama")
    return render_template("pengguna.html", rows=rows)


@app.route("/wilayah", methods=["GET", "POST"])
@perlu_login("puskesmas")
def wilayah():
    if request.method == "POST":
        f = request.form
        try:
            if f.get("aksi") == "tambah_kel":
                for nama in f["nama"].splitlines():
                    if nama.strip():
                        db().execute("INSERT INTO kelurahan (nama) VALUES (?) ON CONFLICT DO NOTHING", (" ".join(nama.split()),))
            elif f.get("aksi") == "ubah_kel":
                db().execute("UPDATE kelurahan SET nama=? WHERE id=?", (" ".join(f["nama"].split()), f["id"]))
            elif f.get("aksi") == "hapus_kel":
                db().execute("DELETE FROM kelurahan WHERE id=?", (f["id"],))
            elif f.get("aksi") == "tambah_paud":
                db().execute("INSERT INTO paud (nama, kelurahan_id) VALUES (?,?)",
                             (" ".join(f["nama"].split()), f["kelurahan_id"]))
            elif f.get("aksi") == "ubah_paud":
                db().execute("UPDATE paud SET nama=?, kelurahan_id=? WHERE id=?",
                             (" ".join(f["nama"].split()), f["kelurahan_id"], f["id"]))
            elif f.get("aksi") == "hapus_paud":
                db().execute("DELETE FROM paud WHERE id=?", (f["id"],))
            db().commit()
        except IntegrityError:
            db().con.rollback()
            flash("Tidak bisa: nama sudah ada atau data masih dipakai (ada PAUD/anak/guru terkait).", "err")
        return redirect(url_for("wilayah"))
    kel = q("SELECT k.*, (SELECT COUNT(*) FROM paud WHERE kelurahan_id=k.id) n FROM kelurahan k ORDER BY nama")
    paud = q("SELECT pa.*, k.nama AS kel, (SELECT COUNT(*) FROM anak WHERE paud_id=pa.id) n_anak, "
             "(SELECT COUNT(*) FROM pengguna WHERE paud_id=pa.id) n_guru FROM paud pa "
             "JOIN kelurahan k ON k.id=pa.kelurahan_id ORDER BY k.nama, pa.nama")
    return render_template("wilayah.html", kel=kel, paud=paud)


@app.errorhandler(403)
def e403(e):
    return render_template("pesan.html", judul="Akses ditolak", pesan="Anda tidak punya akses ke halaman ini."), 403


@app.errorhandler(404)
def e404(e):
    return render_template("pesan.html", judul="Tidak ditemukan", pesan="Halaman atau data tidak ditemukan."), 404


init_db()

if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 5000)),
            debug=os.environ.get("DEBUG") == "1")
