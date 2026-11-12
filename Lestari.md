# Lestari — Dokumentasi Proyek & Panduan Pengguna

> **Lestari** adalah aplikasi web konsultasi kesehatan berbasis AI dalam Bahasa Indonesia.
> Pengguna dapat menceritakan gejala, menanyakan obat, atau mengunggah foto resep/hasil lab,
> lalu menerima analisis triase yang terstruktur dan berbasis bukti dari **Lestari AI**.
> Lestari *bukan* pengganti diagnosis dokter.

---

## Daftar Isi

1. [Apa Itu Lestari](#1-apa-itu-lestari)
2. [Peran (Role) di Website](#2-peran-role-di-website)
3. [Ringkasan Fitur](#3-ringkasan-fitur)
4. [Peta Aplikasi (Halaman & URL)](#4-peta-aplikasi-halaman--url)
5. [Tutorial Pengguna Lengkap](#5-tutorial-pengguna-lengkap)
   - [5.1 Membuat Akun](#51-membuat-akun)
   - [5.2 Masuk (Login)](#52-masuk-login)
   - [5.3 Mengajukan Pertanyaan ke Lestari AI](#53-mengajukan-pertanyaan-ke-lestari-ai)
   - [5.4 Mengirim Pertanyaan Lanjutan](#54-mengirim-pertanyaan-lanjutan)
   - [5.5 Melampirkan Foto](#55-melampirkan-foto)
   - [5.6 Membaca dan Menindaklanjuti Peringatan Darurat](#56-membaca-dan-menindaklanjuti-peringatan-darurat)
   - [5.7 Membuka Kembali, Melanjutkan, dan Menghapus Sesi Lama](#57-membuka-kembali-melanjutkan-dan-menghapus-sesi-lama)
   - [5.8 Menyimpan Konsultasi sebagai Catatan Kesehatan](#58-menyimpan-konsultasi-sebagai-catatan-kesehatan)
   - [5.9 Membaca, Memperluas, Mengunduh, dan Menghapus Catatan Kesehatan](#59-membaca-memperluas-mengunduh-dan-menghapus-catatan-kesehatan)
   - [5.10 Mencari Rumah Sakit Terdekat](#510-mencari-rumah-sakit-terdekat)
   - [5.11 Memeriksa Cuaca (BMKG)](#511-memeriksa-cuaca-bmkg)
   - [5.12 Membaca Artikel Kesehatan](#512-membaca-artikel-kesehatan)
   - [5.13 Mengubah Foto Profil](#513-mengubah-foto-profil)
   - [5.14 Keluar (Logout)](#514-keluar-logout)
6. [Pemecahan Masalah & FAQ](#6-pemecahan-masalah--faq)
7. [Keterbatasan yang Diketahui](#7-keterbatasan-yang-diketahui)
8. [Untuk Pengembang](#8-untuk-pengembang)

---

## 1. Apa Itu Lestari

Lestari adalah **aplikasi web Django** dengan antarmuka bergaya Tailwind yang mengutamakan
tampilan ponsel. Intinya adalah konsultan kesehatan percakapan yang ditenagai Google
**Gemini 2.5 Flash**, ditambah empat utilitas pendukung sehingga bukan sekadar kotak obrolan:

| Kemampuan | Fungsinya |
|---|---|
| **Konsultasi AI** | Obrolan bebas tentang gejala, obat, gizi, hasil lab, kesehatan mental, dan sebagainya. Jawabannya berupa analisis triase terstruktur, bukan diagnosis pasti. |
| **Catatan Kesehatan** | Lestari AI dapat merangkum satu sesi konsultasi menjadi laporan kesehatan terstruktur yang bisa dibaca ulang atau diunduh sebagai PDF, misalnya untuk ditunjukkan ke dokter. |
| **Rumah Sakit Terdekat** | Mencari rumah sakit dalam radius ~30 km dari lokasi perangkat atau dari alamat yang diketik pengguna, lengkap dengan jarak, nomor telepon, tautan peta, dan petunjuk arah. |
| **Cuaca** | Prakiraan resmi BMKG (kondisi saat ini + prakiraan beberapa hari) untuk desa/kelurahan mana pun di Indonesia. |
| **Artikel Kesehatan** | Berita kesehatan terkini dari Google News, dapat dicari dan dikelompokkan per topik. |

**Yang bisa dan tidak bisa dilakukan Lestari AI**

- Lestari AI **hanya menjawab topik kesehatan/medis** — gejala, penyakit, penggunaan dan
  interaksi obat, interpretasi hasil lab pada tingkat triase, gizi, kebugaran, tidur, kesehatan
  mental, pertolongan pertama, pencegahan, dan pola hidup sehat.
- Pertanyaan yang jelas di luar kesehatan akan ditolak dengan kalimat baku:
  *"Mohon maaf, Lestari AI hanya dapat membantu pertanyaan seputar kesehatan…"*
- Lestari AI tidak pernah mengaku sebagai dokter dan tidak memberikan satu diagnosis pasti.
  Setiap jawaban substantif diakhiri dengan catatan penyangkalan dan, bila relevan, arahan ke
  `119` atau IGD terdekat.
- Jawaban memakai struktur tetap: **Ringkasan → Kemungkinan Penyebab → Red Flags →
  Yang Bisa Dilakukan Sekarang → Yang Harus Dihindari → Kapan Harus ke Dokter → Kesimpulan**
  (format lebih singkat dipakai untuk pertanyaan tunggal seperti interaksi obat).
- Ada dua *tool* internal AI: `create_health_note` (menyimpan konsultasi sebagai catatan
  kesehatan) dan `find_nearby_hospitals` (pencarian rumah sakit). Hasil rumah sakit disusun dari
  data nyata OpenStreetMap/Geoapify — AI tidak boleh mengarang nama, alamat, nomor telepon, atau
  jarak rumah sakit.

---

## 2. Peran (Role) di Website

**Hanya ada satu peran yang terlihat pengguna: pengguna terdaftar (Pengguna).**

| Peran | Cara mendapatkannya | Hak akses |
|---|---|---|
| **Pengguna** | Mendaftar di `/signup/` | Seluruh fitur aplikasi: konsultasi AI, catatan kesehatan, pencarian rumah sakit, cuaca, artikel, foto profil, serta pengelolaan sesi dan catatannya sendiri. Semua akun memiliki izin yang sama — tidak ada paket premium, moderator, atau dokter di dalam produk. |
| *(Internal saja)* **Superuser/staf Django** | Dibuat lewat terminal dengan `python manage.py createsuperuser`, lalu masuk ke `/admin/` | Administrasi teknis basis data melalui Django Admin (melihat pengguna, sesi, pesan, catatan, dan cache API). Ini **bukan** bagian dari antarmuka produk publik dan pengguna biasa tidak pernah melihatnya. |

Konsekuensi praktisnya:

- Semua halaman aplikasi (`/konsultasi/`, `/catatan/`, `/rumah-sakit/`, `/cuaca/`, `/artikel/`)
  memerlukan akun yang sudah masuk. Hanya landing page (`/`), halaman login, dan halaman daftar
  yang dapat diakses tanpa masuk.
- Tidak ada dasbor "dokter" atau "admin" di dalam aplikasi. Peran pengguna pada dasarnya hanya
  *sudah masuk* atau *belum masuk*.

---

## 3. Ringkasan Fitur

### 3.1 Landing page (`/`)

- Halaman pemasaran dengan hero carousel empat slide yang berganti otomatis setiap 5 detik
  (tersedia tombol panah dan titik navigasi), strip "Fitur platform kami", bagian pengenalan,
  grid enam kartu fitur, serta bagian "Cara Kerja" dengan empat ubin yang membuka modal detail.
- Tombol ajakan menyesuaikan status masuk: pengunjung melihat **Masuk / Daftar**, pengguna yang
  sudah masuk melihat **Buka Konsultasi**.

### 3.2 Autentikasi

- **Daftar** dengan nama lengkap, email, password, konfirmasi password, dan foto profil opsional.
  Password minimal 8 karakter; email harus mengandung `@` dan `.`; email ganda ditolak. Setelah
  berhasil, pengguna langsung masuk secara otomatis.
- **Masuk** dengan email + password (email berfungsi sebagai username di balik layar).
- Password dapat ditampilkan/disembunyikan lewat ikon mata pada setiap kolom password.
- **Logout** dari sidebar; kembali ke landing page.

### 3.3 Konsultasi AI (`/konsultasi/`)

- Halaman sambutan dengan judul besar, kotak keluhan multiline, tiga topik pemicu sekali klik,
  dan spanduk keselamatan berisi tautan `119`.
- Tampilan obrolan dengan gelembung pengguna (kanan) dan gelembung Lestari AI (kiri, berlogo),
  indikator mengetik ("Lestari AI menganalisis…"), serta render Markdown (judul, daftar,
  tebal, kutipan, tautan).
- Lampiran foto opsional (JPG/PNG/WebP/GIF maksimal **10 MB**) untuk gejala, resep, atau hasil
  lab.
- `Enter` mengirim; `Shift + Enter` menambah baris baru.
- Eskalasi darurat otomatis: jika kata-kata pengguna sendiri cocok dengan kata kunci red flag
  (nyeri dada, sesak napas berat, tanda stroke, perdarahan hebat, keinginan mengakhiri hidup,
  dan sebagainya), jawaban diawali peringatan agar segera menghubungi **119** atau ke IGD.
- Percakapan disimpan sebagai **sesi** dengan judul otomatis (100 karakter pertama pesan
  pertama) dan ditampilkan di sidebar pada bagian **Sesi Terakhir**.
- Sesi memiliki tautan langsung (`/konsultasi/<id>/`) dan dapat dihapus.
- Tiga mode konsultasi didefinisikan di model data — **Triase Lengkap** (default),
  **Konsultasi Cepat**, dan **Tanya Obat & Resep** — tetapi antarmuka obrolan saat ini selalu
  mengirim *Triase Lengkap*; belum ada pemilih mode di layar.
- Pencarian rumah sakit dan pembuatan catatan kesehatan oleh AI terjadi di dalam obrolan yang
  sama (lihat bagian berikutnya).

### 3.4 Catatan Kesehatan (`/catatan/`)

- Menampilkan catatan kesehatan milik pengguna yang sedang masuk, terbaru lebih dulu.
- Setiap catatan adalah laporan yang ditulis ulang oleh AI (bukan salinan obrolan) dengan bagian
  seperti Ringkasan, Keluhan Utama, Kronologi & Detail, Kemungkinan Penyebab, Red Flags, Saran,
  Yang Harus Dihindari, Kapan Harus ke Dokter, dan Kesimpulan.
- Catatan panjang diringkas dengan **Baca selengkapnya / Ciutkan**.
- Setiap catatan dapat diunduh sebagai PDF (`Lestari-<judul>.pdf`) atau dihapus.

### 3.5 Rumah Sakit Terdekat (`/rumah-sakit/`)

- Dua cara mencari: **Gunakan lokasi saya** (geolokasi peramban) atau mengetik nama
  tempat/alamat seperti "SMKN 11 Bandung".
- Mengembalikan maksimal 8 rumah sakit berpenamaan dalam radius **30 km**, diurutkan berdasarkan
  jarak garis lurus, dengan label **Terdekat** pada hasil pertama, alamat, nomor telepon yang
  bisa diklik, tautan **Lihat di peta** (OpenStreetMap), dan **Petunjuk arah** (rute
  berkendara).
- Menampilkan label lokasi dan, untuk lokasi perangkat, perkiraan akurasi peramban beserta
  peringatan bila akurasi lebih buruk dari 1 km.
- Koordinat hanya dipakai untuk pencarian dan tidak disimpan oleh Lestari; hasil rumah sakit
  di-cache per area ~1 km agar tidak melampaui batas layanan peta gratis.
- Sumber data: OpenStreetMap (Nominatim / Photon / Overpass) dan opsional Geoapify.

### 3.6 Cuaca (`/cuaca/`)

- Langsung membuka **Kemayoran, Jakarta Pusat** secara default.
- Ketik minimal 2 karakter di kotak pencarian untuk mendapatkan daftar desa/kelurahan
  (wilayah level-4 BMKG), lalu pilih salah satu.
- Kartu kondisi saat ini: suhu, deskripsi dan ikon cuaca, kelembapan, kecepatan dan arah angin,
  tutupan awan, serta jarak pandang.
- **Prakiraan Beberapa Hari Ke Depan**: kartu per hari dengan slot waktu berisi ikon, kondisi,
  kecepatan angin, dan suhu.
- Data berasal dari API open data resmi BMKG, di-cache selama 10 menit.

### 3.7 Artikel Kesehatan (`/artikel/`)

- Umpan default "Kesehatan", dengan chip filter: **Kesehatan, Fitnes, Nutrisi, Obat,
  Kesehatan Mental, Teknologi Medis**.
- Pencarian bebas (2+ karakter, dengan jeda otomatis; `Enter` juga mencari).
- Setiap kartu menampilkan sumber media, waktu terbit relatif, judul, cuplikan singkat, dan
  membuka artikel asli di tab baru.
- Didukung umpan pencarian Google News RSS, di-cache selama 10 menit.

### 3.8 Profil

- Tersedia di setiap halaman aplikasi: klik avatar bulat di header kanan atas atau di sidebar.
- Modal menampilkan nama, email, dan username, serta memungkinkan mengunggah foto profil baru
  (JPG/PNG/WebP/GIF, maksimal **5 MB**). Foto baru langsung tampil di semua tempat.

---

## 4. Peta Aplikasi (Halaman & URL)

| Halaman | URL | Perlu masuk |
|---|---|---|
| Landing page | `/` | Tidak |
| Masuk (login) | `/login/` | Tidak |
| Daftar (signup) | `/signup/` | Tidak |
| Logout (POST) | `/logout/` | – |
| Konsultasi AI | `/konsultasi/` | Ya |
| Satu sesi konsultasi | `/konsultasi/<session_id>/` | Ya |
| Catatan Kesehatan | `/catatan/` | Ya |
| Rumah Sakit Terdekat | `/rumah-sakit/` | Ya |
| Cuaca | `/cuaca/` | Ya |
| Artikel Kesehatan | `/artikel/` | Ya |
| Django admin (internal) | `/admin/` | Staf/superuser |

Endpoint JSON internal yang dipakai antarmuka (bukan untuk diakses langsung):
`/api/send/`, `/api/sessions/`, `/api/sessions/<id>/`, `/api/sessions/<id>/delete/`,
`/api/notes/`, `/api/notes/<id>/delete/`, `/api/nearby-hospitals/`, `/api/cuaca/search/`,
`/api/cuaca/forecast/`, `/api/artikel/`, `/api/profile/avatar/`.

---

## 5. Tutorial Pengguna Lengkap

Panduan di bawah memakai peramban desktop; di ponsel tata letaknya sama, hanya sidebar
tersembunyi di balik tombol ☰ (hamburger) di kiri atas.

### 5.1 Membuat Akun

1. Buka situs Lestari. Anda akan berada di halaman pemasaran (`/`).
2. Klik **Daftar** di kanan atas (atau tombol "Mulai Gratis" mana pun di halaman).
3. Di layar autentikasi, tab **Daftar** sudah aktif. Jika yang tampil **Masuk**, klik **Daftar**
   pada pengalih tab di bagian atas kartu.
4. Opsional, tambahkan foto profil: klik lingkaran putus-putus dengan ikon orang
   (**Foto Profil (opsional)**), lalu pilih gambar. Format JPG, PNG, WebP, atau GIF, maksimal
   5 MB.
5. Isi:
   - **Nama Lengkap** — nama tampilan Anda (misalnya `Sari Wulandari`).
   - **Email** — dipakai sebagai identitas login (misalnya `sari@example.com`).
   - **Password** — minimal 8 karakter.
   - **Konfirmasi Password** — ulangi password yang sama.
   - Gunakan ikon mata di kolom password untuk memeriksa yang Anda ketik.
6. Klik **Register Akun**.
7. Lestari membuat akun dan langsung memasukkan Anda, lalu membuka **Konsultasi AI** di
   `/konsultasi/`.

> **Jika pendaftaran gagal**, kotak merah menjelaskan penyebabnya: ada kolom kosong, format
> email tidak valid, konfirmasi password tidak sama, password kurang dari 8 karakter, email
> sudah terdaftar, atau foto profil tidak valid/terlalu besar.

### 5.2 Masuk (Login)

1. Buka situs dan klik **Masuk** (atau buka `/login/` langsung).
2. Pastikan tab **Masuk** aktif.
3. Isi **Email** dan **Password**.
4. Klik **Masuk Sekarang**.
5. Anda diarahkan ke **Konsultasi AI**.

Jika kredensial salah, kartu menampilkan *"Email atau password tidak valid. Silakan coba lagi."*
— periksa kembali ejaan email dan password (gunakan ikon mata).

> Login diperlukan untuk semua fitur kecuali landing page. Jika Anda membuka halaman aplikasi
> saat belum masuk, Anda dikembalikan ke halaman awal untuk masuk.

### 5.3 Mengajukan Pertanyaan ke Lestari AI

Ini alur inti, langkah demi langkah.

1. **Masuk** terlebih dahulu (lihat 5.2). Anda sekarang berada di halaman **Konsultasi AI**.
2. Jika belum di sana, klik **Konsultasi AI** di sidebar kiri, atau tekan
   **Konsultasi AI Baru**.
3. Di layar sambutan terlihat judul *"Ada keluhan kesehatan apa hari ini?"* dan kartu input.
   Tersedia juga tiga chip pintasan:
   - **Demam & Meriang > 2 Hari**
   - **Dada Sesak & Asam Lambung Naik**
   - **Cek Interaksi Obat & Dosis**

   Mengklik salah satunya hanya *mengisi* kotak teks dengan contoh keluhan — Anda tetap harus
   mengirimnya sendiri (dan boleh mengeditnya lebih dulu).
4. Klik di dalam kotak teks (placeholder: *"Ceritakan keluhan Anda…"*) dan tulis pertanyaan
   dengan bahasa sehari-hari. Semakin spesifik, semakin baik analisisnya. Detail yang sebaiknya
   disertakan:
   - apa yang dirasakan dan di bagian mana,
   - sudah berapa lama,
   - seberapa berat dan apakah makin memburuk,
   - apa yang sudah dicoba (obat, dosis),
   - riwayat relevan (kehamilan, penyakit kronis, alergi),
   - usia, jika relevan.

   Contoh: *"Sudah 3 hari demam naik turun sampai 38,5°C, disertai nyeri sendi dan mual.
   Sudah minum paracetamol 500 mg dua kali sehari."*
5. Kirim pertanyaan dengan salah satu cara:
   - tekan **Enter**, atau
   - klik tombol biru bulat berikon **↑** di sisi kanan kartu input (tooltip:
     *"Kirim Keluhan ke AI"*).

   Untuk menulis beberapa baris tanpa mengirim, gunakan **Shift + Enter**.
6. Layar beralih ke tampilan obrolan. Pesan Anda muncul sebagai gelembung biru di kanan,
   diikuti indikator animasi kecil bertuliskan **"Lestari AI menganalisis…"**. Tombol kirim
   berubah menjadi ikon berputar dan tidak aktif selama menunggu. Bergantung panjang jawaban,
   proses ini biasanya beberapa detik.
7. Jawaban muncul sebagai gelembung putih di kiri dengan logo Lestari. Formatnya berisi judul
   bagian, poin-poin, istilah tebal, dan catatan penutup.
8. Baca jawabannya. Bagian yang umum untuk pertanyaan gejala:

   | Bagian | Artinya |
   |---|---|
   | **Ringkasan** | Penilaian singkat atas keluhan Anda. |
   | **Kemungkinan Penyebab** | Kemungkinan penyebab beserta perkiraan peluang dan alasannya. |
   | **Hal yang Perlu Diperhatikan (Red Flags)** | Tanda bahaya yang berarti Anda perlu segera mencari bantuan medis. |
   | **Yang Bisa Dilakukan Sekarang** | Langkah perawatan mandiri yang aman. |
   | **Yang Harus Dihindari** | Hal-hal yang dapat memperburuk kondisi. |
   | **Kapan Harus ke Dokter** | Ambang batas konkret untuk menemui tenaga medis. |
   | **Kesimpulan** | Rangkuman dan langkah berikutnya. |

9. Anda dapat langsung menulis pesan lain di kotak yang sama; percakapan berlanjut dengan
   konteks penuh (lihat 5.4).

> Jika Anda bertanya hal yang tidak berkaitan dengan kesehatan, Lestari AI membalas dengan
> penolakan baku yang meminta Anda mengajukan pertanyaan kesehatan.

### 5.4 Mengirim Pertanyaan Lanjutan

1. Tetap di obrolan yang sama — kartu input kini menempel di bawah layar dan placeholder-nya
   berbunyi *"Tulis pesan lanjutan…"*.
2. Tulis pertanyaan lanjutan, misalnya *"Kalau demamnya tidak turun setelah 3 hari, apa yang
   harus saya lakukan?"*.
3. Tekan **Enter** atau klik tombol **↑**.
4. Lestari AI menerima **seluruh percakapan**, jadi Anda tidak perlu mengulang gejala. Anda bisa
   melanjutkan selama diperlukan.
5. Judul sesi di header diambil dari pesan **pertama** dan tidak berubah setelahnya.

### 5.5 Melampirkan Foto

Gunakan untuk ruam, luka, kemasan obat, resep, atau hasil laboratorium.

1. Di kartu input, klik tombol **Foto** (ikon foto di sisi kiri, tooltip *"Unggah Foto Gejala
   atau Hasil Lab"*).
2. Pilih gambar dari perangkat. Format yang diizinkan: **JPG, PNG, WebP, GIF**, maksimal
   **10 MB**.
3. Thumbnail beserta nama berkas muncul di atas kotak teks. Klik **×** pada chip tersebut untuk
   membatalkan lampiran sebelum dikirim.
4. Tulis pertanyaan singkat sebagai konteks, misalnya *"Ini hasil laboratorium saya, tolong
   bantu jelaskan artinya."*
5. Kirim dengan **Enter** atau **↑**. Gambar ditampilkan di dalam gelembung pesan Anda dan
   dikirim ke AI bersama teks.
6. Pada pesan lanjutan Anda dapat melampirkan foto lain dengan cara yang sama.

> Jenis berkas yang salah atau berkas lebih dari 10 MB langsung ditolak dengan pesan singkat di
> bawah kotak input; berkas tidak dikirim.

### 5.6 Membaca dan Menindaklanjuti Peringatan Darurat

1. Bila pesan Anda sendiri mengandung red flag darurat (misalnya *"nyeri dada"*,
   *"sesak napas berat"*, *"pingsan"*, *"muntah darah"*, tanda stroke, atau keinginan menyakiti
   diri), jawaban diawali peringatan menyala:
   **"⚠️ Kondisi ini bisa merupakan kegawatdaruratan. Segera hubungi 119 atau pergi ke unit
   gawat darurat terdekat. Jangan menunggu."**
2. Anggap ini mendesak: hubungi **119** (nomor telepon dapat diklik di seluruh aplikasi) atau
   pergi ke IGD terdekat.
3. Untuk saran rumah sakit di obrolan yang sama, tanyakan *"Rumah sakit terdekat dari [lokasi
   saya / nama tempat]"*; peramban mungkin meminta izin lokasi, lalu Lestari AI menampilkan
   daftar rumah sakit terdekat. Halaman **Rumah Sakit Terdekat** (5.10) memberikan daftar
   lengkap, peta, dan petunjuk arah.
4. Jangan menunggu jawaban obrolan sebelum mencari pertolongan pada keadaan darurat nyata.

### 5.7 Membuka Kembali, Melanjutkan, dan Menghapus Sesi Lama

1. Perhatikan sidebar kiri, bagian **Sesi Terakhir**. Daftar berisi hingga 8 konsultasi
   terakhir, masing-masing dengan judul dan waktu pembaruan terakhir.
2. Klik salah satu sesi untuk memuat riwayat lengkapnya. Obrolan terbuka kembali dengan semua
   pesan sebelumnya dan URL berubah menjadi `/konsultasi/<id>/`, sehingga dapat disimpan sebagai
   bookmark atau dimuat ulang.
3. Tulis pesan baru lalu kirim untuk melanjutkan percakapan tersebut beserta konteks sebelumnya.
4. Untuk memulai dari awal, klik **Konsultasi AI Baru** di bagian atas sidebar. Anda kembali ke
   layar sambutan tanpa menghapus apa pun.
5. Untuk menghapus sesi:
   - arahkan kursor ke sesi di sidebar lalu klik ikon tempat sampah di kanannya, **atau**
   - buka sesi tersebut dan klik ikon tempat sampah di header atas (di sebelah avatar).
6. Konfirmasi dialog (*"Hapus sesi ini? …"* / *"Hapus percakapan ini? …"*). Sesi dan seluruh
   pesannya dihapus permanen; foto yang terlampir juga dihapus dari penyimpanan.

> Pada layar sempit, ketuk ☰ terlebih dahulu untuk membuka sidebar, lalu ketuk sesi.

### 5.8 Menyimpan Konsultasi sebagai Catatan Kesehatan

1. Lakukan konsultasi terlebih dahulu (5.3), agar ada bahan untuk dirangkum.
2. Di obrolan yang sama, kirim permintaan seperti:
   - *"Buatkan catatan kesehatan dari percakapan ini"*
   - *"Simpan rekap kondisi saya"*
   - *"Buat ringkasan kesehatan dari chat ini"*
3. Lestari AI menyimpan catatan dan membalas:
   **"✅ Catatan kesehatan "…" berhasil disimpan di halaman Catatan Kesehatan."**
4. Notifikasi *toast* juga muncul di bagian atas layar sebagai konfirmasi.
5. Isi catatan **bukan** salinan obrolan: proses AI kedua yang berjalan diam-diam merangkum
   seluruh transkrip menjadi laporan terstruktur yang bisa dibaca ulang atau diberikan kepada
   dokter.
6. Buka **Catatan Kesehatan** di sidebar untuk melihatnya (lihat 5.9).

> Pertanyaan biasa tidak membuat catatan — hanya permintaan eksplisit yang melakukannya. Minta
> catatan selama sesi masih ada; jika sesi dihapus kemudian, obrolannya hilang tetapi catatan
> tetap tersimpan (terhubung ke akun Anda, bukan ke obrolan).

### 5.9 Membaca, Memperluas, Mengunduh, dan Menghapus Catatan Kesehatan

1. Klik **Catatan Kesehatan** di sidebar (atau buka `/catatan/`).
2. Catatan diurutkan dari yang terakhir diperbarui. Setiap kartu menampilkan judul dan tanggal
   serta waktu.
3. Jika catatan panjang, tampilannya dipendekkan dengan efek pudar; klik **Baca selengkapnya**
   untuk membuka dan **Ciutkan** untuk menutup kembali.
4. Klik **ikon PDF** (tooltip *"Unduh PDF"*) untuk mengunduh catatan sebagai
   `Lestari-<judul>.pdf`. PDF dibuat di peramban Anda; bergantung panjang catatan, prosesnya
   bisa memakan waktu sejenak.
5. Klik **ikon tempat sampah** (tooltip *"Hapus Catatan"*), lalu konfirmasi untuk menghapus
   catatan secara permanen.
6. Jika halaman kosong, akan tampil petunjuk dan tombol **Mulai Konsultasi AI** — artinya Anda
   belum menyimpan catatan.

### 5.10 Mencari Rumah Sakit Terdekat

**Cara A — memakai lokasi saat ini**

1. Klik **Rumah Sakit Terdekat** di sidebar (atau buka `/rumah-sakit/`).
2. Klik **Gunakan lokasi saya**.
3. Peramban meminta izin lokasi — pilih **Allow** (izinkan).
   (Ini memerlukan koneksi HTTPS; pada HTTP biasa peramban tidak menawarkan lokasi.)
4. Tunggu proses pencarian. Hasil muncul sebagai kartu berisi:
   - nama rumah sakit (kartu pertama diberi label **Terdekat**),
   - alamat,
   - nomor telepon yang bisa diklik,
   - jarak, misalnya `2,4 km` (perkiraan garis lurus, **bukan** waktu tempuh),
   - **Lihat di peta** — membuka rumah sakit di OpenStreetMap,
   - **Petunjuk arah** — membuka rute berkendara dari lokasi Anda.
5. Di atas daftar terlihat label lokasi Anda dan, untuk lokasi perangkat, perkiraan akurasi
   peramban. Jika akurasi lebih buruk dari 1 km, muncul saran untuk mencari berdasarkan alamat.
6. Klik **Cari lagi** untuk mengulangi pencarian.

**Cara B — mencari berdasarkan tempat atau alamat**

1. Pada kartu **"Lokasi perangkat kurang tepat?"**, ketik tempat atau alamat, misalnya
   `SMKN 11 Bandung` atau `Jl. Asia Afrika Bandung`.
2. Klik **Cari alamat**.
3. Daftar diperbarui dengan lokasi tersebut sebagai titik acuan.

Catatan:

- Hanya rumah sakit dalam radius sekitar **30 km** yang dikembalikan, maksimal **8**.
- Jika tidak ada hasil, halaman menyatakan belum ada rumah sakit terdata dalam radius tersebut
  dan menyarankan menghubungi **119** untuk keadaan darurat.
- Jika izin ditolak, aplikasi menampilkan pesan agar Anda mengaktifkan lokasi untuk situs ini di
  pengaturan peramban; pencarian alamat tetap bisa dipakai.
- Koordinat persis Anda tidak disimpan oleh Lestari; hanya cache hasil rumah sakit per area
  ~1 km yang disimpan agar layanan peta gratis tidak kelebihan beban.

### 5.11 Memeriksa Cuaca (BMKG)

1. Klik **Cuaca** di sidebar (atau buka `/cuaca/`).
2. Halaman langsung memuat prakiraan untuk **Kemayoran, Jakarta Pusat**.
3. Untuk daerah lain, klik kotak pencarian (*"Cari desa/kelurahan…"*) dan ketik minimal dua
   huruf, misalnya `Tebet` atau `Bandung`.
4. Tunggu sebentar; daftar dropdown muncul berisi desa/kelurahan yang cocok beserta jalur
   wilayahnya. Klik yang Anda inginkan.
5. Baca kartu kondisi saat ini: jejak lokasi, suhu besar, teks dan ikon kondisi, lalu kelembapan,
   kecepatan/arah angin, tutupan awan, dan jarak pandang.
6. Gulir ke **Prakiraan Beberapa Hari Ke Depan** untuk kartu per hari; setiap baris menampilkan
   waktu, ikon, kondisi, kecepatan angin, dan suhu.
7. Gunakan **×** di dalam kotak pencarian untuk menghapus teks, lalu cari lokasi lain.

> Jika lokasi tidak ditemukan atau data BMKG tidak tersedia, pesan galat muncul di bawah kotak
> pencarian. Prakiraan di-cache 10 menit, jadi pengulangan langsung menampilkan data yang sama.

### 5.12 Membaca Artikel Kesehatan

1. Klik **Artikel Kesehatan** di sidebar (atau buka `/artikel/`).
2. Umpan terbuka pada **Kesehatan**. Gunakan chip di bagian atas untuk berganti topik: **Fitnes,
   Nutrisi, Obat, Kesehatan Mental, Teknologi Medis**.
3. Untuk mencari, ketik minimal dua karakter di *"Cari artikel kesehatan, topik, atau kata
   kunci…"*; hasil dimuat otomatis setelah jeda singkat (atau tekan **Enter**).
4. Setiap kartu menampilkan sumber media, waktu terbit relatif, judul, dan cuplikan singkat.
   Klik **Baca Selengkapnya** (atau bagian mana pun dari kartu) untuk membuka artikel lengkap di
   situs penerbit pada tab baru.
5. Gunakan **×** di kotak pencarian untuk menghapusnya, lalu pilih chip lagi untuk kembali ke
   umpan topik.

> Hasil berasal dari Google News dan di-cache 10 menit. Hasil kosong berarti tidak ada artikel
> yang cocok dengan pencarian Anda.

### 5.13 Mengubah Foto Profil

1. Klik avatar bulat di header kanan atas (atau avatar di bagian bawah sidebar).
2. Modal profil terbuka menampilkan foto, nama, email, dan username Anda.
3. Klik **Ubah Foto Profil** dan pilih gambar (JPG/PNG/WebP/GIF, maksimal 5 MB).
4. Baris status menampilkan *"Mengunggah foto profil…"*, lalu *"Foto profil berhasil
   diperbarui!"*. Foto baru langsung menggantikan yang lama di semua tempat.
5. Tutup modal dengan **×**, klik latar gelap, atau tekan **Esc**.

> Jika unggahan gagal, baris status berubah merah dengan alasannya (format salah, lebih dari
> 5 MB, atau masalah penyimpanan). Foto lama tetap tidak berubah.

### 5.14 Keluar (Logout)

1. Di bagian bawah sidebar, di samping nama dan email Anda, klik ikon **logout** (tooltip
   *"Logout"*).
2. Anda keluar dan kembali ke landing page. Sesi dan catatan kesehatan tetap tersimpan di akun
   Anda untuk login berikutnya.

---

## 6. Pemecahan Masalah & FAQ

| Gejala | Kemungkinan penyebab / yang perlu dilakukan |
|---|---|
| *"Email atau password tidak valid."* | Email atau password salah. Periksa ejaan; gunakan ikon mata untuk memastikan password. Password membedakan huruf besar-kecil. |
| *"Email sudah terdaftar."* saat mendaftar | Sudah ada akun dengan email tersebut — beralihlah ke tab **Masuk**. |
| *"Password minimal 8 karakter."* | Pilih password yang lebih panjang; konfirmasi harus sama persis. |
| AI membalas *"Maaf, terjadi kendala menghubungi Lestari AI…"* | Permintaan ke Gemini gagal (kunci `GEMINI_API_KEY` tidak ada/tidak valid di server, kuota habis, atau gangguan sementara). Tunggu dan coba lagi; jika berlanjut, hubungi operator. |
| *"Maaf, koneksi ke Lestari AI terputus…"* | Jaringan terputus saat permintaan berjalan. Periksa koneksi dan kirim ulang; pertanyaan sebelumnya mungkin tidak tersimpan. |
| *"Foto maksimal 10 MB."* / *"Hanya JPG, PNG, WebP, atau GIF."* | Kompres, konversi, atau pilih gambar yang lebih kecil sebelum mengirim. |
| Tombol kirim tidak berbuat apa-apa | Kotak kosong (hanya spasi) atau masih ada permintaan yang berjalan. Tulis sesuatu dan tunggu ikon berputar selesai. |
| *"Izin lokasi tidak diberikan…"* | Izin lokasi diblokir. Aktifkan untuk situs ini di pengaturan peramban, atau gunakan pencarian alamat di halaman Rumah Sakit. |
| *"Akses lokasi membutuhkan koneksi HTTPS…"* | Geolokasi hanya berfungsi pada HTTPS (atau `localhost`). Gunakan situs aman atau pencarian alamat. |
| *"Lokasi tidak ditemukan…"* | Tempat tersebut belum ada di OpenStreetMap. Ketik alamat lebih lengkap dengan kota/provinsi, atau gunakan lokasi perangkat. |
| Pencarian cuaca tidak memberi hasil | Ketik minimal 2 karakter dan gunakan nama desa/kelurahan; BMKG hanya melayani wilayah level-4. |
| Daftar artikel kosong | Tidak ada hasil Google News untuk kueri tersebut. Coba kata kunci lebih umum atau chip lain. |
| Unduhan PDF gagal | PDF dibuat di peramban; pastikan skrip tidak diblokir lalu coba lagi. |
| Riwayat sesi kosong | Anda belum menyelesaikan konsultasi; pesan pertama yang membuat sesi. |
| Sidebar/menu tidak terlihat di ponsel | Ketuk tombol ☰ di header kiri atas untuk membuka sidebar. |

---

## 7. Keterbatasan yang Diketahui

Dicatat apa adanya agar ekspektasi tetap tepat:

- **Riwayat konsultasi belum dibatasi per akun.** API sesi dan halaman
  `/konsultasi/<id>/` mengambil sesi tanpa memfilter pengguna yang sedang masuk, sehingga setiap
  pengguna yang sudah masuk dapat membuka daftar sesi dan sesi mana pun berdasarkan ID-nya.
  Catatan kesehatan *sudah* dibatasi per pengguna. Jangan menganggap riwayat obrolan bersifat
  privat antar-akun sampai hal ini diperbaiki.
- **Belum ada pemilih mode.** *Konsultasi Cepat* dan *Tanya Obat & Resep* ada di model dan API,
  tetapi obrolan selalu mengirim *Triase Lengkap*.
- **Belum ada alur lupa password atau verifikasi email**; backend email konsol hanya
  dikonfigurasi untuk pengembangan.
- **Belum ada halaman pengaturan akun** selain modal foto profil (nama/email belum dapat diubah
  dari antarmuka).
- **Jawaban AI bergantung pada API Gemini** yang dapat dihubungi dan berkunci benar; tidak ada
  mesin jawaban cadangan atau mode offline.
- **Data pihak ketiga bisa tidak lengkap:** OpenStreetMap/Geoapify mungkin belum memuat rumah
  sakit atau tempat tertentu, BMKG bisa sementara tidak tersedia, dan hasil Google News
  bervariasi.
- Lestari AI adalah bantuan triase edukatif, **bukan** alat medis, diagnosis, atau layanan
  resep.

---

## 8. Untuk Pengembang

### 8.1 Teknologi

- **Backend:** Django 6.1.1 (Python), gaya penerapan serverless di Vercel (`config/wsgi.py`,
  `.vercel/`).
- **Basis data:** SQLite secara default di lokal; PostgreSQL (misalnya Supabase) melalui
  `DATABASE_URL` di produksi.
- **AI:** Google Gemini 2.5 Flash melalui SDK `google-genai`, dengan system instruction yang
  ketat dan dua tool function-calling.
- **Penyimpanan:** bucket kompatibel S3 (Supabase Storage) untuk avatar dan gambar obrolan.
- **Frontend:** template Django dengan Tailwind (build CDN), Plus Jakarta Sans, Material Symbols,
  dan JavaScript vanilla per halaman. Ekspor PDF memakai `html2canvas` + `jsPDF`.
- **Data eksternal:** open data BMKG, Google News RSS, Nominatim/Photon/Overpass, dan opsional
  Geoapify.

### 8.2 Struktur proyek

```
config/                 pengaturan Django, URL, WSGI
konsultasi/
  templates/konsultasi/ landing.html, auth.html, index.html (obrolan),
                        catatan.html, rumah_sakit.html, cuaca.html,
                        artikel.html, _sidebar.html
  views.py              halaman + API JSON
  urls.py               peta rute
  models.py             Profile, ConsultationSession, ConsultationMessage,
                        HealthNote, WeatherCache, WeatherSearchCache,
                        ArtikelCache, GeocodeCache, HospitalSearchCache
  services.py           prompt Gemini, tool, proses laporan kesehatan, kata kunci darurat
  hospitals.py          geocoding + pencarian rumah sakit Overpass/Geoapify + cache
  places.py             alias tempat kurasi untuk lokasi yang belum ada di OSM
  bmkg.py               pencarian + prakiraan BMKG + cache
  artikel.py            parsing Google News RSS + cache
  storage.py            unggah/hapus avatar dan gambar obrolan di S3
  admin.py              pendaftaran Django admin
static/                 lestari.css, lestari-navigation.js, images
manage.py, requirements.txt, db.sqlite3
```

### 8.3 Variabel lingkungan

| Variabel | Fungsi |
|---|---|
| `DJANGO_SECRET_KEY` | **Wajib** saat `DEBUG` nonaktif. |
| `DJANGO_DEBUG` | `true`/`false`; default `true` di lokal, `false` di Vercel. |
| `DJANGO_ALLOWED_HOSTS` | Daftar host tambahan dipisahkan koma. |
| `CSRF_TRUSTED_ORIGINS` | Origin tepercaya dipisahkan koma untuk POST HTTPS. |
| `DATABASE_URL` | URL basis data; default `db.sqlite3` lokal. |
| `GEMINI_API_KEY` | Kunci API Gemini untuk Lestari AI. |
| `GEOAPIFY_API_KEY` | Opsional; geocoding dan pencarian rumah sakit lebih cepat/stabil. |
| `OVERPASS_URLS` | Opsional, daftar mirror Overpass dipisahkan koma. |
| `NOMINATIM_USER_AGENT` | User-Agent yang dikirim ke layanan OpenStreetMap. |
| `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME`, `S3_PUBLIC_BASE_URL` | Penyimpanan foto profil dan gambar obrolan. |

### 8.4 Menjalankan di lokal

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser     # opsional, untuk /admin/
python manage.py runserver
```

Lalu buka `http://127.0.0.1:8000/`, daftarkan akun, dan mulai konsultasi. Isi
`GEMINI_API_KEY` di `.env` sebelum memakai obrolan; halaman rumah sakit, cuaca, dan artikel tetap
berfungsi tanpanya (mengandalkan layanan publik).
