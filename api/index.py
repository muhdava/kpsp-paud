"""Entry point Vercel (Python serverless) -> aplikasi Flask di folder app/."""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

try:
    from app import app  # noqa: E402,F401
except Exception as e:  # tampilkan penyebab gagal start, bukan crash tanpa pesan
    _pesan = f"{type(e).__name__}: {e}"
    traceback.print_exc()

    def app(environ, start_response):
        body = ("<h1>Aplikasi gagal dijalankan</h1><pre>" + _pesan.replace("<", "&lt;") + "</pre>").encode()
        start_response("500 Internal Server Error", [("Content-Type", "text/html; charset=utf-8")])
        return [body]
