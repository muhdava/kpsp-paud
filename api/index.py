"""Entry point Vercel (Python serverless) -> aplikasi Flask di folder app/."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from app import app  # noqa: E402,F401
