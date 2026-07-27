import streamlit as st
import os
from groq import Groq
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import re
import edge_tts
import asyncio

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

# --- FUNCIONES PARA FIREBASE ---
def load_chat_history(user_id="default_user"):
    """Carga el historial de chat y el nombre desde Firestore."""
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
    """Guarda el historial y el nombre en Firestore."""
    try:
        doc_ref = db.collection('chats').document(user_id)
        data = {'messages': messages, 'last_updated': datetime.now()}
        if user_name:
            data['user_name'] = user_name
        doc_ref.set(data)
    except Exception as e:
        st.error(f"Error al guardar el historial: {e}")

# --- FUNCIÓN PARA EXTRAER NOMBRE DEL USUARIO ---
def extract_name(text):
    """Intenta extraer un nombre de un mensaje de presentación."""
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

# --- FUNCIÓN DE TEXTO A VOZ (edge-tts en español) ---
async def text_to_speech_async(text, voice="es-ES-ElviraNeural"):
    """Convierte texto a voz usando edge-tts (gratis, sin API key) y devuelve los bytes del audio."""
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

def text_to_speech(text):
    """Función wrapper para llamar a la función asíncrona desde Streamlit."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(text_to_speech_async(text))

# --- GENERAR EL PROMPT DEL SISTEMA DE FORMA DINÁMICA ---
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
    st.session_state.user_name = nombre_guardado if nombre_guardado else None

# --- MOSTRAR EL HISTORIAL CON BOTÓN PARA ESCUCHAR ---
for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        # Si el mensaje es del asistente, añadir botón para escuchar
        if msg["role"] == "assistant":
            # Usamos el índice como clave para el botón (es único)
            if st.button("🔊 Escuchar", key=f"tts_{idx}"):
                audio_bytes = text_to_speech(msg["content"])
                if audio_bytes:
                    st.audio(audio_bytes, format="audio/mp3")

# --- ENTRADA DEL USUARIO Y RESPUESTA (con carga de archivos y audio) ---
user_input = st.chat_input(
    placeholder="¿Qué tienes en mente hoy o qué proyecto estás desarrollando?",
    accept_file=True,                # Permite subir archivos
    file_type=["pdf", "jpg", "png", "txt", "csv", "docx"],  # Tipos permitidos
    accept_audio=True                # Permite grabar audio
)

if user_input:
    # Extraer el texto y los archivos adjuntos
    message_text = user_input.get("text", "")
    uploaded_files = user_input.get("files", [])
    # Si hay audio grabado, estará en user_input.get("audio")
    audio_file = user_input.get("audio")

    # 1. Si el usuario no tiene nombre guardado, intentar extraerlo del mensaje
    if not st.session_state.user_name:
        posible_nombre = extract_name(message_text)
        if posible_nombre:
            st.session_state.user_name = posible_nombre
            save_chat_history(st.session_state.messages, user_name=st.session_state.user_name)

    # 2. Añadir mensaje del usuario al estado
    # Si hay archivos adjuntos, los mostramos como información adicional
    if uploaded_files:
        # Mostrar información de los archivos subidos
        file_info = "\n\n**Archivos adjuntos:**\n"
        for file in uploaded_files:
            file_info += f"- {file.name} ({file.type}, {file.size} bytes)\n"
        # Añadimos esta información al mensaje del usuario (lo verá la IA)
        full_user_message = message_text + file_info
    else:
        full_user_message = message_text

    st.session_state.messages.append({"role": "user", "content": full_user_message})
    with st.chat_message("user"):
        st.markdown(full_user_message)

    # 3. Preparar la respuesta del asistente
    with st.chat_message("assistant"):
        placeholder = st.empty()
        
        # Estructurar mensajes para la API de Groq
        system_prompt = get_system_prompt()
        api_messages = [{"role": "user", "content": system_prompt}]
        api_messages.extend(st.session_state.messages)

        try:
            # Llamada a Groq
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",  # Modelo estable
                messages=api_messages,
                temperature=0.7
            )
            
            full_response = response.choices[0].message.content
            placeholder.markdown(full_response)
            
            # 4. Guardar la respuesta de la IA en el estado
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
            # 5. Guardar el historial completo y el nombre en Firebase
            save_chat_history(st.session_state.messages, user_name=st.session_state.user_name)
            
            # 6. (Opcional) Mostrar el botón "Escuchar" inmediatamente después de la respuesta
            # Para ello, necesitaríamos un botón en el mismo contenedor, pero es más sencillo
            # recargar la página para que aparezca el botón en el historial.
            # Si quieres que aparezca sin recargar, puedes usar st.rerun() al final.
            st.rerun()  # Esto forzará que se muestre el botón para el nuevo mensaje
            
        except Exception as e:
            st.error(f"Error de conexión con la IA: {str(e)}")
