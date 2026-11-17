"""Render halaman KPSP dari Buku Bagan SDIDTK (PDF) menjadi gambar petunjuk di form skrining.

Halaman PDF yang berisi KPSP: 38, 44, 45, 50, 51, 56, 57, 62, 63, 70-73, 78-81, 86-89.
Hasil: public/static/kpsp/hal_<n>.png (dirujuk dari app/data/kpsp.json, kunci "hal").

Teks 10 pertanyaan per kelompok umur di app/data/kpsp.json disalin dari teks PDF yang sama
(diekstrak dengan PyMuPDF lalu dirapikan manual: pertanyaan yang merujuk gambar diberi
keterangan "lihat buku"). Bila buku direvisi, perbarui kpsp.json dan jalankan skrip ini lagi.

PDF tidak disimpan di repo (7,7 MB). Letakkan file PDF-nya lalu jalankan:

    pip install pymupdf
    python tools/ekstrak_gambar_kpsp.py "BUKU-BAGAN-SDIDTK-revisi-22082022.pdf"
"""
import os
import sys

import pymupdf

HALAMAN = [38, 44, 45, 50, 51, 56, 57, 62, 63, 70, 71, 72, 73, 78, 79, 80, 81, 86, 87, 88, 89]
TUJUAN = os.path.join(os.path.dirname(__file__), "..", "public", "static", "kpsp")


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    doc = pymupdf.open(sys.argv[1])
    os.makedirs(TUJUAN, exist_ok=True)
    for h in HALAMAN:
        doc[h - 1].get_pixmap(dpi=100).save(os.path.join(TUJUAN, f"hal_{h}.png"))
        print("ok hal", h)


if __name__ == "__main__":
    main()
