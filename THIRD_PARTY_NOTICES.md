# Catatan lisensi pihak ketiga

Lisensi kode StrukLokal sendiri adalah MIT (lihat [`LICENSE`](LICENSE)). Daftar di bawah mencakup dependensi langsung yang dinyatakan di `requirements.txt`; dependensi transitif dan artefak model/biner harus ikut dicatat dari environment final sebelum distribusi.

| Komponen | Peran | Lisensi/sumber pemeriksaan |
|---|---|---|
| PaddleOCR | OCR lokal | Apache-2.0 — [repositori PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) |
| PaddlePaddle | Runtime inferensi CPU | Apache-2.0 — [repositori PaddlePaddle](https://github.com/PaddlePaddle/Paddle) |
| Flask | Antarmuka web lokal | BSD-3-Clause — [lisensi Flask](https://flask.palletsprojects.com/en/stable/license/) |
| Pillow | Membaca dan mengubah gambar | MIT-CMU — [metadata PyPI Pillow](https://pypi.org/project/pillow/) |
| NumPy | Representasi gambar untuk OCR | BSD-3-Clause — [metadata PyPI NumPy](https://pypi.org/project/numpy/) |
| pypdfium2 | Merender halaman PDF | Apache-2.0 OR BSD-3-Clause untuk binding; PDFium dan beberapa dependensi binernya memiliki pemberitahuan lisensi tambahan — [dokumentasi lisensi pypdfium2](https://pypdfium2.readthedocs.io/en/stable/readme.html) |

## Model OCR

`prepare_models.py` meminta PaddleOCR menginisialisasi model default runtime. Versi dan ID bobot dipilih oleh versi PaddleOCR yang terpasang dan belum dikunci atau dicatat dalam repositori ini. Sebelum mendistribusikan aplikasi beserta cache model, catat ID/version setiap bobot yang benar-benar diunduh, sumbernya, dan lisensi yang berlaku pada halaman model/artifact tersebut. Jangan menganggap lisensi kode PaddleOCR otomatis mencakup semua bobot yang diunduh.

## Sebelum rilis

- Simpan lisensi dan copyright notices untuk seluruh dependensi transitif dan komponen yang dibundel di wheel/platform target.
- Tinjau build pypdfium2/PDFium yang dipakai; daftar dependensi biner dapat berbeda menurut platform.
- Tinjau lisensi model OCR yang tepat dari cache hasil `prepare_models.py`.
- Perbarui dokumen ini dan sertakan notices yang diwajibkan saat membuat paket distribusi.
