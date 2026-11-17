"""Uji satuan perhitungan umur, pemilihan KPSP, dan status gizi (app/gizi.py).

    python -m pytest tests -q        # atau: python tests/test_gizi.py
"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import gizi  # noqa: E402


def test_hitung_umur_contoh_buku_sdidtk():
    # Contoh di Buku Bagan SDIDTK hal. 15: periksa 15-4-2020, lahir 25-9-2018 -> 1 th 6 bln 20 hr
    u = gizi.hitung_umur(date(2018, 9, 25), date(2020, 4, 15))
    assert (u["tahun"], u["bulan"], u["hari"]) == (1, 6, 20)
    assert u["bulan_total"] == 18
    assert u["bulan_bulat"] == 19  # sisa hari > 16 dibulatkan 1 bulan


def test_pembulatan_16_hari_tidak_dibulatkan():
    u = gizi.hitung_umur(date(2022, 1, 1), date(2022, 7, 17))  # 6 bln 16 hr
    assert u["bulan_bulat"] == 6


def test_pilih_kpsp_kelompok_lebih_muda():
    assert gizi.pilih_kpsp(5) is None
    assert gizi.pilih_kpsp(6) == 6
    assert gizi.pilih_kpsp(40) == 36   # tidak pas -> kelompok umur lebih muda
    assert gizi.pilih_kpsp(72) == 72
    assert gizi.pilih_kpsp(80) == 72


def test_semua_kpsp_berisi_10_soal():
    assert sorted(gizi.KPSP) == [6, 9, 12, 15, 18, 21, 24, 30, 36, 42, 48, 54, 60, 66, 72]
    for umur, k in gizi.KPSP.items():
        assert len(k["soal"]) == 10, umur
        assert k["hal"], umur


def test_interpretasi_kpsp():
    assert gizi.interpretasi_kpsp(10) == "Sesuai umur"
    assert gizi.interpretasi_kpsp(9) == "Sesuai umur"
    assert gizi.interpretasi_kpsp(8) == "Meragukan"
    assert gizi.interpretasi_kpsp(7) == "Meragukan"
    assert gizi.interpretasi_kpsp(6) == "Penyimpangan"
    assert gizi.interpretasi_kpsp(0) == "Penyimpangan"


def test_zscore_median_who_mendekati_nol():
    # Anak laki-laki 36 bln dengan nilai median WHO -> z-score ~ 0
    h = gizi.status_gizi("L", 36, bb=14.3, tb=96.1, cara_ukur="berdiri", lk=49.5)
    for k in ("bbu", "tbu", "bbtb", "lku"):
        assert abs(h[k]["z"]) < 0.15, (k, h[k])
    assert h["status_gizi"] == "Gizi baik"


def test_gizi_buruk_dan_lila():
    h = gizi.status_gizi("L", 12, bb=6.0, tb=70, cara_ukur="terlentang", lk=44, lila=11)
    assert h["status_gizi"] == "Gizi buruk"
    assert h["lila"]["status"] == "Gizi buruk"
    assert gizi.ada_masalah_gizi(h)


def test_koreksi_cara_ukur():
    h = gizi.status_gizi("P", 30, bb=12, tb=90, cara_ukur="terlentang")
    assert h["tb_koreksi"] == 89.3  # >=24 bln diukur terlentang -> dikurangi 0,7 cm


def test_lebih_60_bulan_pakai_imtu():
    h = gizi.status_gizi("P", 66, bb=15, tb=105, cara_ukur="berdiri", lk=49)
    assert h["indeks_utama"] == "IMT/U"
    assert h["bbu"]["z"] is None and h["lku"]["z"] is None
    assert h["status_gizi"] in ("Gizi baik", "Gizi kurang", "Gizi buruk", "Gizi lebih", "Obesitas")


if __name__ == "__main__":
    for nama, fn in list(globals().items()):
        if nama.startswith("test_"):
            fn()
            print("ok", nama)
