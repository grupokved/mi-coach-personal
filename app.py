import streamlit as list
import os
from groq import Groq  # Importamos la librería nativa de Groq

list.set_page_config(page_title="Mi Coach DeepSeek", page_icon="🧠", layout="centered")
list.title("🧠 Coach Personal e Intermediario Técnico")

# Recoge la clave de Groq guardada de forma segura
API_KEY = os.environ.get("GITHUB_TOKEN")

if not API_KEY:
    list.error("Falta configurar la variable de autenticación en Secrets.")
    list.stop()

# Conexión directa y nativa usando el cliente oficial de Groq
client = Groq(api_key=API_KEY)

PROMPT_SISTEMA = """
INSTRUCCIÓN DE ROL (Actúa bajo estos parámetros en cada respuesta):
1. Eres el coach personal, mentor de vida y estratega empresarial del usuario. Tu enfoque es profundamente humano, empático y perspicaz. Escucha de forma activa, cuestiona con preguntas socráticas y ayúdalo a superar bloqueos mentales o miedos en sus proyectos de vida y negocios. No uses clichés motivacionales falsos; sé honesto, directo y analítico.
2. Servir de intermediario técnico. Cuando el usuario te hable de una idea de software o código de forma vaga o emocional, tradúcela. Estructura esa idea en un PROMPT TÉCNICO PERFECTO, optimizado y limpio, listo para que el usuario simplemente lo copie y lo pegue en IAs de programación avanzadas (como Cursor, Copilot o ChatGPT).
Manten un tono de colega brillante, maduro y leal.
"""

if "messages" not in list.session_state:
    list.session_state.messages = []

# Mostrar el historial en pantalla
for message in list.session_state.messages:
    with list.chat_message(message["role"]):
        list.markdown(message["content"])

if user_input := list.chat_input("¿Qué tienes en mente hoy o qué proyecto estás desarrollando?"):
    list.session_state.messages.append({"role": "user", "content": user_input})
    with list.chat_message("user"):
        list.markdown(user_input)

    with list.chat_message("assistant"):
        message_placeholder = list.empty()
        
        # Estructura de mensajes para modelos de razonamiento profundo
        mensajes_para_api = [{"role": "user", "content": f"{PROMPT_SISTEMA}\n\nMensaje del usuario: {msg['content']}" if i == 0 else msg['content']} 
                             for i, msg in enumerate(list.session_state.messages)]
        
        try:
            # Llamada nativa sin intermediarios a los servidores de Groq
            response = client.chat.completions.create(
                model="deepseek-r1-distill-llama-70b", # DeepSeek R1 oficial en Groq
                messages=mensajes_para_api,
                temperature=0.6
            )
            
            full_response = response.choices[0].message.content
            message_placeholder.markdown(full_response)
            list.session_state.messages.append({"role": "assistant", "content": full_response})
            
        except Exception as e:
            list.error(f"Error de conexión con la IA: {str(e)}")
