"""Bangun ulang app/data/who_lms.json (tabel LMS WHO untuk z-score status gizi).

Sumber (sesuai Permenkes No. 2 Tahun 2020 tentang Standar Antropometri Anak):
- 0-60 bulan : WHO Child Growth Standards 2006 (LMS bulanan / per 0,5 cm), diambil dari
               tabel JSON paket pygrowup (github.com/ewheeler/pygrowup), yang bersumber dari WHO.
- 61+ bulan  : WHO Reference 2007 (5-19 tahun) untuk TB/U dan IMT/U, dari file xlsx resmi WHO.

Keluaran: {"L": {...}, "P": {...}} dengan kunci per indeks berisi baris [x, L, M, S]
(x = umur dalam bulan, atau panjang/tinggi badan dalam cm untuk wfl/wfh).

    pip install openpyxl
    python tools/buat_who_lms.py
"""
import io
import json
import os
import urllib.request

import openpyxl

TUJUAN = os.path.join(os.path.dirname(__file__), "..", "app", "data", "who_lms.json")
PYGROWUP = "https://raw.githubusercontent.com/ewheeler/pygrowup/master/pygrowup/tables/{}_zscores.json"
WHO2007 = "https://cdn.who.int/media/docs/default-source/child-growth/growth-reference-5-19-years/{}"
WHO_FILE = {
    ("bmi", "boys"): "bmi-for-age-%285-19-years%29/bmi-boys-z-who-2007-exp.xlsx",
    ("bmi", "girls"): "bmi-for-age-%285-19-years%29/bmi-girls-z-who-2007-exp.xlsx",
    ("hfa", "boys"): "height-for-age-%285-19-years%29/hfa-boys-z-who-2007-exp.xlsx",
    ("hfa", "girls"): "height-for-age-%285-19-years%29/hfa-girls-z-who-2007-exp.xlsx",
}


def unduh(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


def js(nama, kunci):
    data = json.loads(unduh(PYGROWUP.format(nama)))
    return [[float(r[kunci]), float(r["L"]), float(r["M"]), float(r["S"])] for r in data]


def xl(indeks, sx):
    ws = openpyxl.load_workbook(io.BytesIO(unduh(WHO2007.format(WHO_FILE[(indeks, sx)]))), read_only=True).active
    return [[float(r[0]), float(r[1]), float(r[2]), float(r[3])]
            for i, r in enumerate(ws.iter_rows(values_only=True)) if i > 0 and r[0] is not None and r[0] <= 120]


def main():
    out = {}
    for jk, sx in (("L", "boys"), ("P", "girls")):
        out[jk] = {
            "wfa": js(f"wfa_{sx}_0_5", "Month"),
            # lhfa 0-5: baris bulan 24 muncul dua kali (panjang badan lalu tinggi badan); app memisahkannya
            "lhfa": js(f"lhfa_{sx}_0_5", "Month") + xl("hfa", sx),
            "bmifa_pb": js(f"bmifa_{sx}_0_2", "Month"),
            "bmifa_tb": js(f"bmifa_{sx}_2_5", "Month"),
            "bmifa_07": xl("bmi", sx),
            "hcfa": js(f"hcfa_{sx}_0_5", "Month"),
            "wfl": js(f"wfl_{sx}_0_2", "Length"),
            "wfh": js(f"wfh_{sx}_2_5", "Height"),
        }
        print(jk, {k: len(v) for k, v in out[jk].items()})
    with open(TUJUAN, "w") as f:
        json.dump(out, f)
    print("Tersimpan:", os.path.abspath(TUJUAN))


if __name__ == "__main__":
    main()
