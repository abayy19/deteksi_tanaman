"""
🌱 Agentic Plant Doctor
Aplikasi Diagnosis Penyakit Tanaman berbasis 2 AI Agent:
  1. Vision Agent   -> Google Gemini (multimodal, menganalisis foto tanaman)
  2. Diagnosis Agent -> Groq (Llama 3.3 70B, menyusun Kartu Diagnosis final)

Alur Agentic:
  User Input (teks &/atau gambar)
        │
        ▼
  [Vision Agent - Gemini] ── (hanya jalan jika ada gambar)
        │  menghasilkan: deskripsi gejala visual objektif
        ▼
  [Orchestrator] ── menggabungkan teks user + hasil vision agent
        │
        ▼
  [Diagnosis Agent - Groq] ── menyusun Kartu Diagnosis sesuai format wajib
        │
        ▼
  Ditampilkan ke pengguna (Streamlit UI)
"""

import streamlit as st
from PIL import Image
import io
import time

from prompts import VISION_AGENT_PROMPT, DIAGNOSIS_AGENT_PROMPT

# ------------------------------------------------------------------
# KONSTANTA RETRY
# ------------------------------------------------------------------
MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 5  # backoff naik: 5s, 10s, 20s...

# Model fallback jika model utama kena limit (dari yang paling "berat" ke "ringan")
GEMINI_FALLBACK_CHAIN = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-flash-8b"]
GROQ_FALLBACK_CHAIN = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "gemma2-9b-it"]


def _is_rate_limit_error(exc: Exception) -> bool:
    """Deteksi error kuota/rate-limit dari berbagai kemungkinan exception (Gemini & Groq)."""
    msg = str(exc).lower()
    keywords = ["resourceexhausted", "resource exhausted", "429", "rate limit", "quota"]
    return any(k in msg or k in type(exc).__name__.lower() for k in keywords)

# ------------------------------------------------------------------
# KONFIGURASI HALAMAN
# ------------------------------------------------------------------
st.set_page_config(
    page_title="Agentic Plant Doctor 🌱",
    page_icon="🌱",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------
# STYLE TAMBAHAN (mempercantik blockquote & card ala UI/UX pertanian)
# ------------------------------------------------------------------
st.markdown(
    """
    <style>
    blockquote {
        background-color: rgba(46, 139, 87, 0.08);
        border-left: 4px solid #2E8B57;
        padding: 0.6rem 1rem;
        border-radius: 6px;
    }
    .stChatMessage { border-radius: 12px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------
# SIDEBAR - KONFIGURASI API KEY & PENGATURAN AGENT
# ------------------------------------------------------------------
with st.sidebar:
    st.title("⚙️ Konfigurasi Agent")
    st.caption("API Key disimpan hanya selama sesi berjalan (tidak disimpan permanen).")

    groq_api_key = st.text_input(
        "🔑 Groq API Key",
        type="password",
        value=st.secrets.get("GROQ_API_KEY", "") if hasattr(st, "secrets") else "",
        help="Dipakai oleh Diagnosis Agent (Llama 3.3 70B via Groq).",
    )
    gemini_api_key = st.text_input(
        "🔑 Google Gemini API Key",
        type="password",
        value=st.secrets.get("GEMINI_API_KEY", "") if hasattr(st, "secrets") else "",
        help="Dipakai oleh Vision Agent (Gemini) untuk menganalisis foto tanaman.",
    )

    st.divider()
    groq_model = st.selectbox(
        "Model Diagnosis Agent (Groq)",
        ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "gemma2-9b-it"],
        index=0,
    )
    gemini_model_name = st.selectbox(
        "Model Vision Agent (Gemini)",
        ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-1.5-pro"],
        index=0,
        help="Jika sering kena 'kuota habis', coba pilih gemini-1.5-flash-8b (limit lebih longgar).",
    )

    st.divider()
    if st.button("🗑️ Hapus Riwayat Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.caption(
        "**Arsitektur Agentic:**\n\n"
        "🖼️ Vision Agent (Gemini) → mengekstrak gejala visual dari foto\n\n"
        "🩺 Diagnosis Agent (Groq) → menyusun Kartu Diagnosis final"
    )

# ------------------------------------------------------------------
# STATE
# ------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []  # list of dict: role, content, image(optional)

# ------------------------------------------------------------------
# AGENT 1: VISION AGENT (GEMINI)
# ------------------------------------------------------------------
def run_vision_agent(image: Image.Image, api_key: str, model_name: str) -> str:
    """
    Menganalisis foto tanaman secara objektif menggunakan Gemini.
    Dilengkapi retry dengan exponential backoff, dan fallback otomatis
    ke model Gemini yang lebih ringan jika model utama kena rate-limit/kuota habis.
    """
    import google.generativeai as genai

    genai.configure(api_key=api_key)

    # susun urutan model yang dicoba: model pilihan user dulu, baru fallback lainnya
    models_to_try = [model_name] + [m for m in GEMINI_FALLBACK_CHAIN if m != model_name]

    last_error = None
    for model_candidate in models_to_try:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                model = genai.GenerativeModel(
                    model_name=model_candidate,
                    system_instruction=VISION_AGENT_PROMPT,
                )
                response = model.generate_content(
                    [image, "Amati dan laporkan kondisi visual tanaman pada gambar ini."]
                )
                return response.text.strip()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if _is_rate_limit_error(exc):
                    if attempt < MAX_RETRIES:
                        wait_s = BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
                        st.toast(
                            f"⏳ Kuota/rate-limit Gemini ({model_candidate}) tercapai. "
                            f"Coba lagi dalam {wait_s}s (percobaan {attempt}/{MAX_RETRIES})...",
                            icon="⏳",
                        )
                        time.sleep(wait_s)
                        continue
                    else:
                        # habis percobaan untuk model ini -> lanjut ke model fallback berikutnya
                        st.toast(
                            f"🔁 Model {model_candidate} masih kena limit, "
                            f"beralih ke model cadangan...",
                            icon="🔁",
                        )
                        break
                else:
                    # error selain rate-limit -> langsung lempar, tidak perlu fallback
                    raise

    # semua model & percobaan gagal karena rate-limit/kuota
    raise RuntimeError(
        "QUOTA_EXHAUSTED: Semua model Gemini yang dicoba mengalami rate-limit/kuota habis. "
        f"Detail error terakhir: {last_error}"
    )


# ------------------------------------------------------------------
# AGENT 2: DIAGNOSIS AGENT (GROQ)
# ------------------------------------------------------------------
def run_diagnosis_agent(
    user_text: str,
    vision_result: str | None,
    api_key: str,
    model_name: str,
    history: list,
) -> str:
    """
    Menyusun Kartu Diagnosis final berdasarkan gejala teks + hasil vision agent.
    Dilengkapi retry dengan exponential backoff, dan fallback otomatis
    ke model Groq lain jika model utama kena rate-limit/kuota habis.
    """
    from groq import Groq

    client = Groq(api_key=api_key)

    # --- Orchestrator: gabungkan konteks gejala ---
    combined_context = ""
    if user_text:
        combined_context += f"Keterangan/gejala dari pengguna:\n{user_text}\n\n"
    if vision_result:
        combined_context += (
            f"Hasil observasi visual dari Vision Agent (Gemini) terhadap foto tanaman:\n"
            f"{vision_result}\n\n"
        )
    if not combined_context:
        combined_context = "Pengguna belum memberikan gejala spesifik."

    messages = [{"role": "system", "content": DIAGNOSIS_AGENT_PROMPT}]

    # sertakan riwayat percakapan sebelumnya (khusus teks) agar Agent punya konteks lanjutan
    for m in history[-6:]:
        if m["role"] in ("user", "assistant"):
            messages.append({"role": m["role"], "content": m["content"]})

    messages.append({"role": "user", "content": combined_context})

    models_to_try = [model_name] + [m for m in GROQ_FALLBACK_CHAIN if m != model_name]

    last_error = None
    for model_candidate in models_to_try:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                completion = client.chat.completions.create(
                    model=model_candidate,
                    messages=messages,
                    temperature=0.4,
                    max_tokens=1800,
                )
                return completion.choices[0].message.content.strip()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if _is_rate_limit_error(exc):
                    if attempt < MAX_RETRIES:
                        wait_s = BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
                        st.toast(
                            f"⏳ Kuota/rate-limit Groq ({model_candidate}) tercapai. "
                            f"Coba lagi dalam {wait_s}s (percobaan {attempt}/{MAX_RETRIES})...",
                            icon="⏳",
                        )
                        time.sleep(wait_s)
                        continue
                    else:
                        st.toast(
                            f"🔁 Model {model_candidate} masih kena limit, "
                            f"beralih ke model cadangan...",
                            icon="🔁",
                        )
                        break
                else:
                    raise

    raise RuntimeError(
        "QUOTA_EXHAUSTED: Semua model Groq yang dicoba mengalami rate-limit/kuota habis. "
        f"Detail error terakhir: {last_error}"
    )


# ------------------------------------------------------------------
# ORCHESTRATOR
# ------------------------------------------------------------------
def orchestrate(user_text, image, groq_key, gemini_key, groq_model, gemini_model, history):
    vision_result = None

    if image is not None:
        if not gemini_key:
            st.error("⚠️ Mohon isi Gemini API Key di sidebar untuk menganalisis gambar.")
            return None
        try:
            with st.status("🖼️ Vision Agent (Gemini) sedang mengamati gambar...", expanded=False):
                vision_result = run_vision_agent(image, gemini_key, gemini_model)
        except Exception as exc:  # noqa: BLE001
            if _is_rate_limit_error(exc):
                st.error(
                    "🚫 **Kuota Gemini API habis** (Resource Exhausted).\n\n"
                    "Kemungkinan penyebab:\n"
                    "- Batas gratis Gemini API (per menit/hari) sudah tercapai\n"
                    "- Terlalu banyak request dalam waktu singkat\n\n"
                    "**Solusi:**\n"
                    "- Tunggu beberapa saat lalu coba lagi\n"
                    "- Cek kuota di https://aistudio.google.com/app/apikey\n"
                    "- Atau lanjutkan tanpa foto — ketik gejala dalam bentuk teks saja, "
                    "Diagnosis Agent (Groq) tetap bisa bekerja tanpa Vision Agent."
                )
            else:
                st.error(f"❌ Vision Agent (Gemini) mengalami error: {exc}")
            return None

    if not groq_key:
        st.error("⚠️ Mohon isi Groq API Key di sidebar untuk menyusun diagnosis.")
        return None

    try:
        with st.status("🩺 Diagnosis Agent (Groq) sedang menyusun Kartu Diagnosis...", expanded=False):
            final_result = run_diagnosis_agent(
                user_text, vision_result, groq_key, groq_model, history
            )
        return final_result
    except Exception as exc:  # noqa: BLE001
        if _is_rate_limit_error(exc):
            st.error(
                "🚫 **Kuota Groq API habis** (Rate Limit / Resource Exhausted).\n\n"
                "**Solusi:**\n"
                "- Tunggu beberapa saat lalu coba lagi\n"
                "- Cek kuota di https://console.groq.com/settings/limits\n"
                "- Coba ganti model di sidebar (misal ke `llama-3.1-8b-instant`)"
            )
        else:
            st.error(f"❌ Diagnosis Agent (Groq) mengalami error: {exc}")
        return None


# ------------------------------------------------------------------
# HEADER
# ------------------------------------------------------------------
st.title("🌱 Agentic Plant Doctor")
st.caption(
    "Konsultasi penyakit tanaman dengan 2 AI Agent yang saling berkolaborasi: "
    "**Vision Agent (Gemini)** 🖼️ + **Diagnosis Agent (Groq/Llama)** 🩺"
)
st.divider()

# ------------------------------------------------------------------
# RENDER RIWAYAT CHAT
# ------------------------------------------------------------------
for msg in st.session_state.messages:
    avatar = "🧑‍🌾" if msg["role"] == "user" else "🌱"
    with st.chat_message(msg["role"], avatar=avatar):
        if msg.get("image_bytes"):
            st.image(msg["image_bytes"], width=280)
        st.markdown(msg["content"])

# ------------------------------------------------------------------
# INPUT AREA
# ------------------------------------------------------------------
uploaded_image = st.file_uploader(
    "📷 Unggah foto tanaman/daun/buah yang bergejala (opsional)",
    type=["jpg", "jpeg", "png"],
)

user_prompt = st.chat_input("Ceritakan gejala tanaman Anda, atau kirim saja fotonya...")

if user_prompt is not None:
    image_obj = None
    image_bytes_for_display = None

    if uploaded_image is not None:
        image_bytes_for_display = uploaded_image.getvalue()
        image_obj = Image.open(io.BytesIO(image_bytes_for_display)).convert("RGB")

    # tampilkan pesan user
    with st.chat_message("user", avatar="🧑‍🌾"):
        if image_bytes_for_display:
            st.image(image_bytes_for_display, width=280)
        st.markdown(user_prompt if user_prompt else "*(mengirim foto tanpa keterangan)*")

    st.session_state.messages.append(
        {
            "role": "user",
            "content": user_prompt if user_prompt else "(mengirim foto tanpa keterangan)",
            "image_bytes": image_bytes_for_display,
        }
    )

    # jalankan orkestrasi agent
    with st.chat_message("assistant", avatar="🌱"):
        result = orchestrate(
            user_text=user_prompt,
            image=image_obj,
            groq_key=groq_api_key,
            gemini_key=gemini_api_key,
            groq_model=groq_model,
            gemini_model=gemini_model_name,
            history=st.session_state.messages,
        )
        if result:
            st.markdown(result)
            st.session_state.messages.append(
                {"role": "assistant", "content": result, "image_bytes": None}
            )
        else:
            st.warning("Diagnosis tidak dapat diproses. Periksa kembali API Key di sidebar.")

# ------------------------------------------------------------------
# FOOTER
# ------------------------------------------------------------------
st.divider()
st.caption(
    "⚠️ Disclaimer: Diagnosis dihasilkan oleh AI dan bersifat sebagai referensi awal. "
    "Untuk kasus serangan berat atau bernilai ekonomi tinggi, konsultasikan dengan "
    "Penyuluh Pertanian Lapangan (PPL) atau ahli fitopatologi setempat."
)
