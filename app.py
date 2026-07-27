import streamlit as st
import os
from groq import Groq
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

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Mi Coach Personal", page_icon="🧠", layout="wide")
st.title("🧠 Coach Personal e Intermediario Técnico")

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

# --- CONFIGURACIÓN DE GROQ ---
API_KEY = os.environ.get("GITHUB_TOKEN")
if not API_KEY:
    st.error("⚠️ Falta la clave de API de Groq en los Secrets.")
    st.stop()

client = Groq(api_key=API_KEY)

# --- DICCIONARIO DE VOCES DISPONIBLES EN ESPAÑOL ---
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

# --- MODELOS DISPONIBLES ---
MODELS = {
    "GPT-OSS-120B (multimodal)": "openai/gpt-oss-120b",
    "Llama 3.3 70B (rápido)": "llama-3.3-70b-versatile",
}

# --- MODELOS DE OCR (VISIÓN) ---
OCR_MODELS = {
    "Llama 4 Maverick (OCR)": "meta-llama/llama-4-maverick-17b-128e-instruct",
    "Llama 4 Scout (OCR)": "meta-llama/llama-4-scout-17b-16e-instruct",
    "Qwen 3.6 (OCR)": "qwen/qwen3.6-27b",
}

# --- FUNCIONES PARA FIREBASE ---
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

# --- FUNCIÓN DE TEXTO A VOZ (edge-tts) ---
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

# --- FUNCIÓN PARA OCR CON MODELOS DE VISIÓN DE GROQ ---
def ocr_image_with_groq(image_bytes, mime_type, ocr_model):
    """
    Usa un modelo de visión de Groq (Llama 4 Maverick, Scout, etc.) para extraer texto de una imagen.
    """
    try:
        # Codificar la imagen en base64
        encoded = base64.b64encode(image_bytes).decode('utf-8')
        data_url = f"data:{mime_type};base64,{encoded}"
        
        # Llamada al modelo de visión
        completion = client.chat.completions.create(
            model=ocr_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extrae TODO el texto de esta imagen. Devuelve solo el texto extraído, sin comentarios adicionales. Si no hay texto, responde 'No se encontró texto'."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": data_url
                            }
                        }
                    ]
                }
            ],
            temperature=0.1  # Baja temperatura para mayor precisión
        )
        
        extracted_text = completion.choices[0].message.content.strip()
        return extracted_text if extracted_text else "No se encontró texto."
    
    except Exception as e:
        st.error(f"Error en OCR con {ocr_model}: {e}")
        return f"Error al procesar la imagen: {str(e)}"

# --- FUNCIÓN PARA PROCESAR ARCHIVOS SUBIDOS ---
def process_uploaded_file(uploaded_file, ocr_model):
    """Procesa el archivo subido y devuelve el contenido extraído."""
    file_type = uploaded_file.type
    file_name = uploaded_file.name
    file_bytes = uploaded_file.read()
    
    # Imagen: OCR con modelo de visión de Groq
    if file_type.startswith("image/"):
        try:
            extracted_text = ocr_image_with_groq(file_bytes, file_type, ocr_model)
            return {
                "type": "text",
                "content": f"[OCR de la imagen '{file_name}' usando {ocr_model}]:\n{extracted_text[:3000]}"
            }
        except Exception as e:
            st.error(f"Error al procesar la imagen: {e}")
            return {
                "type": "text",
                "content": f"Error al procesar la imagen '{file_name}': {str(e)}"
            }
    
    # PDF: extraer texto con PyPDF2
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
    
    # Archivo de texto plano
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
    
    # CSV
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

# --- GENERAR EL PROMPT DEL SISTEMA ---
def get_system_prompt():
    base_prompt = """
Eres "El Estratega", un coach personal, mentor de vida y estratega empresarial. 
Tu enfoque es profundamente humano, empático y perspicaz.
Escucha de forma activa, cuestiona con preguntas socráticas y ayuda a superar bloqueos mentales o miedos.
No uses clichés motivacionales falsos; sé honesto, directo y analítico.
También sirves como intermediario técnico: cuando el usuario hable de una idea de software o código vago, tradúcela en un PROMPT TÉCNICO PERFECTO, listo para copiar y pegar en Cursor, Copilot o ChatGPT.
Mantén un tono de colega brillante, maduro y leal.
"""
    if st.session_state.get('user_name'):
        return f"{base_prompt}\n\nDirígete al usuario por su nombre: {st.session_state.user_name}."
    else:
        return base_prompt

# --- INICIALIZAR EL ESTADO DE LA SESIÓN ---
if "messages" not in st.session_state:
    historial, nombre_guardado = load_chat_history()
    st.session_state.messages = historial
    st.session_state.user_name = nombre_guardado if nombre_guardado else None

# --- SELECCIONAR VOZ, MODELO DE CHAT Y MODELO DE OCR EN LA BARRA LATERAL ---
st.sidebar.title("⚙️ Configuración")

st.sidebar.markdown("### 🎤 Voz para texto a voz")
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
st.sidebar.markdown("### 🤖 Modelo para el Chat")
model_options = list(MODELS.keys())
if "selected_model" not in st.session_state:
    st.session_state.selected_model = model_options[0]
selected_model_label = st.sidebar.selectbox(
    "Elige el modelo de chat",
    options=model_options,
    index=model_options.index(st.session_state.selected_model)
)
st.session_state.selected_model = selected_model_label
selected_model_id = MODELS[selected_model_label]
st.sidebar.markdown(f"**Chat:** `{selected_model_id}`")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🖼️ Modelo para OCR (imágenes)")
ocr_options = list(OCR_MODELS.keys())
if "selected_ocr_model" not in st.session_state:
    st.session_state.selected_ocr_model = ocr_options[0]  # Llama 4 Maverick por defecto
selected_ocr_label = st.sidebar.selectbox(
    "Elige el modelo de OCR",
    options=ocr_options,
    index=ocr_options.index(st.session_state.selected_ocr_model)
)
st.session_state.selected_ocr_model = selected_ocr_label
selected_ocr_model_id = OCR_MODELS[selected_ocr_label]
st.sidebar.markdown(f"**OCR:** `{selected_ocr_model_id}`")

# --- MOSTRAR EL HISTORIAL CON BOTÓN DE REPRODUCCIÓN ---
for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            content_hash = hashlib.md5(msg["content"].encode()).hexdigest()[:8]
            if st.button("🔊 Escuchar", key=f"tts_{idx}_{content_hash}"):
                voice_short = VOICES[st.session_state.selected_voice]
                audio_bytes = text_to_speech(msg["content"], voice_short)
                if audio_bytes:
                    st.audio(audio_bytes, format="audio/mp3")

# --- ENTRADA DEL USUARIO Y RESPUESTA ---
user_input = st.chat_input(
    placeholder="¿Qué tienes en mente hoy? (Puedes subir imágenes, PDFs, etc.)",
    accept_file=True,
    file_type=["pdf", "jpg", "jpeg", "png", "txt", "csv"],
    accept_audio=True
)

if user_input is not None:
    # 1. Extraer texto del mensaje
    user_text = user_input.get("text", "")
    
    # 2. Procesar archivos adjuntos usando el modelo de OCR seleccionado
    uploaded_files = user_input.get("files", [])
    file_contents = []
    for uploaded_file in uploaded_files:
        processed = process_uploaded_file(uploaded_file, selected_ocr_model_id)
        if processed:
            file_contents.append(processed)
    
    # 3. Construir el mensaje del usuario (SOLO TEXTO, sin imágenes en la API)
    full_user_text = user_text
    for fc in file_contents:
        if fc["type"] == "text":
            full_user_text += "\n\n" + fc["content"]
    
    # Si no hay contenido (solo archivos no procesables), añadir un texto por defecto
    if not full_user_text.strip():
        full_user_text = "He subido un archivo."
    
    # 4. Si el usuario no tiene nombre guardado, intentar extraerlo
    if not st.session_state.user_name and user_text:
        posible_nombre = extract_name(user_text)
        if posible_nombre:
            st.session_state.user_name = posible_nombre
            save_chat_history(st.session_state.messages, user_name=st.session_state.user_name)
    
    # 5. Guardar mensaje del usuario en el estado (para mostrar en el historial)
    display_text = user_text if user_text else ""
    if file_contents:
        display_text += "\n\n📎 Archivos adjuntos: " + ", ".join([f"'{f.get('content', 'archivo')}'" for f in file_contents if f])
    
    st.session_state.messages.append({"role": "user", "content": display_text})
    with st.chat_message("user"):
        st.markdown(display_text)
    
    # 6. Preparar la respuesta del asistente
    with st.chat_message("assistant"):
        placeholder = st.empty()
        
        # Construir los mensajes para la API (TODOS DE TEXTO PLANO)
        system_prompt = get_system_prompt()
        
        # Preparar el historial anterior (solo texto)
        history_messages = []
        for msg in st.session_state.messages[:-1]:  # Excluir el mensaje actual
            if msg["role"] == "user":
                history_messages.append({"role": "user", "content": msg["content"]})
            else:
                history_messages.append({"role": "assistant", "content": msg["content"]})
        
        try:
            # Usar el modelo de chat seleccionado
            response = client.chat.completions.create(
                model=selected_model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    *history_messages,
                    {"role": "user", "content": full_user_text}
                ],
                temperature=0.7
            )
            
            full_response = response.choices[0].message.content
            placeholder.markdown(full_response)
            
            # 7. Guardar la respuesta en el estado
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
            # 8. Guardar en Firebase
            save_chat_history(st.session_state.messages, user_name=st.session_state.user_name)
            
        except Exception as e:
            st.error(f"Error de conexión con la IA: {str(e)}")
