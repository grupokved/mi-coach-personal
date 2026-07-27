import streamlit as st
import os
from groq import Groq

st.set_page_config(page_title="Mi Coach DeepSeek", page_icon="🧠", layout="centered")
st.title("🧠 Coach Personal e Intermediario Técnico")

# 1. Recuperar la clave secreta de Streamlit Cloud
API_KEY = os.environ.get("GITHUB_TOKEN")

if not API_KEY:
    st.error("⚠️ Falta la clave de API en Secrets. Revisa la configuración.")
    st.stop()

# 2. Conectar con el motor nativo de Groq
client = Groq(api_key=API_KEY)

# 3. El "Alma" de tu coach
PROMPT_SISTEMA = """
Eres el coach personal, mentor de vida y estratega empresarial del usuario. 
Tu enfoque es profundamente humano, empático y perspicaz. 
Escucha de forma activa, cuestiona con preguntas socráticas y ayúdalo a superar bloqueos mentales o miedos en sus proyectos de vida y negocios. 
No uses clichés motivacionales falsos; sé honesto, directo y analítico.
También sirves como intermediario técnico: cuando el usuario te hable de una idea de software o código de forma vaga, tradúcela en un PROMPT TÉCNICO PERFECTO, listo para copiar y pegar en Cursor, Copilot o ChatGPT.
Mantén un tono de colega brillante, maduro y leal.
"""

# 4. Inicializar el historial de la conversación
if "messages" not in st.session_state:
    st.session_state.messages = []

# 5. Mostrar los mensajes anteriores
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 6. Entrada del usuario
if user_input := st.chat_input("¿Qué tienes en mente hoy o qué proyecto estás desarrollando?"):
    # Guardamos el mensaje del usuario
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Preparamos la respuesta del asistente
    with st.chat_message("assistant"):
        placeholder = st.empty()
        
        # Estructura de mensajes para DeepSeek R1 (ponemos el sistema como primer usuario)
        api_messages = [{"role": "user", "content": PROMPT_SISTEMA}]
        api_messages.extend(st.session_state.messages)  # Añadimos todo el historial

        try:
            # Llamada al modelo ESTABLE de DeepSeek en Groq
            response = client.chat.completions.create(
                model="deepseek-r1-distill-llama-70b",  # ¡Este es el que SÍ funciona hoy!
                messages=api_messages,
                temperature=0.7
            )
            
            full_response = response.choices[0].message.content
            placeholder.markdown(full_response)
            
            # Guardamos la respuesta de la IA en el historial
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
        except Exception as e:
            st.error(f"Error de conexión con la IA: {str(e)}")
