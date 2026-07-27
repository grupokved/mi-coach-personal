import streamlit as st
import os
from groq import Groq

st.set_page_config(page_title="Mi Coach DeepSeek", page_icon="🧠", layout="centered")
st.title("🧠 Coach Personal e Intermediario Técnico")

API_KEY = os.environ.get("GITHUB_TOKEN")

if not API_KEY:
    st.error("⚠️ Falta la clave de API en Secrets.")
    st.stop()

client = Groq(api_key=API_KEY)

PROMPT_SISTEMA = """
Eres el coach personal, mentor de vida y estratega empresarial del usuario. 
Tu enfoque es profundamente humano, empático y perspicaz. 
Escucha de forma activa, cuestiona con preguntas socráticas y ayúdalo a superar bloqueos mentales o miedos en sus proyectos de vida y negocios. 
No uses clichés motivacionales falsos; sé honesto, directo y analítico.
También sirves como intermediario técnico: cuando el usuario te hable de una idea de software o código de forma vaga, tradúcela en un PROMPT TÉCNICO PERFECTO, listo para copiar y pegar en Cursor, Copilot o ChatGPT.
Mantén un tono de colega brillante, maduro y leal.
"""

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if user_input := st.chat_input("¿Qué tienes en mente hoy o qué proyecto estás desarrollando?"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        
        # ⚠️ IMPORTANTE: Sin system prompt, todo va en el primer mensaje del usuario
        api_messages = [{"role": "user", "content": PROMPT_SISTEMA}]
        api_messages.extend(st.session_state.messages)

        try:
            response = client.chat.completions.create(
                model="qwen/qwen3-32b",  # ✅ El modelo correcto
                messages=api_messages,
                temperature=0.6  # ✅ Temperatura ideal según documentación
            )
            
            full_response = response.choices[0].message.content
            placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
        except Exception as e:
            st.error(f"Error de conexión con la IA: {str(e)}")
