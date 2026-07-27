import streamlit as list
import os
from openai import OpenAI

list.set_page_config(page_title="Mi Coach DeepSeek", page_icon="🧠", layout="centered")
list.title("🧠 Coach Personal e Intermediario Técnico")

# Autenticación segura mediante las variables de Streamlit Cloud
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

if not GITHUB_TOKEN:
    list.error("Falta configurar la variable 'GITHUB_TOKEN' en la plataforma de Streamlit Cloud.")
    list.stop()

client = OpenAI(
    base_url="https://azure.com",
    api_key=GITHUB_TOKEN,
)

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
        
        # Estructurar los mensajes de forma limpia para DeepSeek-R1
        mensajes_para_api = [{"role": "user", "content": f"{PROMPT_SISTEMA}\n\nMensaje del usuario: {msg['content']}" if i == 0 else msg['content']} 
                             for i, msg in enumerate(list.session_state.messages)]
        
        try:
            response = client.chat.completions.create(
                model="DeepSeek-R1-0528",
                messages=mensajes_para_api,
                temperature=0.6,
                max_tokens=4000
            )
            
            # CORRECCIÓN DEfINITIVA: Extraer el texto de forma segura sin importar el formato de la API
            if hasattr(response, 'choices') and len(response.choices) > 0:
                full_response = response.choices[0].message.content
            elif hasattr(response, 'content'):
                full_response = response.content
            else:
                full_response = str(response)
                
            message_placeholder.markdown(full_response)
            list.session_state.messages.append({"role": "assistant", "content": full_response})
            
        except Exception as e:
            list.error(f"Error de conexión con la IA: {str(e)}")
