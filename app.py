import streamlit as st
import os
from groq import Groq
import google.generativeai as genai
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
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

if not GROQ_API_KEY:
    st.error("⚠️ Falta la clave de API de Groq en los Secrets.")
    st.stop()

groq_client = Groq(api_key=GROQ_API_KEY)

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_available = True
else:
    gemini_available = False
    st.sidebar.warning("⚠️ No se encontró GEMINI_API_KEY.")

if OPENROUTER_API_KEY:
    openrouter_client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
        default_headers={
            "HTTP-Referer": "https://tu-app.streamlit.app",
            "X-Title": "Mi Coach Clara System",
        }
    )
    st.sidebar.success("✅ OpenRouter conectado")
else:
    openrouter_client = None
    st.sidebar.warning("⚠️ No se encontró OPENROUTER_API_KEY.")

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

def get_gemini_models():
    if not GEMINI_API_KEY:
        return None
    try:
        models = genai.list_models()
        chat_models = {}
        for model in models:
            if "gemini" in model.name and "generateContent" in model.supported_generation_methods:
                model_id = model.name.replace("models/", "")
                display_name = model_id
                if len(display_name) > 30:
                    display_name = display_name[:27] + "..."
                chat_models[f"🔴 {display_name}"] = model_id
        return chat_models if chat_models else None
    except Exception as e:
        st.sidebar.warning(f"⚠️ Error al obtener modelos de Gemini: {e}")
    return None

def get_openrouter_models():
    return {
        "🟣 GPT-4o-mini (gratuito)": "openai/gpt-4o-mini",
        "🟣 Gemini 3.5 Flash (gratuito)": "google/gemini-3.5-flash",
        "🟣 Gemini 3.1 Flash (gratuito)": "google/gemini-3.1-flash",
        "🟣 Mistral 7B (gratuito)": "mistralai/mistral-7b-instruct",
        "🟣 Llama 3.3 70B (gratuito)": "meta-llama/llama-3.3-70b-instruct",
        "🟣 DeepSeek-V3 (gratuito)": "deepseek/deepseek-chat",
        "🟣 Qwen 2.5 72B (gratuito)": "qwen/qwen-2.5-72b-instruct",
        "🟣 GPT-4o (alias)": "~openai/gpt-latest",
    }

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
gemini_models = get_gemini_models()
openrouter_models = get_openrouter_models()

MODELS = {
    "🟢 Llama 3.3 70B": "llama-3.3-70b-versatile",
    "🟢 Llama 3.1 8B": "llama-3.1-8b-instant",
    "🟢 GPT-OSS 120B": "openai/gpt-oss-120b",
    "🟢 GPT-OSS 20B": "openai/gpt-oss-20b",
    "🟢 Qwen 3.6 27B": "qwen/qwen3.6-27b",
    "🟢 Groq Compound": "groq/compound",
    "🟢 Groq Compound Mini": "groq/compound-mini",
    "🟢 Mixtral 8x7B": "mixtral-8x7b-32768",

    "🔴 Gemini 3.5 Flash": "gemini-3.5-flash",
    "🔴 Gemini 3.1 Flash": "gemini-3.1-flash",
    "🔴 Gemini 3.1 Flash-Lite": "gemini-3.1-flash-lite",
    "🔴 Gemini 2.5 Flash": "gemini-2.5-flash",
    "🔴 Gemini 2.5 Pro": "gemini-2.5-pro",
    "🔴 Gemini 2.5 Flash-Lite": "gemini-2.5-flash-lite",

    "🟣 GPT-4o-mini": "openai/gpt-4o-mini",
    "🟣 Gemini 3.5 Flash (OR)": "google/gemini-3.5-flash",
    "🟣 Gemini 3.1 Flash (OR)": "google/gemini-3.1-flash",
    "🟣 Mistral 7B": "mistralai/mistral-7b-instruct",
    "🟣 Llama 3.3 70B (OR)": "meta-llama/llama-3.3-70b-instruct",
    "🟣 DeepSeek-V3": "deepseek/deepseek-chat",
    "🟣 Qwen 2.5 72B": "qwen/qwen-2.5-72b-instruct",
    "🟣 GPT-4o (alias)": "~openai/gpt-latest",
}

if groq_models:
    MODELS.update(groq_models)
if gemini_models:
    MODELS.update(gemini_models)
if openrouter_models:
    MODELS.update(openrouter_models)

# --- FUNCIONES DE MEMORIA Y RESUMEN ---
def get_user_profile(user_id="default_user"):
    """Recupera el perfil del usuario desde Firebase."""
    try:
        doc_ref = db.collection('users').document(user_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
    except Exception as e:
        st.error(f"Error al recuperar perfil: {e}")
    return {}

def save_user_profile(profile, user_id="default_user"):
    """Guarda el perfil del usuario en Firebase."""
    try:
        doc_ref = db.collection('users').document(user_id)
        doc_ref.set(profile, merge=True)
    except Exception as e:
        st.error(f"Error al guardar perfil: {e}")

def get_conversation_summary(user_id="default_user"):
    """Recupera el resumen de la conversación desde Firebase."""
    try:
        doc_ref = db.collection('chats').document(user_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict().get('summary', '')
    except Exception as e:
        st.error(f"Error al recuperar el resumen: {e}")
    return ''

def save_conversation_summary(summary, user_id="default_user"):
    """Guarda el resumen de la conversación en Firebase."""
    try:
        doc_ref = db.collection('chats').document(user_id)
        doc_ref.set({
            'summary': summary,
            'last_updated': datetime.now()
        }, merge=True)
    except Exception as e:
        st.error(f"Error al guardar el resumen: {e}")

def get_chat_history(user_id="default_user"):
    """Recupera el historial de mensajes desde Firebase."""
    try:
        doc_ref = db.collection('chats').document(user_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict().get('messages', [])
    except Exception as e:
        st.error(f"Error al cargar el historial: {e}")
    return []

def save_chat_history(messages, user_id="default_user"):
    """Guarda el historial de mensajes en Firebase."""
    try:
        doc_ref = db.collection('chats').document(user_id)
        doc_ref.set({
            'messages': messages,
            'last_updated': datetime.now()
        }, merge=True)
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

def generate_summary(messages, system_prompt, model_id):
    """Genera un resumen de la conversación usando el modelo actual."""
    if len(messages) < 5:
        return "Conversación breve, sin resumen aún."
    
    is_groq = any(model_id.startswith(p) for p in ["llama-", "mixtral-", "gemma-", "openai/gpt-oss", "meta-llama/", "qwen/qwen", "groq/"])
    is_gemini = "gemini" in model_id
    is_openrouter = not is_groq and not is_gemini
    
    conversation_text = ""
    for msg in messages:
        conversation_text += f"{msg['role']}: {msg['content']}\n"
    
    prompt = f"""
    Genera un resumen ejecutivo de la siguiente conversación.
    El resumen debe ser conciso (máximo 200 palabras) y capturar:
    - El tema principal.
    - Los puntos clave discutidos.
    - Las decisiones o acciones acordadas.
    
    Conversación:
    {conversation_text}
    """
    
    try:
        if is_groq and groq_client:
            response = groq_client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5
            )
            return response.choices[0].message.content
        elif is_gemini and GEMINI_API_KEY:
            model = genai.GenerativeModel(model_id)
            response = model.generate_content(prompt)
            return response.text
        elif is_openrouter and openrouter_client:
            response = openrouter_client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5
            )
            return response.choices[0].message.content
        else:
            return "No se pudo generar resumen: cliente no disponible."
    except Exception as e:
        st.error(f"Error al generar resumen: {e}")
        return "No se pudo generar resumen."

# --- TEXTO A VOZ ---
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

# --- OCR LOCAL ---
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

# --- DIVISIÓN DE TEXTOS ---
def split_text_into_chunks(text, max_chars=800):
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

def call_gemini(model_id, system_prompt, user_text):
    if not GEMINI_API_KEY:
        return "Error: Clave de Gemini no configurada."
    try:
        model = genai.GenerativeModel(
            model_id,
            system_instruction=system_prompt
        )
        response = model.generate_content(user_text)
        return response.text
    except Exception as e:
        return f"Error en Gemini: {str(e)}"

def process_long_text_with_ia(text, system_prompt, history_messages, model_id, max_chars=800, pause_seconds=5):
    """
    Procesa un texto largo dividiéndolo en partes con pausas.
    Soporta Groq, Gemini y OpenRouter.
    """
    is_groq = any(model_id.startswith(p) for p in ["llama-", "mixtral-", "gemma-", "openai/gpt-oss", "meta-llama/", "qwen/qwen", "groq/"])
    is_gemini = "gemini" in model_id
    is_openrouter = not is_groq and not is_gemini

    # --- Groq ---
    if is_groq:
        if not groq_client:
            return "Error: Cliente de Groq no disponible."
        client = groq_client

        chunks = split_text_into_chunks(text, max_chars)
        total_chunks = len(chunks)

        if total_chunks == 1:
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

        st.info(f"📊 Usando Groq - {len(text)} caracteres → {total_chunks} fragmentos de {max_chars} caracteres. Pausa de {pause_seconds}s.")
        progress_bar = st.progress(0)
        status_text = st.empty()

        partial_responses = []
        for i, chunk in enumerate(chunks):
            status_text.text(f"⏳ Procesando fragmento {i+1} de {total_chunks}...")
            progress_bar.progress((i + 1) / total_chunks)

            chunk_prompt = f"""
            A continuación, analiza el fragmento {i+1} de {total_chunks} de un texto extenso.
            Extrae los puntos clave de esta sección de forma estructurada.

            --- INICIO DEL FRAGMENTO {i+1} ---
            {chunk}
            --- FIN DEL FRAGMENTO {i+1} ---
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
                st.error(f"Error en fragmento {i+1}: {e}")
                time.sleep(pause_seconds * 2)
                continue

            if i < total_chunks - 1:
                status_text.text(f"⏳ Esperando {pause_seconds}s...")
                time.sleep(pause_seconds)

        progress_bar.empty()
        status_text.empty()

        if not partial_responses:
            return "No se pudo procesar el texto. Intenta con fragmentos más pequeños."

        st.info("🔄 Generando resumen completo...")
        combined_text = "\n\n".join(partial_responses)
        if len(combined_text) > 8000:
            combined_text = combined_text[:8000] + "\n... (truncado)"
            st.warning("⚠️ El resumen combinado se ha truncado para evitar errores.")

        summary_prompt = f"""
        He analizado el texto en {total_chunks} fragmentos. Ahora necesito un RESUMEN EJECUTIVO FINAL.

        Organiza tu respuesta en estas secciones:
        1. **Resumen ejecutivo** (máximo 10 líneas)
        2. **Flujo de trabajo paso a paso**
        3. **Herramientas y costes** (tabla)
        4. **Prompts listos para copiar** (mínimo 5)
        5. **Aplicación práctica para mi negocio**

        Aquí están los análisis de todos los fragmentos:
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

    # --- Gemini ---
    if is_gemini:
        if not GEMINI_API_KEY:
            return "Error: Cliente de Gemini no disponible."
        if len(text) > 30000:
            chunks = split_text_into_chunks(text, max_chars=8000)
            st.info(f"📊 Usando Gemini - {len(text)} caracteres → {len(chunks)} partes con pausas de {pause_seconds}s.")
            progress_bar = st.progress(0)
            status_text = st.empty()
            partial_responses = []
            for i, chunk in enumerate(chunks):
                status_text.text(f"⏳ Procesando parte {i+1} de {len(chunks)}...")
                progress_bar.progress((i + 1) / len(chunks))
                chunk_prompt = f"""
                A continuación, analiza la PARTE {i+1} de {len(chunks)} de un texto extenso.
                Extrae los puntos clave de esta sección.
                
                --- INICIO DE LA PARTE {i+1} ---
                {chunk}
                --- FIN DE LA PARTE {i+1} ---
                """
                resp = call_gemini(model_id, system_prompt, chunk_prompt)
                partial_responses.append(resp)
                if i < len(chunks) - 1:
                    status_text.text(f"⏳ Esperando {pause_seconds}s...")
                    time.sleep(pause_seconds)
            progress_bar.empty()
            status_text.empty()
            combined = "\n\n".join(partial_responses)
            summary_prompt = f"""
            He analizado el texto en {len(chunks)} partes. Ahora necesito un RESUMEN EJECUTIVO FINAL.
            Organiza tu respuesta en estas secciones:
            1. Resumen ejecutivo (máximo 10 líneas)
            2. Flujo de trabajo paso a paso
            3. Herramientas y costes (tabla)
            4. Prompts listos para copiar (mínimo 5)
            5. Aplicación práctica para mi negocio
            
            Aquí están los análisis de todas las partes:
            {combined}
            """
            return call_gemini(model_id, system_prompt, summary_prompt)
        else:
            return call_gemini(model_id, system_prompt, text)

    # --- OpenRouter ---
    if is_openrouter:
        if not openrouter_client:
            return "Error: Cliente de OpenRouter no disponible."
        client = openrouter_client

        if len(text) > 30000:
            chunks = split_text_into_chunks(text, max_chars=8000)
            st.info(f"📊 Usando OpenRouter - {len(text)} caracteres → {len(chunks)} partes con pausas de {pause_seconds}s.")
            progress_bar = st.progress(0)
            status_text = st.empty()
            partial_responses = []
            for i, chunk in enumerate(chunks):
                status_text.text(f"⏳ Procesando parte {i+1} de {len(chunks)}...")
                progress_bar.progress((i + 1) / len(chunks))
                chunk_prompt = f"""
                A continuación, analiza la PARTE {i+1} de {len(chunks)} de un texto extenso.
                Extrae los puntos clave de esta sección.
                
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
                return "No se pudo procesar el texto."
            combined = "\n\n".join(partial_responses)
            summary_prompt = f"""
            He analizado el texto en {len(chunks)} partes. Ahora necesito un RESUMEN EJECUTIVO FINAL.
            Organiza tu respuesta en estas secciones:
            1. Resumen ejecutivo (máximo 10 líneas)
            2. Flujo de trabajo paso a paso
            3. Herramientas y costes (tabla)
            4. Prompts listos para copiar (mínimo 5)
            5. Aplicación práctica para mi negocio
            
            Aquí están los análisis de todas las partes:
            {combined}
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
        else:
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

    return "Error: No se pudo determinar el proveedor."

# --- PROMPT DEL SISTEMA CON IDENTIDAD ---
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
    # Añadir identidad del usuario si existe
    if st.session_state.get('user_name'):
        return f"{base_prompt}\n\nDirígete al usuario por su nombre: {st.session_state.user_name}."
    else:
        return base_prompt

# --- INICIALIZAR ESTADO DE SESIÓN ---
# Cargar perfil del usuario
user_profile = get_user_profile()
st.session_state.user_name = user_profile.get('name', None)
st.session_state.user_profession = user_profile.get('profession', '')
st.session_state.user_goals = user_profile.get('goals', '')

# Cargar resumen y mensajes
if "messages" not in st.session_state:
    historial = get_chat_history()
    if len(historial) > 15:
        historial = historial[-15:]
    st.session_state.messages = historial
    st.session_state.summary = get_conversation_summary()
    
    # Si no hay resumen y hay mensajes, generar uno
    if not st.session_state.summary and len(st.session_state.messages) > 5:
        st.info("🔄 Generando resumen inicial...")
        # Usar el primer modelo de la lista para el resumen inicial
        temp_model = list(MODELS.keys())[0]
        st.session_state.summary = generate_summary(
            st.session_state.messages,
            get_system_prompt(),
            MODELS[temp_model]
        )
        if st.session_state.summary:
            save_conversation_summary(st.session_state.summary)

# --- BARRA LATERAL ---
st.sidebar.title("⚙️ Configuración")

# Datos del usuario (identidad permanente)
st.sidebar.markdown("### 👤 Tu Identidad")
user_name = st.sidebar.text_input("Tu nombre", value=st.session_state.user_name or "")
if user_name != st.session_state.user_name:
    st.session_state.user_name = user_name
    save_user_profile({"name": user_name})

user_profession = st.sidebar.text_input("Tu profesión", value=st.session_state.user_profession or "")
if user_profession != st.session_state.user_profession:
    st.session_state.user_profession = user_profession
    save_user_profile({"profession": user_profession})

user_goals = st.sidebar.text_area("Tus objetivos", value=st.session_state.user_goals or "")
if user_goals != st.session_state.user_goals:
    st.session_state.user_goals = user_goals
    save_user_profile({"goals": user_goals})

st.sidebar.markdown("---")

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
elif selected_model_label.startswith("🔴"):
    st.sidebar.info("**Proveedor:** Gemini")
elif selected_model_label.startswith("🟣"):
    st.sidebar.info("**Proveedor:** OpenRouter")
else:
    st.sidebar.info("**Proveedor:** Desconocido")

st.sidebar.markdown(f"**Modelo:** `{selected_model_id}`")
st.sidebar.caption(f"📋 {len(MODELS)} modelos disponibles")

st.sidebar.markdown("---")

# 📋 Resumen actual
st.sidebar.markdown("### 📋 Resumen de la conversación")
if st.session_state.summary:
    st.sidebar.text_area("Resumen actual", st.session_state.summary, height=100, key="summary_display")
else:
    st.sidebar.info("Sin resumen aún (necesitas más de 5 mensajes)")

st.sidebar.markdown("---")

# 🗑️ Botón para nuevo espacio de trabajo
if st.sidebar.button("🗑️ Nuevo espacio de trabajo", help="Borra el historial y el resumen, pero mantiene tu identidad"):
    st.session_state.messages = []
    st.session_state.summary = ""
    save_chat_history([])
    save_conversation_summary("")
    st.rerun()

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
    
    # Detectar nombre automáticamente
    if not st.session_state.user_name and user_text:
        posible_nombre = extract_name(user_text)
        if posible_nombre:
            st.session_state.user_name = posible_nombre
            save_user_profile({"name": posible_nombre})
    
    display_text = user_text if user_text else ""
    if file_contents:
        display_text += "\n\n📎 Archivos adjuntos: " + ", ".join([f"'{f.get('content', 'archivo')}'" for f in file_contents if f])
    
    st.session_state.messages.append({"role": "user", "content": display_text})
    with st.chat_message("user"):
        st.markdown(display_text)
    
    with st.chat_message("assistant"):
        placeholder = st.empty()
        
        system_prompt = get_system_prompt()
        
        # --- CONSTRUIR CONTEXTO PARA LA IA (resumen + últimos mensajes) ---
        context_messages = []
        
        # 1. Identidad del usuario (siempre)
        if st.session_state.user_name:
            context_messages.append({
                "role": "system",
                "content": f"El usuario se llama {st.session_state.user_name}. Profesión: {st.session_state.user_profession}. Objetivos: {st.session_state.user_goals}"
            })
        
        # 2. Resumen de la conversación (si existe)
        if st.session_state.summary:
            context_messages.append({
                "role": "system",
                "content": f"Resumen de la conversación anterior: {st.session_state.summary}"
            })
        
        # 3. Últimos 5 mensajes (sin incluir el actual)
        last_messages = st.session_state.messages[-5:] if len(st.session_state.messages) > 5 else st.session_state.messages
        for msg in last_messages:
            context_messages.append(msg)
        
        # 4. Añadir el mensaje actual
        context_messages.append({"role": "user", "content": full_user_text})
        
        try:
            # Llamar a la IA con el contexto reducido
            full_response = process_long_text_with_ia(
                text=full_user_text,  # Se usa para la división de texto largo
                system_prompt=system_prompt,
                history_messages=context_messages,  # Contexto reducido
                model_id=selected_model_id,
                max_chars=800,
                pause_seconds=5
            )
            
            placeholder.markdown(full_response)
            
            content_hash = hashlib.md5(full_response.encode()).hexdigest()[:8]
            if st.button("🔊 Escuchar (nuevo)", key=f"tts_live_{content_hash}"):
                voice_short = VOICES[st.session_state.selected_voice]
                audio_bytes = text_to_speech(full_response, voice_short)
                if audio_bytes:
                    st.audio(audio_bytes, format="audio/mp3")
            
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
            # Guardar historial en Firebase (últimos 20 mensajes máximo)
            if len(st.session_state.messages) > 20:
                st.session_state.messages = st.session_state.messages[-20:]
            save_chat_history(st.session_state.messages)
            
            # Generar resumen cada 8 mensajes
            if len(st.session_state.messages) % 8 == 0 and len(st.session_state.messages) > 5:
                st.info("🔄 Generando resumen de la conversación...")
                new_summary = generate_summary(
                    st.session_state.messages,
                    system_prompt,
                    selected_model_id
                )
                if new_summary and "No se pudo" not in new_summary:
                    st.session_state.summary = new_summary
                    save_conversation_summary(new_summary)
            
        except Exception as e:
            st.error(f"Error de conexión con la IA: {str(e)}")
