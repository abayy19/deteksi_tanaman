# 🌱 Agentic Plant Doctor

Aplikasi diagnosis penyakit tanaman berbasis **2 AI Agent yang berkolaborasi (agentic pipeline)**:

| Agent | Model | Peran |
|---|---|---|
| 🖼️ **Vision Agent** | Google **Gemini** (`gemini-2.0-flash`) | Menganalisis foto tanaman secara objektif → mengekstrak gejala visual (warna bercak, tekstur, pola, dll) |
| 🩺 **Diagnosis Agent** | **Groq** (`llama-3.3-70b-versatile`) | Menerima gejala dari teks user + hasil Vision Agent → menyusun **Kartu Diagnosis** lengkap sesuai format UI/UX wajib |

Alur kerja:

```
User (teks &/atau foto)
        │
        ▼
[Vision Agent - Gemini]  ← hanya aktif jika ada foto
        │  (deskripsi gejala visual objektif)
        ▼
[Orchestrator]  ← menggabungkan teks user + hasil vision agent
        │
        ▼
[Diagnosis Agent - Groq]  ← menyusun Kartu Diagnosis final (format markdown wajib)
        │
        ▼
   Ditampilkan di UI Streamlit
```

---

## 📦 Struktur Proyek

```
plant_doctor_app/
├── app.py                        # Aplikasi utama Streamlit
├── prompts.py                    # System prompt masing-masing agent
├── requirements.txt              # Dependencies
├── .streamlit/
│   └── secrets.toml.example      # Contoh format API key
└── README.md
```

---

## 🔑 1. Siapkan API Key

- **Groq API Key**: daftar gratis di https://console.groq.com/keys
- **Gemini API Key**: daftar gratis di https://aistudio.google.com/apikey

Kamu bisa memasukkan key ini langsung di **sidebar aplikasi** saat runtime (paling praktis),
atau menyimpannya di `secrets.toml` (lihat langkah 3).

---

## 💻 2. Jalankan Secara Lokal

```bash
# 1. Buat virtual environment (opsional tapi disarankan)
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Jalankan aplikasi
streamlit run app.py
```

Aplikasi akan terbuka otomatis di `http://localhost:8501`.

---

## 🔐 3. (Opsional) Simpan API Key via Secrets

Agar tidak perlu input manual setiap kali:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Lalu edit `.streamlit/secrets.toml` dan isi dengan key asli kamu.
File ini **sudah otomatis diabaikan** — jangan sampai ter-commit ke Git publik.

---

## ☁️ 4. Deploy ke Streamlit Community Cloud

1. Push folder ini ke repository GitHub (public/private).
   Pastikan **tidak** mengikutsertakan `secrets.toml` asli (hanya `.example`-nya).
2. Buka https://share.streamlit.io → **New app**.
3. Pilih repo, branch, dan file utama: `app.py`.
4. Sebelum deploy, buka menu **Advanced settings → Secrets**, lalu tempel:
   ```toml
   GROQ_API_KEY = "gsk_xxxxxxxxxxxxxxxxxxxxxxxx"
   GEMINI_API_KEY = "AIzaSyxxxxxxxxxxxxxxxxxxxx"
   ```
5. Klik **Deploy**. Selesai! 🎉

---

## ⚙️ 5. Kustomisasi

- **Ganti model**: pilih dari dropdown di sidebar (`llama-3.3-70b-versatile`,
  `llama-3.1-8b-instant`, `gemma2-9b-it` untuk Groq; `gemini-2.0-flash`,
  `gemini-1.5-flash`, `gemini-1.5-pro` untuk Gemini).
- **Ubah gaya/format jawaban**: edit `DIAGNOSIS_AGENT_PROMPT` di `prompts.py`.
- **Ubah cara Vision Agent mengamati gambar**: edit `VISION_AGENT_PROMPT` di `prompts.py`.

---

## ⚠️ Disclaimer

Diagnosis dihasilkan oleh AI dan bersifat referensi awal. Untuk serangan berat atau
tanaman bernilai ekonomi tinggi, tetap konsultasikan dengan Penyuluh Pertanian
Lapangan (PPL) atau ahli fitopatologi setempat.
