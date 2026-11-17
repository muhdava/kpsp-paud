"""Buat ulang ikon PNG/ICO dari public/static/favicon.svg (ikon tab browser & layar utama HP).

Butuh Microsoft Edge atau Chrome terpasang (dipakai Playwright untuk merender SVG).

    pip install playwright pillow
    python tools/buat_ikon.py            # memakai Edge
    python tools/buat_ikon.py chrome     # memakai Chrome
"""
import os
import sys

from PIL import Image
from playwright.sync_api import sync_playwright

PUB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public")


def main():
    svg = open(os.path.join(PUB, "static", "favicon.svg"), encoding="utf-8").read()
    kanal = "chrome" if (len(sys.argv) > 1 and sys.argv[1] == "chrome") else "msedge"
    with sync_playwright() as p:
        br = p.chromium.launch(channel=kanal)
        for n in (512, 180, 32):
            pg = br.new_page(viewport={"width": n, "height": n})
            pg.set_content('<html><body style="margin:0;background:transparent">'
                           + svg.replace("<svg ", f'<svg width="{n}" height="{n}" ', 1) + "</body></html>")
            pg.screenshot(path=os.path.join(PUB, "static", f"ikon-{n}.png"), omit_background=True,
                          clip={"x": 0, "y": 0, "width": n, "height": n})
        br.close()
    Image.open(os.path.join(PUB, "static", "ikon-512.png")).save(
        os.path.join(PUB, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    print("ok")


if __name__ == "__main__":
    main()
