# StrukLokal

MVP lokal untuk mengubah foto/PDF struk menjadi kandidat nama toko, tanggal, dan total. Pengguna memeriksa dan menyetujui setiap transaksi sebelum ekspor CSV. Aplikasi tidak mengirim berkas atau data transaksi ke server luar.

## Menjalankan di Windows

Gunakan Python 3.10–3.12 untuk ketersediaan wheel PaddlePaddle yang lebih luas. Python 3.14 yang ada di mesin pengembangan saat ini tidak dipakai sebagai environment aplikasi.

1. Pasang Python 3.11 64-bit.
2. Buka PowerShell di folder ini, lalu siapkan environment:

   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

3. Saat masih online, unduh model PaddleOCR ke folder `.paddlex_cache` di proyek:

   ```powershell
   python prepare_models.py
   ```

4. Jalankan aplikasi:

   ```powershell
   python app.py
   ```

5. Buka <http://127.0.0.1:5000> di browser. Setelah langkah 3, matikan jaringan dan unggah satu berkas untuk memastikan konfigurasi lokal dapat berjalan offline.

Jalankan unit test parser (tidak perlu model OCR):

```powershell
python -m unittest discover -s tests -v
```

Model PaddleOCR berukuran besar dan diunduh saat `prepare_models.py` dijalankan. Cache disimpan di `.paddlex_cache` dalam folder proyek; pertahankan folder tersebut untuk penggunaan offline. Dependensi dan model harus tersedia sebelum penggunaan offline.
Konfigurasi menetapkan `lang="id"` dan `ocr_version="PP-OCRv6"`; Bahasa Indonesia didukung model PP-OCRv6.

## Perilaku MVP

- Format masukan JPG/JPEG, PNG, dan PDF hasil pemindaian; maksimal 10 MB dan 5 halaman PDF.
- Orientasi gambar EXIF diterapkan. Gambar beresolusi ekstrem ditolak; gambar/PDF diperkecil untuk OCR.
- Kandidat tanggal dan total dihasilkan dengan aturan heuristik; semua hasil wajib diperiksa manusia.
- CSV UTF-8 dengan BOM hanya berisi transaksi yang disetujui. Nilai berawalan karakter formula spreadsheet diawali apostrof.
- Data dan teks OCR hanya disimpan dalam memori proses; berhentikan server untuk menghapus seluruh data sesi. Tidak ada basis data dan berkas unggahan tidak ditulis ke disk.
- Server hanya mengikat ke `127.0.0.1`. Jangan ubah host menjadi alamat publik untuk deployment.

## Batasan yang diketahui

Parser heuristik memiliki unit test untuk tanggal/nominal satu baris, label TOTAL terpisah, subtotal/pajak, dan kandidat total seri; ini belum menggantikan evaluasi pada 20 sampel berlabel. Ambiguitas sebagian dideteksi melalui kandidat tanggal dan total; pengguna tetap harus membandingkan hasil dengan struk asli. OCR dapat gagal pada struk pudar atau foto buruk.

## Lisensi

Kode StrukLokal dilisensikan di bawah MIT (lihat `LICENSE`). Lisensi dependensi dan model OCR dicatat terpisah di `THIRD_PARTY_NOTICES.md`; inventaris penuh komponen transitif dan bobot model tetap harus diperiksa sebelum distribusi.
