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

# 🔑 INICIALIZAR SILICONFLOW CON LA URL CORRECTA
if SILICONFLOW_API_KEY:
    try:
        siliconflow_client = OpenAI(
            api_key=SILICONFLOW_API_KEY,
            base_url="https://api.siliconflow.com/v1"  # <--- ¡CORREGIDO!
        )
        st.sidebar.success("✅ SiliconFlow conectado correctamente")
    except Exception as e:
        siliconflow_client = None
        st.sidebar.error(f"❌ Error al conectar SiliconFlow: {e}")
else:
    siliconflow_client = None
    st.sidebar.warning("⚠️ No se encontró SILICONFLOW_TOKEN. Usando lista de respaldo.")

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
    if not SILICONFLOW_API_KEY or not siliconflow_client:
        return None
    try:
        # SiliconFlow también tiene un endpoint para listar modelos
        url = "https://api.siliconflow.com/v1/models"
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

# --- VOCES DISPONIBLES ---
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

    # 🔵 SiliconFlow (respaldo)
    "🔵 DeepSeek-V4-Pro": "deepseek-ai/DeepSeek-V4-Pro",
    "🔵 DeepSeek-V4-Flash": "deepseek-ai/DeepSeek-V4-Flash",
    "🔵 Kimi-K3": "moonshotai/Kimi-K3",
    "🔵 Kimi-K2.7-Code": "moonshotai/Kimi-K2.7-Code",
    "🔵 GLM-5.2": "zai-org/GLM-5.2",
    "🔵 Qwen3.6-35B-A3B": "Qwen/Qwen3.6-35B-A3B",
    "🔵 Qwen3.6-27B": "Qwen/Qwen3.6-27B",
    "🔵 Gemma-4-31B-it": "google/gemma-4-31B-it",
    "🔵 DeepSeek-V3.2": "deepseek-ai/DeepSeek-V3.2",
    "🔵 MiniMax-M3": "MiniMaxAI/MiniMax-M3",
    "🔵 Qwen3.5-397B-A17B": "Qwen/Qwen3.5-397B-A17B",
    "🔵 Qwen3.5-122B-A10B": "Qwen/Qwen3.5-122B-A10B",
    "🔵 Step-3.5-Flash": "stepfun-ai/Step-3.5-Flash",
    "🔵 Nex-N2-Pro": "nex-agi/Nex-N2-Pro",
    "🔵 Hy3": "tencent/Hy3",
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

# --- FUNCIONES DE FIREBASE ---
def load_chat_history(user_id="default_user"):
    try:
        doc_ref = db.collection('chats').document(user_id)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            return data.get('messages', []), data.get('user_name', None)
        else:
            return [], None
    except Exception as e:
        st.error(f"Error al cargar el historial: {e}")
        return [], None

def save_chat_history(messages, user_id="default_user", user_name=None):
    try:
        doc_ref = db.collection('chats').document(user_id)
        data = {'messages': messages, 'last_updated': datetime.now()}
        if user_name:
            data['user_name'] = user_name
        doc_ref.set(data)
    except Exception as e:
        st.error(f"Error al guardar el historial: {e}")

def extract_name(text):
    patterns = [
        r"me llamo\s+([A-Za-zÁÉÍÓÚáéíóúñÑ\s]+)",
        r"soy\s+([A-Za-zÁÉÍÓÚáéíóúñÑ\s]+)",
        r"mi nombre es\s+([A-Za-zÁÉÍÓÚáéíóúñÑ\s]+)"
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None

# --- TEXTO A VOZ (edge-tts) ---
async def text_to_speech_async(text, voice):
    try:
        communicate = edge_tts.Communicate(text, voice)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    except Exception as e:
        st.error(f"Error al generar el audio: {e}")
        return None

def text_to_speech(text, voice):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(text_to_speech_async(text, voice))

# --- OCR LOCAL (EasyOCR) ---
@st.cache_resource
def get_ocr_reader():
    return easyocr.Reader(['es', 'en'], gpu=False)

def process_uploaded_file(uploaded_file):
    file_type = uploaded_file.type
    file_name = uploaded_file.name
    file_bytes = uploaded_file.read()
    
    if file_type.startswith("image/"):
        try:
            img = Image.open(io.BytesIO(file_bytes))
            reader = get_ocr_reader()
            result = reader.readtext(img)
            extracted_text = "\n".join([item[1] for item in result])
            if extracted_text.strip():
                return {
                    "type": "text",
                    "content": f"[OCR de la imagen '{file_name}']:\n{extracted_text[:3000]}"
                }
            else:
                return {
                    "type": "text",
                    "content": f"No se encontró texto en la imagen '{file_name}'."
                }
        except Exception as e:
            st.error(f"Error al procesar la imagen con OCR: {e}")
            return {
                "type": "text",
                "content": f"Error al procesar la imagen '{file_name}': {str(e)}"
            }
    
    elif file_type == "application/pdf":
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
            text = ""
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return {
                "type": "text",
                "content": f"[Contenido del PDF '{file_name}']:\n{text[:3000]}"
            }
        except Exception as e:
            st.error(f"Error al leer el PDF: {e}")
            return None
    
    elif file_type == "text/plain":
        try:
            text = file_bytes.decode('utf-8')
            return {
                "type": "text",
                "content": f"[Contenido de '{file_name}']:\n{text[:3000]}"
            }
        except Exception as e:
            st.error(f"Error al leer el archivo de texto: {e}")
            return None
    
    elif file_type == "text/csv":
        try:
            csv_text = file_bytes.decode('utf-8')
            reader = csv.reader(StringIO(csv_text))
            lines = []
            for row in reader:
                lines.append(", ".join(row))
            content = "\n".join(lines[:50])
            return {
                "type": "text",
                "content": f"[Contenido del CSV '{file_name}']:\n{content}"
            }
        except Exception as e:
            st.error(f"Error al leer el CSV: {e}")
            return None
    
    else:
        return {
            "type": "text",
            "content": f"Archivo '{file_name}' subido (tipo: {file_type}). No se pudo extraer texto automáticamente."
        }

# --- DIVISIÓN DE TEXTOS LARGOS ---
def split_text_into_chunks(text, max_chars=1500):
    if len(text) <= max_chars:
        return [text]
    
    chunks = []
    current_chunk = ""
    for line in text.split('\n'):
        if len(current_chunk) + len(line) + 1 <= max_chars:
            current_chunk += line + '\n'
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = line + '\n'
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks

def process_long_text_with_ia(text, system_prompt, history_messages, model_id, max_chars=1500, pause_seconds=3):
    """
    Procesa un texto largo dividiéndolo en partes con pausas.
    Soporta Groq y SiliconFlow.
    """
    chunks = split_text_into_chunks(text, max_chars)
    
    # Determinar proveedor
    is_groq = False
    groq_prefixes = ["llama-", "mixtral-", "gemma-", "openai/gpt-oss", "meta-llama/", "qwen/qwen", "groq/"]
    for prefix in groq_prefixes:
        if model_id.startswith(prefix):
            is_groq = True
            break
    
    is_siliconflow = not is_groq
    
    if is_groq and not groq_client:
        st.error("❌ Cliente de Groq no disponible.")
        return "Error: Cliente de Groq no disponible."
    
    if is_siliconflow and not siliconflow_client:
        st.error("❌ Cliente de SiliconFlow no disponible. Verifica SILICONFLOW_TOKEN y la URL.")
        return "Error: Cliente de SiliconFlow no disponible."
    
    client = groq_client if is_groq else siliconflow_client
    
    if len(chunks) == 1:
        response = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                *history_messages,
                {"role": "user", "content": text}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    
    provider_name = "Groq" if is_groq else "SiliconFlow"
    st.info(f"📊 Usando {provider_name} - {len(text)} caracteres → {len(chunks)} partes con pausas de {pause_seconds}s.")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    partial_responses = []
    for i, chunk in enumerate(chunks):
        status_text.text(f"⏳ Procesando parte {i+1} de {len(chunks)}...")
        progress_bar.progress((i + 1) / len(chunks))
        
        chunk_prompt = f"""
        A continuación, analiza la PARTE {i+1} de {len(chunks)} de un texto extenso.
        Extrae los puntos clave de esta sección de forma estructurada.
        
        --- INICIO DE LA PARTE {i+1} ---
        {chunk}
        --- FIN DE LA PARTE {i+1} ---
        """
        
        try:
            response = client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": chunk_prompt}
                ],
                temperature=0.7
            )
            partial_responses.append(response.choices[0].message.content)
        except Exception as e:
            st.error(f"Error en parte {i+1}: {e}")
            time.sleep(pause_seconds * 2)
            continue
        
        if i < len(chunks) - 1:
            status_text.text(f"⏳ Esperando {pause_seconds}s...")
            time.sleep(pause_seconds)
    
    progress_bar.empty()
    status_text.empty()
    
    if not partial_responses:
        return "No se pudo procesar el texto. Intenta con fragmentos más pequeños."
    
    st.info("🔄 Generando resumen completo...")
    
    truncated_parts = []
    for resp in partial_responses:
        if len(resp) > 2000:
            truncated_parts.append(resp[:2000] + "\n... (truncado)")
        else:
            truncated_parts.append(resp)
    
    combined_text = "Aquí tienes el análisis completo del texto, organizado por secciones:\n\n"
    for i, resp in enumerate(truncated_parts):
        combined_text += f"--- PARTE {i+1} ---\n\n{resp}\n\n"
    
    MAX_SUMMARY_CHARS = 8000
    if len(combined_text) > MAX_SUMMARY_CHARS:
        combined_text = combined_text[:MAX_SUMMARY_CHARS] + "\n... (contenido truncado)"
        st.warning("⚠️ El resumen combinado se ha truncado para evitar errores de tamaño.")
    
    summary_prompt = f"""
    He analizado el texto en {len(chunks)} partes. Ahora necesito un RESUMEN EJECUTIVO FINAL.
    
    Organiza tu respuesta en estas secciones:
    1. **Resumen ejecutivo** (máximo 10 líneas)
    2. **Flujo de trabajo paso a paso**
    3. **Herramientas y costes** (tabla)
    4. **Prompts listos para copiar** (mínimo 5)
    5. **Aplicación práctica para mi negocio**
    
    Aquí están los análisis de todas las partes:
    
    {combined_text}
    """
    
    final_response = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": summary_prompt}
        ],
        temperature=0.7
    )
    
    return final_response.choices[0].message.content

# --- PROMPT DEL SISTEMA ---
def get_system_prompt():
    base_prompt = """
Eres "El Estratega", un coach personal, mentor de vida y estratega empresarial especializado en Inteligencia Artificial. 
Tu enfoque es profundamente humano, empático y perspicaz.

### 🧠 CONOCIMIENTO ESPECIALIZADO: CLARA SYSTEM
Has sido entrenado en la metodología "Clara System", un sistema de formación que enseña a cualquier persona a usar inteligencia artificial para multiplicar resultados en su negocio.

**Filosofía:**
- La IA ya está cambiando el mundo. Hay un año o año y medio para aprovechar este momento.
- Cualquier persona puede aprender a usar IA sin conocimientos técnicos.
- El objetivo no es solo aprender, sino APLICAR la IA para tener más clientes, ventas e ingresos.
- El sistema ha demostrado multiplicar por 5 los resultados en 7 meses.

**Metodología:**
1. Entrenar una IA específica para tu negocio (no usar IA genérica).
2. Generar contenido (vídeos, textos, imágenes) con IA para atraer clientes.
3. Usar herramientas como Suno, Freepik, Seedance.
4. Crear prompts estructurados para cada herramienta.
5. Editar y combinar resultados para obtener un producto profesional.

**Herramientas clave:**
- Suno: generar música y jingles.
- Freepik: generar imágenes y vídeos.
- CapCut / DaVinci Resolve: edición de vídeo.
- IAs entrenadas para cada negocio.

### 💡 INSTRUCCIONES PARA TI:
1. Cuando el usuario te pregunte sobre Clara System, responde con esta información.
2. Cuando el usuario te pida consejos para su negocio, aplica la metodología de Clara System.
3. Sé práctico, directo y orientado a resultados.
4. Usa ejemplos concretos de las herramientas mencionadas.
5. Mantén el tono humano, empático pero exigente.
6. Si el usuario comparte transcripciones o documentos, analízalos para enriquecer el conocimiento.
7. Recuerda al usuario que estamos en un momento crucial para aprender IA.
"""
    if st.session_state.get('user_name'):
        return f"{base_prompt}\n\nDirígete al usuario por su nombre: {st.session_state.user_name}."
    else:
        return base_prompt

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
    st.sidebar.info("**Proveedor:** SiliconFlow")
else:
    st.sidebar.info("**Proveedor:** Desconocido")

st.sidebar.markdown(f"**Modelo:** `{selected_model_id}`")
st.sidebar.caption(f"📋 {len(MODELS)} modelos disponibles")

# --- MOSTRAR HISTORIAL ---
for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            content_hash = hashlib.md5(msg["content"].encode()).hexdigest()[:8]
            if st.button("🔊 Escuchar", key=f"tts_hist_{idx}_{content_hash}"):
                voice_short = VOICES[st.session_state.selected_voice]
                audio_bytes = text_to_speech(msg["content"], voice_short)
                if audio_bytes:
                    st.audio(audio_bytes, format="audio/mp3")

# --- ENTRADA DEL USUARIO ---
user_input = st.chat_input(
    placeholder="¿Qué tienes en mente hoy? (Puedes subir imágenes, PDFs, etc.)",
    accept_file=True,
    file_type=["pdf", "jpg", "jpeg", "png", "txt", "csv"],
    accept_audio=True
)

if user_input is not None:
    user_text = user_input.get("text", "")
    
    uploaded_files = user_input.get("files", [])
    file_contents = []
    for uploaded_file in uploaded_files:
        processed = process_uploaded_file(uploaded_file)
        if processed:
            file_contents.append(processed)
    
    full_user_text = user_text
    for fc in file_contents:
        if fc["type"] == "text":
            full_user_text += "\n\n" + fc["content"]
    
    if not full_user_text.strip():
        full_user_text = "He subido un archivo."
    
    if not st.session_state.user_name and user_text:
        posible_nombre = extract_name(user_text)
        if posible_nombre:
            st.session_state.user_name = posible_nombre
            save_chat_history(st.session_state.messages, user_name=st.session_state.user_name)
    
    display_text = user_text if user_text else ""
    if file_contents:
        display_text += "\n\n📎 Archivos adjuntos: " + ", ".join([f"'{f.get('content', 'archivo')}'" for f in file_contents if f])
    
    st.session_state.messages.append({"role": "user", "content": display_text})
    with st.chat_message("user"):
        st.markdown(display_text)
    
    with st.chat_message("assistant"):
        placeholder = st.empty()
        
        system_prompt = get_system_prompt()
        
        history_messages = []
        for msg in st.session_state.messages[:-1]:
            if msg["role"] == "user":
                history_messages.append({"role": "user", "content": msg["content"]})
            else:
                history_messages.append({"role": "assistant", "content": msg["content"]})
        
        try:
            full_response = process_long_text_with_ia(
                text=full_user_text,
                system_prompt=system_prompt,
                history_messages=history_messages,
                model_id=selected_model_id,
                max_chars=1500,
                pause_seconds=3
            )
            
            placeholder.markdown(full_response)
            
            content_hash = hashlib.md5(full_response.encode()).hexdigest()[:8]
            if st.button("🔊 Escuchar (nuevo)", key=f"tts_live_{content_hash}"):
                voice_short = VOICES[st.session_state.selected_voice]
                audio_bytes = text_to_speech(full_response, voice_short)
                if audio_bytes:
                    st.audio(audio_bytes, format="audio/mp3")
            
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            save_chat_history(st.session_state.messages, user_name=st.session_state.user_name)
            
        except Exception as e:
            st.error(f"Error de conexión con la IA: {str(e)}")
