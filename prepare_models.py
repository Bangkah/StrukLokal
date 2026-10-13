"""Download/cache the OCR models during online setup so later runs can be offline."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
os.environ["USERPROFILE"] = str(BASE_DIR / ".paddle_home")
os.environ["HOME"] = str(BASE_DIR / ".paddle_home")
os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(BASE_DIR / ".paddlex_cache"))

import numpy as np
from paddleocr import PaddleOCR

engine = PaddleOCR(
    lang="id",
    ocr_version="PP-OCRv6",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    engine="paddle",
)
engine.predict(np.full((64, 256, 3), 255, dtype=np.uint8))
print("Model OCR siap di cache lokal. Uji kembali aplikasi saat jaringan dimatikan.")
