# IDB Bali — Sistem Peminjaman Ruangan Kampus IDB Bali

Implementasi web untuk PRD **Sistem Informasi Peminjaman Ruangan Kampus IDB Bali — Release 1.0**. Aplikasi mencakup pencarian slot, kalender ketersediaan, reservasi eksklusif tanpa double booking, approval Sarpras, pembatalan mandiri, bukti QR, surat peminjaman PDF, audit log, pengelolaan pengguna, dan laporan peminjaman. Tampilan memakai warna resmi IDB Bali (teal &amp; oranye), logo resmi kampus, dan foto fasilitas dari situs IDB Bali.

## Menjalankan aplikasi

```bash
# 1. (Opsional) buat virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Pasang dependensi
pip install -r requirements.txt

# 3. Jalankan
python3 app.py
# atau tentukan port lain: PORT=9000 python3 app.py
```

Buka **http://127.0.0.1:8080**. Server berjalan di `0.0.0.0`, jadi perangkat lain pada jaringan yang sama dapat membuka **http://<IP-komputer>:8080**.

Cari IP lokal komputer:

```bash
ipconfig getifaddr en0 || ipconfig getifaddr en1
```

Aktifkan debug hanya untuk lokal: `FLASK_DEBUG=1 python3 app.py`.

Database SQLite dan 28 ruangan contoh dibuat otomatis saat aplikasi pertama kali dijalankan (`instance/idb_rooms.db`). Untuk mereset data demo, hentikan server lalu hapus folder `instance/` dan isi `uploads/` (kecuali `.gitkeep`).

### Akun demo

Login memakai **NIM mahasiswa** atau **NIK/NIP dosen/staf**, bukan email. Kata sandi akun demo terdiri dari 4 karakter: `idb1`.

| Peran | NIM / NIK / NIP | Kata sandi |
| --- | --- | --- |
| Mahasiswa | `22101001` | `idb1` |
| Dosen / Staf | `5101018701250001` | `idb1` |
| Petugas Sarpras | `SAR-001` | `idb1` |
| Super Admin | `ADM-000` | `idb1` |

Email lama dan password lama (`demo123`) tetap diterima untuk kompatibilitas data demo yang sudah ada; akun seed otomatis dimigrasikan ke kata sandi 4 karakter saat aplikasi dijalankan.

## Fitur Release 1.0

- **Pencarian slot** berdasarkan tanggal, rentang jam, gedung, kapasitas, kategori, dan kata kunci, lengkap dengan foto setiap ruang.
- **Kalender ketersediaan** publik per bulan, filter per ruang, tanpa menampilkan data pribadi pemesan.
- **Reservasi eksklusif** dengan transaksi `BEGIN IMMEDIATE` + write lock; dua permintaan pada slot yang sama menghasilkan tepat satu `confirmed` dan satu `failed`.
- **Alur status** `processing → confirmed / failed` dan `cancelled`, dengan validasi `mulai < selesai` (BR-01).
- **Aturan ruang**: ruang lab/studio tertentu mewajibkan dokumen; Aula memerlukan approval Sarpras; UKS dan Ruang Dosen dikecualikan dari peminjaman rutin.
- **Pembatalan mandiri** hanya oleh pemilik dan sebelum waktu mulai (BR-03), dengan alasan wajib.
- **Dashboard Sarpras**: antrean verifikasi, approval/penolakan, pembatalan dengan alasan, filter reservasi, dan utilization ruang.
- **Kelola pengguna**: pencarian akun, rekap reservasi per pengguna, dan perubahan peran oleh Super Admin dengan audit log.
- **Laporan peminjaman**: rekap status, utilisasi per ruang/gedung, tren bulanan, pemohon teraktif, dan ekspor CSV.
- **Audit log** mencatat aktor, waktu, aksi, dan alasan untuk setiap perubahan status (BR-04).
- **Bukti peminjaman QR** + halaman verifikasi publik yang membatasi data pribadi.
- **Surat peminjaman PDF** otomatis setelah reservasi berstatus `confirmed`: kop IDB Bali, nomor surat, nama, NIM/NIK, program studi, ruang, tanggal, jam, keperluan, informasi persetujuan, dan QR verifikasi. Tidak ada logo atau tanda tangan yang dikarang.
- **Pengelolaan aturan ruang** oleh Sarpras/Super Admin.
- UI responsif untuk ponsel dan desktop, tanpa framework frontend.

## Test

```bash
python3 -m unittest discover -s tests -v
```

Test suite mencakup BR-01, BR-02 (termasuk request konkuren), BR-03, BR-04, approval Aula, QR, verifikasi publik, dan skenario AC-02A/AC-02B/AC-02D/AC-05A.

## Struktur proyek

```
app.py                 # routes, validasi, transaksi reservasi, QR, audit
schema.sql             # skema SQLite
templates/             # Jinja: publik, auth, user, admin, bukti, verifikasi
static/css/style.css   # desain responsif
static/js/app.js       # navigasi, toast, upload label, print, time helper
tests/test_app.py      # test suite (23 test)
static/img/logo-idb.png     # logo resmi IDB Bali (sumber: idbbali.ac.id)
static/img/logo-mark.png    # mark logo resmi untuk header
static/img/rooms/           # foto fasilitas kampus (sumber: idbbali.ac.id/fasilitas-kampus)
docs/PRD.md            # ringkasan requirement & traceability
docs/DATA.md           # model data, business rules, guardrail transaksi
docs/ACCEPTANCE.md     # matriks acceptance + test
docs/SKILLS.md         # panduan & verifikasi skill OpenCode
AGENTS.md              # instruksi untuk AI code agent berikutnya
```

## Catatan implementasi

- Database: SQLite dengan WAL, `busy_timeout`, `BEGIN IMMEDIATE`, dan `threading.Lock` proses-level. Untuk deployment multi-proses, gunakan PostgreSQL/MySQL dan row-level locking (`SELECT ... FOR UPDATE`) atau constraint eksklusi.
- Autentikasi: session cookie Flask yang ditandatangani, password PBKDF2-SHA256 (kompatibel dengan Python 3.9 tanpa OpenSSL scrypt). Login utama memakai NIM/NIK; email hanya fallback untuk akun lama.
- Surat PDF dibuat dengan ReportLab (`reportlab>=4.0,<4.3` untuk kompatibilitas Python 3.9). Berkas dihasilkan saat diunduh, bukan disimpan sebagai dokumen statis.
- Foto ruang dipetakan per kode/kategori dari aset publik `idbbali.ac.id/fasilitas-kampus`. Foto bersifat ilustratif fasilitas kampus; verifikasi kondisi ruang tetap dilakukan Sarpras.
- Dokumen pendukung disimpan di `uploads/` dan hanya dapat diunduh pemilik reservasi atau Sarpras.
- Aplikasi ini adalah demo fungsional Release 1.0; belum mencakup pembayaran, AI recommendation, peta 3D, atau integrasi IoT sesuai out-of-scope PRD.
