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
    # 🇪🇸 España
    "España - Elvira (femenino)": "es-ES-ElviraNeural",
    "España - Álvaro (masculino)": "es-ES-AlvaroNeural",
    # 🇲🇽 México
    "México - Dalia (femenino)": "es-MX-DaliaNeural",
    "México - Jorge (masculino)": "es-MX-JorgeNeural",
    # 🇦🇷 Argentina
    "Argentina - Elena (femenino)": "es-AR-ElenaNeural",
    # 🇧🇴 Bolivia
    "Bolivia - Marcelo (masculino)": "es-BO-MarceloNeural",
    # 🇨🇱 Chile
    "Chile - Catalina (femenino)": "es-CL-CatalinaNeural",
    # 🇨🇴 Colombia
    "Colombia - Gonzalo (masculino)": "es-CO-GonzaloNeural",
    # 🇨🇷 Costa Rica
    "Costa Rica - Juan (masculino)": "es-CR-JuanNeural",
    # 🇨🇺 Cuba
    "Cuba - Belkys (femenino)": "es-CU-BelkysNeural",
    # 🇩🇴 República Dominicana
    "República Dominicana - Emilio (masculino)": "es-DO-EmilioNeural",
    # 🇪🇨 Ecuador
    "Ecuador - Andrea (femenino)": "es-EC-AndreaNeural",
    # 🇬🇹 Guatemala
    "Guatemala - Andrés (masculino)": "es-GT-AndresNeural",
    # 🇭🇳 Honduras
    "Honduras - Carlos (masculino)": "es-HN-CarlosNeural",
    # 🇳🇮 Nicaragua
    "Nicaragua - Federico (masculino)": "es-NI-FedericoNeural",
    # 🇵🇦 Panamá
    "Panamá - Margarita (femenino)": "es-PA-MargaritaNeural",
    # 🇵🇪 Perú
    "Perú - Camila (femenino)": "es-PE-CamilaNeural",
    # 🇵🇷 Puerto Rico
    "Puerto Rico - Karina (femenino)": "es-PR-KarinaNeural",
    # 🇵🇾 Paraguay
    "Paraguay - Tania (femenino)": "es-PY-TaniaNeural",
    # 🇸🇻 El Salvador
    "El Salvador - Lorena (femenino)": "es-SV-LorenaNeural",
    # 🇺🇸 Estados Unidos (español)
    "EE.UU. - Alonso (masculino)": "es-US-AlonsoNeural",
    # 🇺🇾 Uruguay
    "Uruguay - Mateo (masculino)": "es-UY-MateoNeural",
    # 🇻🇪 Venezuela
    "Venezuela - Paola (femenino)": "es-VE-PaolaNeural",
}

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

# --- FUNCIÓN DE TEXTO A VOZ (edge-tts) ---
async def text_to_speech_async(text, voice):
    """
    Convierte texto a voz usando edge-tts (gratuito, sin API key).
    Devuelve los bytes del audio MP3.
    """
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
    """Función wrapper para llamar desde Streamlit."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(text_to_speech_async(text, voice))

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
    if st.session_state.get('user_name'):
        return f"{base_prompt}\n\nDirígete al usuario por su nombre: {st.session_state.user_name}."
    else:
        return base_prompt

# --- INICIALIZAR EL ESTADO DE LA SESIÓN ---
if "messages" not in st.session_state:
    historial, nombre_guardado = load_chat_history()
    st.session_state.messages = historial
    st.session_state.user_name = nombre_guardado if nombre_guardado else None

# --- SELECCIONAR VOZ EN LA BARRA LATERAL ---
st.sidebar.title("🎤 Configuración de Voz")
st.sidebar.markdown("Selecciona la voz para el texto a voz:")

# Obtener las opciones del diccionario (ordenadas alfabéticamente)
voice_options = sorted(VOICES.keys())

# Inicializar la voz seleccionada en la sesión
if "selected_voice" not in st.session_state:
    # Por defecto, la voz femenina de México (Dalia) porque es muy natural
    st.session_state.selected_voice = "México - Dalia (femenino)"

# Selector de voz
selected_voice_label = st.sidebar.selectbox(
    "Elige una voz",
    options=voice_options,
    index=voice_options.index(st.session_state.selected_voice)
)
st.session_state.selected_voice = selected_voice_label

# Mostrar la voz actual en la barra lateral
st.sidebar.markdown(f"**Voz actual:** {selected_voice_label}")
st.sidebar.markdown("---")

# --- MOSTRAR EL HISTORIAL CON BOTÓN DE REPRODUCCIÓN ---
for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        # Si el mensaje es del asistente, añadir un botón para escucharlo
        if msg["role"] == "assistant":
            # Crear un botón con una clave única basada en el índice
            if st.button("🔊 Escuchar", key=f"tts_{idx}_{msg['content'][:30]}"):
                # Obtener el shortName de la voz seleccionada
                voice_short = VOICES[st.session_state.selected_voice]
                audio_bytes = text_to_speech(msg["content"], voice_short)
                if audio_bytes:
                    st.audio(audio_bytes, format="audio/mp3")

# --- ENTRADA DEL USUARIO Y RESPUESTA ---
if user_input := st.chat_input(
    placeholder="¿Qué tienes en mente hoy o qué proyecto estás desarrollando?",
    accept_file=True,
    file_type=["pdf", "jpg", "png", "txt", "csv", "docx"],
    accept_audio=True
):
    # 1. Si el usuario no tiene nombre guardado, intentar extraerlo del mensaje
    if not st.session_state.user_name:
        posible_nombre = extract_name(user_input.get("text", ""))
        if posible_nombre:
            st.session_state.user_name = posible_nombre
            save_chat_history(st.session_state.messages, user_name=st.session_state.user_name)

    # 2. Añadir mensaje del usuario al estado
    user_text = user_input.get("text", "")
    st.session_state.messages.append({"role": "user", "content": user_text})
    with st.chat_message("user"):
        st.markdown(user_text)

    # 3. Preparar la respuesta del asistente
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
            
            # 4. Guardar la respuesta de la IA en el estado
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
            # 5. Guardar el historial completo y el nombre en Firebase
            save_chat_history(st.session_state.messages, user_name=st.session_state.user_name)
            
        except Exception as e:
            st.error(f"Error de conexión con la IA: {str(e)}")
