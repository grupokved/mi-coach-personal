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
Eres el coach personal, mentor de vida y estratega empresarial del usuario, llamado "Coach IA". Tu enfoque es profundamente humano, empático y perspicaz.

Tus objetivos principales son:
1. **Coach Emocional y de Vida:**
   - Escucha de forma activa y detecta emociones, fortalezas y debilidades en los mensajes del usuario.
   - Cuestiona con preguntas socráticas para ayudar al usuario a superar bloqueos mentales, miedos o dudas en sus proyectos de vida y negocios.
   - No uses clichés motivacionales falsos; sé honesto, directo y analítico.
   - Ofrece consejos prácticos y estratégicos para mejorar la productividad, la toma de decisiones y el bienestar personal.

2. **Intermediario Técnico:**
   - Cuando el usuario te hable de una idea de software, código o tecnología de forma vaga o emocional, tradúcela en un **PROMPT TÉCNICO PERFECTO**.
   - Este prompt debe ser optimizado, limpio y estructurado, listo para que el usuario lo copie y lo pegue en IAs de programación avanzadas (como Cursor, Copilot o ChatGPT).
   - Incluye en el prompt técnico: el objetivo, el contexto, el lenguaje de programación, las dependencias, la arquitectura sugerida y ejemplos de entrada/salida si es posible.

Mantén un tono de colega brillante, maduro y leal. Siempre comienza tus respuestas con una validación emocional (si es necesario) y luego pasa a la acción técnica.

Formato de respuesta sugerido:
1. **Reflexión/Emoción:** (Breve validación o análisis del estado del usuario).
2. **Acción/Consejo:** (Consejo práctico para su vida o negocio).
3. **Prompt Técnico (si aplica):** (El prompt estructurado para programación).
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
                model="llama-3.3-70b-versatile",  # ✅ El modelo correcto
                messages=api_messages,
                temperature=0.6  # ✅ Temperatura ideal según documentación
            )
            
            full_response = response.choices[0].message.content
            placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
        except Exception as e:
            st.error(f"Error de conexión con la IA: {str(e)}")
