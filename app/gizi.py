"""Perhitungan umur, pemilihan KPSP, dan status gizi.

Status gizi mengikuti Permenkes No. 2 Tahun 2020 tentang Standar Antropometri Anak
(tabel LMS WHO Child Growth Standards 0-60 bulan dan WHO Reference 2007 untuk >60 bulan).
LiLA dan lingkar kepala mengikuti Buku Bagan SDIDTK (revisi 2022).
"""
import json
import math
import os
from datetime import date

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

with open(os.path.join(_DIR, "kpsp.json"), encoding="utf-8") as f:
    KPSP = {int(k): v for k, v in json.load(f).items()}
KPSP_UMUR = sorted(KPSP)

with open(os.path.join(_DIR, "who_lms.json"), encoding="utf-8") as f:
    _RAW = json.load(f)


def _siapkan(raw):
    t = {}
    for jk, d in raw.items():
        lh = d["lhfa"]
        # baris bulan 24 muncul dua kali: pertama panjang badan, kedua tinggi badan
        idx = [i for i, r in enumerate(lh) if r[0] == 24][1]
        t[jk] = {
            "bbu": d["wfa"],
            "pbu": lh[:idx],
            "tbu": lh[idx:],
            "imtu_pb": d["bmifa_pb"],
            "imtu_tb": d["bmifa_tb"] + d["bmifa_07"],
            "lku": d["hcfa"],
            "bbpb": d["wfl"],
            "bbtb": d["wfh"],
        }
    return t


LMS = _siapkan(_RAW)


# ---------------------------------------------------------------- umur
def hitung_umur(tgl_lahir: date, tgl_periksa: date):
    """Cara hitung umur SDIDTK: kurangkan hari/bulan/tahun, pinjam 1 bulan = 30 hari."""
    th = tgl_periksa.year - tgl_lahir.year
    bl = tgl_periksa.month - tgl_lahir.month
    hr = tgl_periksa.day - tgl_lahir.day
    if hr < 0:
        hr += 30
        bl -= 1
    if bl < 0:
        bl += 12
        th -= 1
    total_bln = th * 12 + bl
    bulat = total_bln + (1 if hr > 16 else 0)  # lebih 16 hari dibulatkan 1 bulan
    hari = (tgl_periksa - tgl_lahir).days
    return {
        "tahun": th, "bulan": bl, "hari": hr,
        "teks": f"{th} th {bl} bln {hr} hr",
        "bulan_total": total_bln,
        "bulan_bulat": bulat,
        "hari_total": hari,
        "bulan_desimal": hari / 30.4375,
    }


def pilih_kpsp(umur_bulan_bulat: int):
    """KPSP sesuai umur; bila tidak pas gunakan kelompok umur yang lebih muda."""
    pilihan = [u for u in KPSP_UMUR if u <= umur_bulan_bulat]
    return pilihan[-1] if pilihan else None


def interpretasi_kpsp(skor: int):
    if skor >= 9:
        return "Sesuai umur"
    if skor >= 7:
        return "Meragukan"
    return "Penyimpangan"


TINDAKAN_KPSP = {
    "Sesuai umur": "Lanjutkan stimulasi sesuai umur dan jadwalkan skrining berikutnya.",
    "Meragukan": "Edukasi orang tua untuk intervensi stimulasi perkembangan, evaluasi ulang KPSP 2 minggu lagi.",
    "Penyimpangan": "Rujuk ke Puskesmas / RS rujukan tumbuh kembang.",
}


# ---------------------------------------------------------------- z-score
def _interp(tabel, x):
    if x < tabel[0][0] or x > tabel[-1][0]:
        return None
    for a, b in zip(tabel, tabel[1:]):
        if a[0] <= x <= b[0]:
            if b[0] == a[0]:
                return a[1:]
            f = (x - a[0]) / (b[0] - a[0])
            return [a[i] + f * (b[i] - a[i]) for i in (1, 2, 3)]
    return tabel[-1][1:]


def _z(lms, y, terbatas):
    L, M, S = lms
    z = ((y / M) ** L - 1) / (L * S) if L != 0 else math.log(y / M) / S
    if terbatas and abs(z) > 3:  # metode WHO untuk indeks berbasis berat
        sd = lambda k: M * (1 + L * S * k) ** (1 / L)
        if z > 3:
            z = 3 + (y - sd(3)) / (sd(3) - sd(2))
        else:
            z = -3 + (y - sd(-3)) / (sd(-2) - sd(-3))
    return round(z, 2)


def kls_bbu(z):
    if z < -3: return "Berat badan sangat kurang"
    if z < -2: return "Berat badan kurang"
    if z <= 1: return "Berat badan normal"
    return "Risiko berat badan lebih"


def kls_tbu(z):
    if z < -3: return "Sangat pendek"
    if z < -2: return "Pendek"
    if z <= 3: return "Normal"
    return "Tinggi"


def kls_bbtb(z):
    if z < -3: return "Gizi buruk"
    if z < -2: return "Gizi kurang"
    if z <= 1: return "Gizi baik"
    if z <= 2: return "Berisiko gizi lebih"
    if z <= 3: return "Gizi lebih"
    return "Obesitas"


def kls_imtu_5_18(z):
    if z < -3: return "Gizi buruk"
    if z < -2: return "Gizi kurang"
    if z <= 1: return "Gizi baik"
    if z <= 2: return "Gizi lebih"
    return "Obesitas"


def kls_lku(z):
    if z < -2: return "Mikrosefali"
    if z <= 2: return "Normal"
    return "Makrosefali"


def kls_lila(cm):
    if cm < 11.5: return "Gizi buruk"
    if cm < 12.5: return "Gizi kurang"
    return "Normal"


def _f(v):
    try:
        v = float(str(v).replace(",", "."))
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def status_gizi(jk, umur_bln_desimal, bb=None, tb=None, cara_ukur=None, lk=None, lila=None):
    """Kembalikan dict z-score & klasifikasi. jk: 'L' / 'P'. cara_ukur: 'terlentang' / 'berdiri'."""
    t = LMS[jk]
    u = umur_bln_desimal
    bb, tb, lk, lila = _f(bb), _f(tb), _f(lk), _f(lila)
    h = {"catatan": []}

    # koreksi cara ukur (Permenkes 2/2020)
    if tb:
        if u < 24 and cara_ukur == "berdiri":
            tb += 0.7
            h["catatan"].append("PB = TB + 0,7 cm (anak <24 bln diukur berdiri)")
        elif u >= 24 and cara_ukur == "terlentang":
            tb -= 0.7
            h["catatan"].append("TB = PB - 0,7 cm (anak ≥24 bln diukur terlentang)")
        h["tb_koreksi"] = round(tb, 1)

    def isi(kode, nilai, tabel, x, kls, terbatas):
        if nilai is None:
            return
        lms = _interp(tabel, x)
        if lms is None:
            h[kode] = {"z": None, "status": "Di luar rentang tabel"}
            return
        z = _z(lms, nilai, terbatas)
        h[kode] = {"z": z, "status": kls(z)}

    if u <= 60:
        isi("bbu", bb, t["bbu"], u, kls_bbu, True)
    elif bb:
        h["bbu"] = {"z": None, "status": "Tidak dinilai (>60 bln, gunakan IMT/U)"}

    if tb:
        isi("tbu", tb, t["pbu"] if u < 24 else t["tbu"], u, kls_tbu, False)

    if bb and tb:
        if u <= 60:
            isi("bbtb", bb, t["bbpb"] if u < 24 else t["bbtb"], tb, kls_bbtb, True)
        imt = bb / ((tb / 100) ** 2)
        h["imt"] = round(imt, 1)
        isi("imtu", imt, t["imtu_pb"] if u < 24 else t["imtu_tb"], u,
            kls_bbtb if u <= 60 else kls_imtu_5_18, True)

    if lk:
        if u <= 60:
            isi("lku", lk, t["lku"], u, kls_lku, False)
        else:
            h["lku"] = {"z": None, "status": "Tidak dinilai (tabel s.d. 60 bln)"}

    if lila:
        if 6 <= u < 60:
            h["lila"] = {"z": None, "status": kls_lila(lila)}
        else:
            h["lila"] = {"z": None, "status": "Tidak dinilai (hanya 6-59 bln)"}

    # kesimpulan status gizi utama: BB/TB (0-60 bln) atau IMT/U (>60 bln)
    utama = h.get("bbtb") if u <= 60 else h.get("imtu")
    h["status_gizi"] = utama["status"] if utama and utama.get("z") is not None else None
    h["indeks_utama"] = "BB/PB atau BB/TB" if u <= 60 else "IMT/U"
    return h


def ada_masalah_gizi(h):
    """True bila ada salah satu indeks di luar kategori normal."""
    normal = {"Berat badan normal", "Normal", "Gizi baik"}
    for k in ("bbu", "tbu", "bbtb", "imtu", "lku", "lila"):
        s = h.get(k)
        if s and s.get("z") is not None and s["status"] not in normal:
            return True
        if k == "lila" and s and s["status"] in ("Gizi buruk", "Gizi kurang"):
            return True
    return False
