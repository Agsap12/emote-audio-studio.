# Panduan Deploy & Integrasi — Emote Audio Studio

Dokumentasi lengkap untuk setup **Ekstensi Browser (Manifest V3)**, **Cloud Backend 24 Jam**, dan **Cloudflare Turnstile**.

---

## 1. Pembuatan & Pemasangan Ekstensi Browser (Manifest V3)

Ekstensi ini berfungsi untuk:
- Mendeteksi sesi login Roblox yang sedang aktif di browser secara otomatis (Username, Display Name, User ID).
- Mengambil daftar grup Roblox tempat akunmu memiliki akses/role, sehingga ID grup tidak perlu dicari manual.
- Mendeteksi Sound / Asset ID baru di Roblox Creator Dashboard (`create.roblox.com`) dan menyediakan tombol satu-klik **"Salin ID"** serta auto-sync ke Emote Audio Studio.
- Menghubungkan Web App Emote Audio Studio (`Index.HTML`) langsung dengan sesi Roblox browser.

### Cara Memasang di Chrome / Edge / Brave:
1. Buka browser (Google Chrome, Microsoft Edge, atau Brave).
2. Masuk ke halaman ekstensi:
   - **Chrome**: `chrome://extensions/`
   - **Edge**: `edge://extensions/`
   - **Brave**: `brave://extensions/`
3. Aktifkan **Developer Mode** (Mode Pengembang) di pojok kanan atas.
4. Klik tombol **Load Unpacked** (Muat yang belum dibongkar).
5. Pilih folder ekstensi di proyek ini:
   `H:\roblox project\asset low polly\music emot\WEB\auto\extension`
6. Ekstensi **"Emote Audio Studio — Roblox Auto Bridge"** akan langsung aktif.
7. Buka `Index.HTML` atau `http://127.0.0.1:8765/`, badge ekstensi di header akan otomatis berubah menjadi **"Ekstensi: Aktif 🟢"**.

---

## 2. Setup Backend Cloud 24 Jam (Render / Railway / HuggingFace)

Dengan backend cloud, aplikasi dapat memproses unduhan audio TikTok/YouTube dan upload ke Roblox 24 jam nonstop tanpa perlu menyalakan PC.

### Pilihan A: Render.com (Gratis & Sangat Stabil)
1. Push folder `H:\roblox project\asset low polly\music emot\WEB\auto` ke repositori GitHub pribadi.
2. Buka [dashboard.render.com](https://dashboard.render.com/) dan login.
3. Klik **New +** -> **Web Service**.
4. Hubungkan repositori GitHub-mu.
5. Konfigurasi service:
   - **Runtime**: `Docker` (Render otomatis mendeteksi `Dockerfile`)
   - **Region**: Singapore (paling cepat untuk Indonesia)
   - **Instance Type**: `Free`
6. Environment Variables (opsional):
   - `EAS_CLOUD` = `1`
   - `CLOUDFLARE_TURNSTILE_SECRET_KEY` = `(Secret key dari Cloudflare milikmu)`
   - `EAS_ENFORCE_TURNSTILE` = `0` (atau `1` jika ingin wajib Turnstile)
7. Klik **Create Web Service**. Setelah deploy selesai, kamu akan mendapatkan URL seperti:
   `https://emote-audio-studio-xxxx.onrender.com`
8. Buka `Index.HTML` -> Buka bagian **6. Akun dan Pengaturan** -> Buka **Pengaturan Server Backend** -> Masukkan URL Render tersebut -> Klik **Simpan & Tes**.

### Pilihan B: Railway.app
1. Buka [railway.app](https://railway.app/) dan buat project baru.
2. Pilih **Deploy from GitHub repo**.
3. Railway akan membaca `railway.json` dan `Dockerfile` secara otomatis.
4. Di tab Settings, klik **Generate Domain** untuk mendapatkan URL publik (misal: `https://eas-production.up.railway.app`).
5. Masukkan domain tersebut ke input server di `Index.HTML`.

### Pilihan C: Hugging Face Spaces (Gratis 24 Jam Bebas Kuota)
1. Buka [huggingface.co/spaces](https://huggingface.co/spaces) -> Klik **Create new Space**.
2. Berikan nama Space, pilih **Space SDK**: **Docker** (Blank).
3. Upload file `Dockerfile`, `requirements.txt`, `app.py`, `Index.HTML`, dan folder proyek ke Space tersebut.
4. Hugging Face akan mem-build container Docker dan menjalankan server pada port `7860`.

---

## 3. Integrasi Cloudflare Turnstile & Verifikasi Token

Emote Audio Studio telah terintegrasi penuh dengan Cloudflare Turnstile:
- **Frontend (`Index.HTML`)**: Widget Turnstile terpasang dengan theme adaptif (`auto`) dan callback otomatis (`onTurnstileSuccess`, `onTurnstileExpired`, `onTurnstileError`).
- **Site Key Default**: Menggunakan official Cloudflare testing sitekey `1x00000000000000000000AA` (selalu lolos / testing friendly).
- **Backend (`app.py`)**:
  - Endpoint verifikasi token: `POST /api/turnstile/verify`
  - Validasi otomatis saat upload Roblox: token dikirim melalui header `CF-Turnstile-Response` dan form data `turnstile_token`.
  - Menggunakan API resmi Cloudflare: `https://challenges.cloudflare.com/turnstile/v0/siteverify`.

---

## 4. UI Apple Liquid Glass (visionOS / iOS 18 Design System)

Fitur UI yang disempurnakan:
1. **Dynamic Spatial Header**:
   - Menampilkan status live backend server (`Lokal 🟢` / `Cloud 24 Jam (XX ms) 🟢` / `Offline 🔴`).
   - Menampilkan status ekstensi browser (`Aktif 🟢` / `Tidak aktif`).
   - Tombol toggle tema gelap (Dark) dan terang (Light) dengan transisi lembut.
2. **Auto Group Sync**:
   - Deteksi grup otomatis dari ekstensi langsung memunculkan pemilih grup di langkah ke-6, cukup klik **"Gunakan Grup Ini"** untuk mengisi ID Grup.
3. **Turnstile Glass Container**:
   - Wadah frosted glass dengan indikator status verifikasi manusia.
4. **Waveform & Sound Tuner**:
   - Canvas audio reactive dengan dynamic peaks, reverb slider, pitch & speed calculator untuk simulasi in-game Roblox.

