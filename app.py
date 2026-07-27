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
    base_url="https://models.inference.ai.azure.com",
    api_key=GITHUB_TOKEN,
)

PROMPT_SISTEMA = """
Eres el coach personal, mentor de vida y estratega empresarial del usuario. Tu enfoque es profundamente humano, empático y perspicaz. 
Tus objetivos principales son:
1. Actuar como un detector de emociones, fortalezas y debilidades del usuario. Escucha de forma activa, cuestiona con preguntas socráticas y ayúdalo a superar bloqueos mentales o miedos en sus proyectos de vida y negocios. No uses clichés motivacionales falsos; sé honesto, directo y analítico.
2. Servir de intermediario técnico. Cuando el usuario te hable de una idea de software o código de forma vaga o emocional, tradúcela. Estructura esa idea en un PROMPT TÉCNICO PERFECTO, optimizado y limpio, listo para que el usuario simplemente lo copie y lo pegue en IAs de programación avanzadas (como Cursor, Copilot o ChatGPT).
Manten un tono de colega brillante, maduro y leal.
"""

if "messages" not in list.session_state:
    list.session_state.messages = [{"role": "system", "content": PROMPT_SISTEMA}]

for message in list.session_state.messages:
    if message["role"] != "system":
        with list.chat_message(message["role"]):
            list.markdown(message["content"])

if user_input := list.chat_input("¿Qué tienes en mente hoy o qué proyecto estás desarrollando?"):
    list.session_state.messages.append({"role": "user", "content": user_input})
    with list.chat_message("user"):
        list.markdown(user_input)

    with list.chat_message("assistant"):
        message_placeholder = list.empty()
        
        response = client.chat.completions.create(
            model="DeepSeek-R1-0528",
            messages=list.session_state.messages,
            temperature=0.7
        )
        
        # Corrección definitiva para extraer el texto de forma segura
        full_response = response.choices[0].message.content
        message_placeholder.markdown(full_response)
        
    list.session_state.messages.append({"role": "assistant", "content": full_response})
