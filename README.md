# StrukLokal

StrukLokal adalah MVP pencatatan transaksi lokal. Aplikasi membaca foto atau PDF struk, menyajikan kandidat nama toko, tanggal, dan total untuk diperiksa, lalu mengekspor transaksi yang disetujui ke CSV.

Dokumen dan hasil OCR diproses di komputer pengguna. Aplikasi tidak memakai basis data dan tidak mengirim isi struk ke layanan luar. Persiapan model pertama kali memerlukan koneksi internet untuk mengunduh bobot OCR.

## Fitur dan batas penggunaan

- Masukan: JPG, JPEG, PNG, dan PDF hasil pemindaian.
- Batas berkas: 10 MB; PDF paling banyak 5 halaman.
- Gambar berorientasi EXIF diperbaiki dan gambar besar diperkecil sebelum OCR.
- OCR memakai PaddleOCR dengan konfigurasi bahasa Indonesia (`id`) dan PP-OCRv6.
- Parser heuristik membuat kandidat tanggal dan total. Pengguna harus memeriksa setiap nilai sebelum menyetujui transaksi.
- CSV menggunakan UTF-8 dengan BOM, hanya memuat transaksi terverifikasi, dan melindungi sel yang dapat ditafsirkan sebagai formula spreadsheet.
- Data transaksi berada di memori proses dan hilang ketika server berhenti. Aplikasi hanya mengikat ke `127.0.0.1`.

> Struk pudar, buram, atau memiliki tata letak yang tidak umum dapat menghasilkan pembacaan keliru. Hasil otomatis bukan pengganti pemeriksaan struk asli.

## Struktur proyek

```text
.
├── app.py             # Rute Flask, validasi transaksi, dan ekspor CSV
├── parser.py          # Ekstraksi heuristik tanggal, toko, dan nominal
├── receipt_ocr.py     # Dekode gambar/PDF dan integrasi PaddleOCR
├── prepare_models.py  # Unduh dan siapkan model untuk penggunaan offline
├── scripts/
│   └── check_repo_hygiene.py # Cegah cache, virtualenv, dan secret ikut Git
├── templates/
│   └── index.html     # Antarmuka Jinja
├── static/
│   ├── app.js         # Interaksi pemilihan berkas
│   └── style.css      # Gaya antarmuka
└── tests/
    └── test_parser.py # Unit test parser tanpa memuat model OCR
```

## Menjalankan di Windows

Gunakan Python 3.12 64-bit yang menyediakan dukungan wheel PaddlePaddle pada lingkungan pengembangan ini.

1. Buka PowerShell di folder proyek dan buat virtual environment:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

2. Saat terhubung ke internet, unduh dan siapkan model OCR:

   ```powershell
   python prepare_models.py
   ```

   Model disimpan di cache proyek (`.paddlex_cache` dan `.paddle_home`), yang tidak termasuk dalam Git. Pertahankan cache itu jika ingin menjalankan OCR tanpa jaringan.

3. Jalankan aplikasi:

   ```powershell
   python app.py
   ```

4. Buka <http://127.0.0.1:5000> di browser. Untuk memastikan penggunaan offline, siapkan model dahulu, matikan jaringan, lalu coba unggah dokumen.

## Pemeriksaan parser

Unit test parser tidak memerlukan model OCR. Pasang alat pengembangan dan jalankan seluruh pemeriksaan lokal:

```powershell
python -m pip install -r requirements-dev.txt
ruff check .
ruff format --check .
python -m compileall -q app.py parser.py receipt_ocr.py prepare_models.py tests scripts
python -W error -m unittest discover -s tests -v
python scripts/check_repo_hygiene.py
```

Workflow GitHub Actions menjalankan lint, pemeriksaan format, pemeriksaan kebersihan Git, kompilasi sintaks, dan unit test di Ubuntu serta Windows dengan Python 3.10, 3.11, dan 3.12. Matriks lintas versi/platform ini memeriksa parser dan sintaks; setup aplikasi OCR yang didukung tetap dijelaskan terpisah di atas.

Untuk menjadikan QA sebagai syarat merge ke `main`, aktifkan branch protection/ruleset di GitHub dan wajibkan job **Required QA gate** pada workflow **StrukLokal QA**. Workflow menyediakan gate gabungan, tetapi tidak dapat mengaktifkan aturan repositori dengan sendirinya.

Job CI tidak mengunduh bobot PaddleOCR atau mengklaim telah menguji pengenalan pada struk nyata. Unit test memeriksa aturan parser, bukan akurasi OCR atau seluruh alur unggah sampai ekspor.

## Lisensi dan status evaluasi

Kode StrukLokal dilisensikan dengan MIT (lihat [LICENSE](LICENSE)). Lihat [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) untuk ringkasan lisensi paket langsung yang digunakan di lingkungan pengembangan. Berkas itu bukan inventaris lengkap dependensi transitif atau bobot model; verifikasi lisensi masing-masing sebelum redistribusi.

Parser memiliki unit test, tetapi proyek belum dievaluasi pada 20 struk Indonesia berlabel dan belum memiliki hasil evaluasi akurasi OCR yang terdokumentasi. Catat jumlah sampel, kriteria pencocokan, dan kegagalan saat evaluasi sebelum membuat klaim akurasi.
