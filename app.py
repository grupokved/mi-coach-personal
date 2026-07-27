import streamlit as st
import os
from groq import Groq
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import re
import io
import tempfile
import base64

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Mi Coach Personal", page_icon="🧠", layout="centered")
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

# --- FUNCIONES DE PROCESAMIENTO DE ARCHIVOS (versión simplificada) ---
def process_uploaded_file(uploaded_file):
    """Procesa el archivo subido y devuelve su contenido como texto."""
    file_type = uploaded_file.type
    file_name = uploaded_file.name
    file_bytes = uploaded_file.getvalue()  # Leer el contenido binario
    
    if file_type.startswith("image/"):
        # Para imágenes: usamos una librería OCR o la enviamos a la IA multimodal
        # Por simplicidad, aquí solo devolvemos un mensaje
        return f"[Imagen subida: {file_name}. Usa 'analizar imagen' para procesarla con OCR.]"
    
    elif file_type.startswith("audio/"):
        # Para audio: usamos Whisper de Groq o local
        # Por simplicidad, indicamos que se transcribirá
        return f"[Audio subido: {file_name}. Próximamente se transcribirá.]"
    
    elif file_type == "application/pdf":
        # Para PDF: extraemos texto (necesitarías PyPDF2 o pdfplumber)
        return f"[PDF subido: {file_name}. Extracción de texto disponible.]"
    
    elif file_type == "text/csv":
        # Para CSV: procesar con pandas
        return f"[CSV subido: {file_name}. Análisis de datos disponible.]"
    
    else:
        # Para archivos de texto (txt, md, etc.)
        try:
            text = uploaded_file.read().decode("utf-8")
            return text
        except:
            return f"[Archivo no soportado: {file_name}]"

# --- FUNCIONES DE FIREBASE (sin cambios) ---
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

def get_system_prompt():
    base_prompt = """
Eres "El Estratega", un coach personal, mentor de vida y estratega empresarial. 
Tu enfoque es profundamente humano, empático y perspicaz.
Escucha de forma activa, cuestiona con preguntas socráticas y ayuda a superar bloqueos mentales o miedos.
No uses clichés motivacionales falsos; sé honesto, directo y analítico.
También sirves como intermediario técnico: cuando el usuario hable de una idea de software o código vago, tradúcela en un PROMPT TÉCNICO PERFECTO, listo para copiar y pegar en Cursor, Copilot o ChatGPT.
Mantén un tono de colega brillante, maduro y leal.
"""
    if st.session_state.user_name:
        return f"{base_prompt}\n\nDirígete al usuario por su nombre: {st.session_state.user_name}."
    else:
        return base_prompt

# --- INICIALIZAR EL ESTADO DE LA SESIÓN ---
if "messages" not in st.session_state:
    historial, nombre_guardado = load_chat_history()
    st.session_state.messages = historial
    st.session_state.user_name = nombre_guardado

# --- MOSTRAR EL HISTORIAL ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- NUEVA VERSIÓN DE LA ENTRADA DEL USUARIO CON ARCHIVOS Y AUDIO ---
user_input = st.chat_input(
    placeholder="¿Qué tienes en mente hoy o qué proyecto estás desarrollando?",
    accept_file=True,                # Permite subir archivos
    file_type=["pdf", "jpg", "png", "txt", "csv", "docx", "md"],  # Tipos permitidos
    accept_audio=True                # Permite grabar audio
)

# --- PROCESAR LA ENTRADA ---
if user_input is not None:
    # 1. Extraer el texto del mensaje
    message_text = user_input.get("text", "")
    
    # 2. Procesar archivos adjuntos (si los hay)
    uploaded_files = user_input.get("files", [])
    file_content = ""
    for uploaded_file in uploaded_files:
        processed_text = process_uploaded_file(uploaded_file)
        file_content += f"\n\n--- Archivo adjunto: {uploaded_file.name} ---\n{processed_text}"
    
    # 3. Si hay archivos, añadir su contenido al mensaje del usuario
    if file_content:
        mensaje_completo = f"{message_text}\n\n{file_content}"
    else:
        mensaje_completo = message_text
    
    # 4. Si es audio, podemos transcribirlo (por ahora solo mostramos)
    audio_file = user_input.get("audio")
    if audio_file is not None:
        # Aquí iría la transcripción con Whisper
        mensaje_completo += f"\n\n[Audio grabado: {audio_file.name} - {audio_file.size} bytes]"
    
    # 5. Si el usuario no tiene nombre guardado, intentar extraerlo
    if not st.session_state.user_name:
        posible_nombre = extract_name(mensaje_completo)
        if posible_nombre:
            st.session_state.user_name = posible_nombre
            save_chat_history(st.session_state.messages, user_name=st.session_state.user_name)
    
    # 6. Añadir mensaje del usuario al estado
    st.session_state.messages.append({"role": "user", "content": mensaje_completo})
    with st.chat_message("user"):
        st.markdown(mensaje_completo)
    
    # 7. Preparar la respuesta del asistente
    with st.chat_message("assistant"):
        placeholder = st.empty()
        
        system_prompt = get_system_prompt()
        api_messages = [{"role": "user", "content": system_prompt}]
        api_messages.extend(st.session_state.messages)
        
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=api_messages,
                temperature=0.7
            )
            
            full_response = response.choices[0].message.content
            placeholder.markdown(full_response)
            
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            save_chat_history(st.session_state.messages, user_name=st.session_state.user_name)
            
        except Exception as e:
            st.error(f"Error de conexión con la IA: {str(e)}")
