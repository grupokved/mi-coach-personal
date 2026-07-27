import streamlit as st
import os
from groq import Groq
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import re
import base64  # 👈 NUEVO: Para codificar el audio en HTML y reproducirlo

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

# --- FUNCIÓN DE TEXTO A VOZ (TTS) --- 👈 NUEVO BLOQUE
def text_to_speech(text):
    """
    Convierte el texto a voz usando la API de Groq TTS.
    Devuelve los bytes del audio MP3.
    """
    try:
        audio_response = client.audio.speech.create(
            model="tts-1",          # Modelo gratuito de TTS
            voice="onyx",           # Voz masculina (puedes probar "nova", "shimmer", etc.)
            input=text
        )
        return audio_response.content  # Devuelve los bytes del audio
    except Exception as e:
        st.error(f"Error al generar el audio: {e}")
        return None

def get_audio_html(audio_bytes):
    """Genera un reproductor de audio HTML a partir de bytes MP3."""
    if audio_bytes is None:
        return ""
    # Codificar el audio en base64 para incrustarlo en HTML
    b64 = base64.b64encode(audio_bytes).decode()
    return f'<audio controls autoplay style="width: 100%; margin-top: 5px;"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>'
# --- FIN BLOQUE TTS ---

# --- FUNCIONES PARA FIREBASE ---
def load_chat_history(user_id="default_user"):
    """Carga el historial de chat desde Firestore."""
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
    """Guarda el historial de chat en Firestore, incluyendo el nombre del usuario."""
    try:
        doc_ref = db.collection('chats').document(user_id)
        data = {'messages': messages, 'last_updated': datetime.now()}
        if user_name:
            data['user_name'] = user_name
        doc_ref.set(data)
    except Exception as e:
        st.error(f"Error al guardar el historial: {e}")

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

# --- INICIALIZAR EL ESTADO DE LA SESIÓN ---
if "messages" not in st.session_state:
    historial, nombre_guardado = load_chat_history()
    st.session_state.messages = historial
    if nombre_guardado:
        st.session_state.user_name = nombre_guardado
    else:
        st.session_state.user_name = None

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

# --- MOSTRAR EL HISTORIAL ---
for idx, msg in enumerate(st.session_state.messages):  # 👈 NUEVO: Añadimos un índice para cada mensaje
    with st.chat_message(msg["role"]):
        # Si el mensaje es del asistente, añadir un botón de "escuchar"
        if msg["role"] == "assistant":
            # Mostrar el texto del mensaje
            st.markdown(msg["content"])
            
            # Crear un botón con ícono de altavoz para generar audio 👈 NUEVO
            # Usamos una clave única basada en el índice para que cada botón sea independiente
            if st.button("🔊 Escuchar", key=f"tts_{idx}"):
                # Generar el audio
                audio_bytes = text_to_speech(msg["content"])
                if audio_bytes:
                    # Mostrar el reproductor de audio dentro del mismo mensaje
                    st.markdown(get_audio_html(audio_bytes), unsafe_allow_html=True)
        else:
            # Para mensajes del usuario, solo mostramos el texto
            st.markdown(msg["content"])

# --- ENTRADA DEL USUARIO Y RESPUESTA ---
if user_input := st.chat_input(
    placeholder="¿Qué tienes en mente hoy o qué proyecto estás desarrollando?",
    accept_file=True,                # 👈 NUEVO: Permite subir archivos
    file_type=["pdf", "jpg", "png", "txt", "csv", "docx"],  # Tipos de archivo permitidos
    accept_audio=True                # 👈 NUEVO: Permite grabar audio
):
    # 1. Si el usuario no tiene nombre guardado, intentar extraerlo del mensaje
    if not st.session_state.user_name:
        posible_nombre = extract_name(user_input.get("text", ""))  # 👈 MODIFICADO: el input ahora es un dict
        if posible_nombre:
            st.session_state.user_name = posible_nombre
            save_chat_history(st.session_state.messages, user_name=st.session_state.user_name)

    # 2. Obtener el texto del mensaje (si hay archivo o audio, el texto puede estar vacío)
    message_text = user_input.get("text", "")
    # Si no hay texto pero sí archivos, podrías generar un mensaje automático
    if not message_text and user_input.get("files"):
        message_text = "He adjuntado un archivo para que lo analices."
    if not message_text and user_input.get("audio"):
        message_text = "He grabado un audio para que lo transcribas."

    # 3. Añadir mensaje del usuario al estado (solo si hay texto o archivos)
    if message_text or user_input.get("files") or user_input.get("audio"):
        # Aquí puedes procesar los archivos y el audio antes de guardar
        # Por ahora, solo guardamos el texto
        st.session_state.messages.append({"role": "user", "content": message_text})
        with st.chat_message("user"):
            st.markdown(message_text)

        # 4. Preparar la respuesta del asistente
        with st.chat_message("assistant"):
            placeholder = st.empty()
            
            # Estructurar mensajes para la API de Groq
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
                
                # 5. Guardar la respuesta de la IA en el estado
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
                # 6. Guardar el historial completo y el nombre en Firebase
                save_chat_history(st.session_state.messages, user_name=st.session_state.user_name)
                
                # 7. 👈 NUEVO: Generar audio automáticamente después de la respuesta (opcional)
                # Si quieres que el audio se genere automáticamente, descomenta las siguientes líneas:
                # audio_bytes = text_to_speech(full_response)
                # if audio_bytes:
                #     st.markdown(get_audio_html(audio_bytes), unsafe_allow_html=True)
                
            except Exception as e:
                st.error(f"Error de conexión con la IA: {str(e)}")
