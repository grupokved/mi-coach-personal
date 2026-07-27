import streamlit as st
import os
from groq import Groq
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import re

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
    # Patrones comunes: "me llamo X", "soy X", "mi nombre es X"
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
    # Cargar historial y nombre desde Firebase
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
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- ENTRADA DEL USUARIO Y RESPUESTA ---
if user_input := st.chat_input("¿Qué tienes en mente hoy o qué proyecto estás desarrollando?"):
    # 1. Si el usuario no tiene nombre guardado, intentar extraerlo del mensaje
    if not st.session_state.user_name:
        posible_nombre = extract_name(user_input)
        if posible_nombre:
            st.session_state.user_name = posible_nombre
            # Guardar el nombre en Firebase de inmediato
            save_chat_history(st.session_state.messages, user_name=st.session_state.user_name)

    # 2. Añadir mensaje del usuario al estado
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # 3. Preparar la respuesta del asistente
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
            
            # 4. Guardar la respuesta de la IA en el estado
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
            # 5. Guardar el historial completo y el nombre en Firebase
            save_chat_history(st.session_state.messages, user_name=st.session_state.user_name)
            
        except Exception as e:
            st.error(f"Error de conexión con la IA: {str(e)}")
