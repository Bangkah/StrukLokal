"""Download and warm the configured OCR model for later offline use."""

import numpy as np

from receipt_ocr import build_ocr_engine


def main() -> None:
    engine = build_ocr_engine()
    sample_image = np.full((64, 256, 3), 255, dtype=np.uint8)
    engine.predict(sample_image)
    print(
        "Model OCR siap di cache lokal. Uji kembali aplikasi saat jaringan dimatikan."
    )



if __name__ == "__main__":
    main()
