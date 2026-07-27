import streamlit as st
import os
from groq import Groq
from openai import OpenAI
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import re
import edge_tts
import asyncio
import base64
import io
from PIL import Image
import PyPDF2
import csv
from io import StringIO
import hashlib
import easyocr
import requests
import time

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Mi Coach Clara System", page_icon="🧠", layout="wide")
st.title("🧠 Coach Clara System - Tu Estratega de IA")

# --- CONFIGURACIÓN DE FIREBASE ---
if not firebase_admin._apps:
    try:
        firebase_creds = dict(st.secrets["firebase"])
        cred = credentials.Certificate(firebase_creds)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"Error al inicializar Firebase: {e}")
        st.stop()

db = firestore.client()

# --- CONFIGURACIÓN DE APIS ---
GROQ_API_KEY = os.environ.get("GITHUB_TOKEN")
SILICONFLOW_API_KEY = os.environ.get("SILICONFLOW_TOKEN")

if not GROQ_API_KEY:
    st.error("⚠️ Falta la clave de API de Groq en los Secrets.")
    st.stop()

groq_client = Groq(api_key=GROQ_API_KEY)

if SILICONFLOW_API_KEY:
    siliconflow_client = OpenAI(
        api_key=SILICONFLOW_API_KEY,
        base_url="https://api.siliconflow.cn/v1"
    )
else:
    siliconflow_client = None
    st.sidebar.warning("⚠️ No se encontró SILICONFLOW_TOKEN. Usando lista de respaldo de SiliconFlow.")

# --- FUNCIONES PARA OBTENER MODELOS ---
def get_groq_models():
    try:
        url = "https://api.groq.com/openai/v1/models"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            models_data = response.json()
            chat_models = {}
            for model in models_data.get("data", []):
                model_id = model.get("id")
                if model_id and not any(x in model_id for x in ["whisper", "guard", "orpheus", "prompt"]):
                    display_name = model_id
                    for prefix in ["meta-llama/", "openai/", "qwen/", "canopylabs/", "minimaxai/"]:
                        if display_name.startswith(prefix):
                            display_name = display_name[len(prefix):]
                    if len(display_name) > 30:
                        display_name = display_name[:27] + "..."
                    chat_models[f"🟢 {display_name}"] = model_id
            return chat_models
    except Exception as e:
        st.sidebar.warning(f"⚠️ Error al obtener modelos de Groq: {e}")
    return None

def get_siliconflow_models():
    if not SILICONFLOW_API_KEY:
        return None
    try:
        url = "https://api.siliconflow.cn/v1/models"
        headers = {"Authorization": f"Bearer {SILICONFLOW_API_KEY}"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            models_data = response.json()
            chat_models = {}
            for model in models_data.get("data", []):
                model_id = model.get("id")
                if model_id:
                    display_name = model_id
                    if len(display_name) > 35:
                        display_name = display_name[:32] + "..."
                    chat_models[f"🔵 {display_name}"] = model_id
            return chat_models
    except Exception as e:
        st.sidebar.warning(f"⚠️ Error al obtener modelos de SiliconFlow: {e}")
    return None

# --- VOICES DICTIONARY ---
VOICES = {
    "España - Elvira (femenino)": "es-ES-ElviraNeural",
    "España - Álvaro (masculino)": "es-ES-AlvaroNeural",
    "México - Dalia (femenino)": "es-MX-DaliaNeural",
    "México - Jorge (masculino)": "es-MX-JorgeNeural",
    "Argentina - Elena (femenino)": "es-AR-ElenaNeural",
    "Bolivia - Marcelo (masculino)": "es-BO-MarceloNeural",
    "Chile - Catalina (femenino)": "es-CL-CatalinaNeural",
    "Colombia - Gonzalo (masculino)": "es-CO-GonzaloNeural",
    "Costa Rica - Juan (masculino)": "es-CR-JuanNeural",
    "Cuba - Belkys (femenino)": "es-CU-BelkysNeural",
    "República Dominicana - Emilio (masculino)": "es-DO-EmilioNeural",
    "Ecuador - Andrea (femenino)": "es-EC-AndreaNeural",
    "Guatemala - Andrés (masculino)": "es-GT-AndresNeural",
    "Honduras - Carlos (masculino)": "es-HN-CarlosNeural",
    "Nicaragua - Federico (masculino)": "es-NI-FedericoNeural",
    "Panamá - Margarita (femenino)": "es-PA-MargaritaNeural",
    "Perú - Camila (femenino)": "es-PE-CamilaNeural",
    "Puerto Rico - Karina (femenino)": "es-PR-KarinaNeural",
    "Paraguay - Tania (femenino)": "es-PY-TaniaNeural",
    "El Salvador - Lorena (femenino)": "es-SV-LorenaNeural",
    "EE.UU. - Alonso (masculino)": "es-US-AlonsoNeural",
    "Uruguay - Mateo (masculino)": "es-UY-MateoNeural",
    "Venezuela - Paola (femenino)": "es-VE-PaolaNeural",
}

# --- OBTENER MODELOS DINÁMICOS ---
groq_models = get_groq_models()
siliconflow_models = get_siliconflow_models()

# --- LISTA DE RESPALDO SIEMPRE INCLUIDA ---
MODELS = {
    # 🟢 Groq (respaldo)
    "🟢 Llama 3.3 70B": "llama-3.3-70b-versatile",
    "🟢 Llama 3.1 8B": "llama-3.1-8b-instant",
    "🟢 GPT-OSS 120B": "openai/gpt-oss-120b",
    "🟢 GPT-OSS 20B": "openai/gpt-oss-20b",
    "🟢 Qwen 3.6 27B": "qwen/qwen3.6-27b",
    "🟢 Groq Compound": "groq/compound",
    "🟢 Groq Compound Mini": "groq/compound-mini",
    "🟢 Mixtral 8x7B": "mixtral-8x7b-32768",

    # 🔵 SiliconFlow (respaldo - modelos top)
    "🔵 DeepSeek-V4-Pro (1.6T MoE)": "deepseek-ai/DeepSeek-V4-Pro",
    "🔵 DeepSeek-V4-Flash (284B)": "deepseek-ai/DeepSeek-V4-Flash",
    "🔵 Kimi-K3 (2.8T)": "moonshotai/Kimi-K3",
    "🔵 Kimi-K2.7-Code (1T)": "moonshotai/Kimi-K2.7-Code",
    "🔵 GLM-5.2 (744B)": "zai-org/GLM-5.2",
    "🔵 Qwen3.6-35B-A3B (MoE)": "Qwen/Qwen3.6-35B-A3B",
    "🔵 Qwen3.6-27B (multimodal)": "Qwen/Qwen3.6-27B",
    "🔵 Gemma-4-31B-it (Google)": "google/gemma-4-31B-it",
    "🔵 DeepSeek-V3.2 (685B)": "deepseek-ai/DeepSeek-V3.2",
    "🔵 MiniMax-M3 (1M ctx)": "MiniMaxAI/MiniMax-M3",
    "🔵 Qwen3.5-397B-A17B": "Qwen/Qwen3.5-397B-A17B",
    "🔵 Qwen3.5-122B-A10B": "Qwen/Qwen3.5-122B-A10B",
    "🔵 Step-3.5-Flash": "stepfun-ai/Step-3.5-Flash",
    "🔵 Nex-N2-Pro": "nex-agi/Nex-N2-Pro",
    "🔵 Hy3 (Tencent)": "tencent/Hy3",
    "🔵 LongCat-2.0": "meituan-longcat/LongCat-2.0",
    "🔵 DeepSeek-V3.1-Terminus": "deepseek-ai/DeepSeek-V3.1-Terminus",
    "🔵 DeepSeek-R1": "deepseek-ai/DeepSeek-R1",
    "🔵 Qwen3-32B": "Qwen/Qwen3-32B",
    "🔵 Qwen3-14B": "Qwen/Qwen3-14B",
    "🔵 Qwen3-8B": "Qwen/Qwen3-8B",
}

# Añadir modelos dinámicos (sobrescriben si hay duplicados)
if groq_models:
    MODELS.update(groq_models)
if siliconflow_models:
    MODELS.update(siliconflow_models)

# --- FUNCIONES FIREBASE, TTS, OCR, DIVISIÓN Y PROMPT ---
# (Mantén el resto de las funciones igual que en el código anterior)
# Para ahorrar espacio, no repito todo, pero asegúrate de que las funciones
# load_chat_history, save_chat_history, extract_name, text_to_speech_async,
# text_to_speech, get_ocr_reader, process_uploaded_file, split_text_into_chunks,
# process_long_text_with_ia, get_system_prompt estén presentes.

# --- INICIALIZAR ESTADO DE SESIÓN ---
if "messages" not in st.session_state:
    historial, nombre_guardado = load_chat_history()
    st.session_state.messages = historial
    st.session_state.user_name = nombre_guardado if nombre_guardado else None

# --- BARRA LATERAL ---
st.sidebar.title("⚙️ Configuración")

# Selector de Voz
st.sidebar.markdown("### 🎤 Voz")
voice_options = sorted(VOICES.keys())
if "selected_voice" not in st.session_state:
    st.session_state.selected_voice = "México - Dalia (femenino)"
selected_voice_label = st.sidebar.selectbox(
    "Elige una voz",
    options=voice_options,
    index=voice_options.index(st.session_state.selected_voice)
)
st.session_state.selected_voice = selected_voice_label
st.sidebar.markdown(f"**Voz actual:** {selected_voice_label}")

st.sidebar.markdown("---")

# Selector de Modelo
st.sidebar.markdown("### 🤖 Modelo de IA")
model_options = sorted(MODELS.keys())
if "selected_model_label" not in st.session_state:
    st.session_state.selected_model_label = model_options[0]

selected_model_label = st.sidebar.selectbox(
    "Elige el modelo",
    options=model_options,
    index=model_options.index(st.session_state.selected_model_label)
)
st.session_state.selected_model_label = selected_model_label
selected_model_id = MODELS[selected_model_label]

if selected_model_label.startswith("🟢"):
    st.sidebar.info("**Proveedor:** Groq")
elif selected_model_label.startswith("🔵"):
    st.sidebar.info("**Proveedor:** SiliconFlow (respaldo o dinámico)")
else:
    st.sidebar.info("**Proveedor:** Desconocido")

st.sidebar.markdown(f"**Modelo:** `{selected_model_id}`")
st.sidebar.caption(f"📋 {len(MODELS)} modelos disponibles (Groq + SiliconFlow)")

# --- MOSTRAR HISTORIAL Y ENTRADA DE USUARIO ---
# (El resto del código de visualización y manejo de entrada del usuario va aquí,
# tal como estaba antes. Asegúrate de incluirlo completo.)

# --- FIN ---
