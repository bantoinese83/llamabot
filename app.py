import json
import os
from datetime import datetime
from enum import Enum
from typing import List, Dict

import requests
import streamlit as st
from PIL import Image
from cachetools import cached, TTLCache
from groq import Groq
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base
from streamlit_lottie import st_lottie

# Constants for the Streamlit app and database
CONFIG_FILE_NAME = "config.json"
API_KEY_ENV_VAR = "GROQ_API_KEY"
DB_NAME = "chat_history.db"

# UI Settings
THEME_COLOR = "#00bfae"

# Lottie's animation URLs or file paths
LOTTIE_WELCOME_URL = "https://lottie.host/6cc5c636-161e-4fe2-a29e-d0a010fb857d/oUxnN8jMLv.json"
LOTTIE_LOADING_URL = "https://lottie.host/6db67e84-29ca-4df7-9aed-e918be35c04f/GUHZd8ZAiP.json"
LOTTIE_SUCCESS_URL = "https://lottie.host/0d17b47d-7e01-4b7d-a8fb-f94b6c69dd48/jycOqQmo4J.json"
LOTTIE_ERROR_URL = "https://lottie.host/caa8d9f2-7b02-4462-867d-4a5a1aa1a175/3HRdfJrk9m.json"
LOTTIE_NO_DATA_URL = "https://lottie.host/aa234c54-eca8-4b61-a21c-83b5b1e82698/1EEUxyZ91a.json"


# Enum for chat roles
class Role(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


# Database setup
Base = declarative_base()


class ChatMessage(Base):
    __tablename__ = 'chat_history'
    id = Column(Integer, primary_key=True)
    role = Column(String)
    content = Column(String)
    timestamp = Column(DateTime)
    model_id = Column(String)  # Add model_id to the table


class Feedback(Base):
    __tablename__ = 'feedback'
    id = Column(Integer, primary_key=True)
    chat_message_id = Column(Integer, ForeignKey('chat_history.id'))
    is_positive = Column(Boolean)
    comment = Column(String)


def initialize_db():
    engine = create_engine(f'sqlite:///{DB_NAME}')
    Base.metadata.create_all(engine)


@cached(cache=TTLCache(maxsize=100, ttl=300))
def get_groq_models():
    api_key = os.getenv(API_KEY_ENV_VAR)
    url = "https://api.groq.com/openai/v1/models"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    for _ in range(3):  # Retry mechanism
        response = requests.get(url, headers=headers)
        if response.ok:
            try:
                models = response.json()["data"]
                return [{"name": model["id"], "id": model["id"], "info": model.get("description", "")} for model in
                        models]
            except (KeyError, TypeError) as e:
                st.error(f"Error parsing models from the API response: {e}")
                return []
        else:
            st.error(f"Failed to fetch models from the API: {response.text}")
    return []


def save_message(role: str, content: str, timestamp: str, model: Dict[str, str]):
    engine = create_engine(f'sqlite:///{DB_NAME}')
    Session = sessionmaker(bind=engine)
    session = Session()
    new_message = ChatMessage(
        role=role,
        content=content,
        timestamp=datetime.fromisoformat(timestamp),
        model_id=model["id"]  # Extract the model ID from the dictionary
    )
    session.add(new_message)
    session.commit()
    session.close()


def load_chat_history() -> List[Dict[str, str]]:
    engine = create_engine(f'sqlite:///{DB_NAME}')
    Session = sessionmaker(bind=engine)
    session = Session()
    chat_history = session.query(ChatMessage).order_by(ChatMessage.id).all()
    session.close()
    return [{"role": msg.role, "content": msg.content, "timestamp": msg.timestamp.isoformat(), "model_id": msg.model_id}
            for msg in chat_history]


def load_configuration() -> Dict[str, str]:
    try:
        working_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(working_dir, CONFIG_FILE_NAME)
        with open(config_path) as config_file:
            return json.load(config_file)
    except FileNotFoundError:
        st.error(f"Configuration file '{CONFIG_FILE_NAME}' not found. Please ensure it exists.")
        return {}
    except json.JSONDecodeError:
        st.error("Failed to decode the configuration file. Please check the file format.")
        return {}


def create_groq_client(api_key: str) -> Groq:
    os.environ[API_KEY_ENV_VAR] = api_key
    return Groq()


def fetch_chat_response(client: Groq, history: List[Dict[str, str]], model: str) -> str:
    try:
        response = client.chat.completions.create(
            model=model,
            messages=history
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Error retrieving response from API: {e}")
        return "😅 Sorry, there was an error processing your request."


def format_timestamp(timestamp_iso: str) -> str:
    timestamp_dt = datetime.fromisoformat(timestamp_iso)
    return timestamp_dt.strftime("%Y-%m-%d %H:%M:%S")


def initialize_chat_history():
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = load_chat_history()


def display_chat_history():
    for i, chat_message in enumerate(st.session_state.chat_history):
        formatted_timestamp = format_timestamp(chat_message["timestamp"])
        with st.chat_message(chat_message["role"]):
            st.markdown(f"{chat_message['content']}<br><small>{formatted_timestamp} ⏰</small>", unsafe_allow_html=True)
        if i < len(st.session_state.chat_history) - 1:
            st.markdown("---")  # Add separator


def handle_user_input(groq_client_instance: Groq, selected_model: Dict[str, str]):
    user_message = st.chat_input("Ask LLAMA... 🦙")
    if user_message:
        st.chat_message(Role.USER.value).markdown(f"👤 {user_message}")
        timestamp = datetime.now().isoformat()
        if selected_model:
            save_message(Role.USER.value, user_message, timestamp, selected_model)
            st.session_state.chat_history.append({
                "role": Role.USER.value,
                "content": user_message,
                "timestamp": timestamp,
                "model_id": selected_model["id"]  # Add model_id to the chat history
            })

            # Create a placeholder for the animation
            lottie_thinking_placeholder = st.empty()

            # Display the thinking animation
            with lottie_thinking_placeholder.container():
                st_lottie(LOTTIE_LOADING_URL, height=200, width=200, key="thinking")

                history_for_api = prepare_history_for_api()
                assistant_reply = fetch_chat_response(groq_client_instance, history_for_api, selected_model["id"])

                add_assistant_reply(assistant_reply, selected_model)
                display_assistant_reply(assistant_reply)

            # Clear the animation placeholder after the response
            lottie_thinking_placeholder.empty()

            # Clear the user input after sending
            st.text_input("User Input", value="", label_visibility="collapsed")
            st.rerun()
        else:
            st.error("No model selected. Please select a model from the sidebar.")


def prepare_history_for_api() -> List[Dict[str, str]]:
    return [
        {"role": Role.SYSTEM.value, "content": "You are my helpful assistant 🦙"},
        *[{"role": msg["role"], "content": msg["content"]} for msg in st.session_state.chat_history]
    ]


def add_assistant_reply(reply: str, model: Dict[str, str]):
    timestamp = datetime.now().isoformat()
    save_message(Role.ASSISTANT.value, reply, timestamp, model)
    st.session_state.chat_history.append({
        "role": Role.ASSISTANT.value,
        "content": reply,
        "timestamp": timestamp,
        "model_id": model["id"],
        "id": len(st.session_state.chat_history)  # Ensure each message has a unique id
    })


def display_assistant_reply(reply: str):
    st.markdown("---")  # Add separator
    with st.chat_message(Role.ASSISTANT.value):
        st_lottie(LOTTIE_SUCCESS_URL, height=150, width=150, key="reply_success")
        st.markdown(f"🤖 {reply}")


def save_feedback(chat_message_id, is_positive, comment):
    engine = create_engine(f'sqlite:///{DB_NAME}')
    Session = sessionmaker(bind=engine)
    session = Session()

    # Check if feedback already exists for the given chat_message_id
    existing_feedback = session.query(Feedback).filter_by(chat_message_id=chat_message_id).first()

    if existing_feedback:
        # Update the existing feedback
        existing_feedback.is_positive = is_positive
        existing_feedback.comment = comment
        session.commit()
        st.success("Feedback updated!")
    else:
        # Insert new feedback
        new_feedback = Feedback(chat_message_id=chat_message_id, is_positive=is_positive, comment=comment)
        session.add(new_feedback)
        session.commit()
        st.success("Feedback saved!")

    session.close()


def clear_chat_history():
    engine = create_engine(f'sqlite:///{DB_NAME}')
    Session = sessionmaker(bind=engine)
    session = Session()
    session.query(ChatMessage).delete()
    session.commit()
    session.close()
    st.session_state.chat_history = []


def search_chat_history(query: str):
    filtered_history = []
    for chat_message in st.session_state.chat_history:
        if query.lower() in chat_message["content"].lower():
            filtered_history.append(chat_message)
    return filtered_history


# Function to parse models_info.md and return a dictionary of model descriptions
def parse_models_info(file_path: str) -> Dict[str, str]:
    models_info = {}
    with open(file_path, 'r') as file:
        lines = file.readlines()
        current_model_id = None
        current_model_description = []
        for line in lines:
            if line.startswith("**"):
                if current_model_id:
                    models_info[current_model_id] = "\n".join(current_model_description)
                current_model_id = line.split("**")[1].strip()
                current_model_description = []
            elif line.startswith("- Model ID:"):
                current_model_id = line.split(":")[1].strip()
            elif line.startswith("- "):
                current_model_description.append(line.strip())
        if current_model_id:
            models_info[current_model_id] = "\n".join(current_model_description)
    return models_info


# Directory to store uploaded audio files
UPLOADS_DIR = "uploads"
if not os.path.exists(UPLOADS_DIR):
    os.makedirs(UPLOADS_DIR)


def transcribe_audio(client: Groq, audio_file_path, model="whisper-large-v3", language=None):
    """Transcribes audio using Groq's Whisper API."""
    try:
        with open(audio_file_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(audio_file_path, file.read()),
                model=model,
                language=language
            )
        return transcription.text
    except Exception as e:
        st.error(f"Error transcribing audio: {e}")
        return None


def main():
    st.set_page_config(
        page_title="LLAMABOT",
        page_icon="🦙",
        layout="centered",
        initial_sidebar_state="expanded"
    )

    # Load configuration and initialize Groq client
    config = load_configuration()
    api_key_value = config.get(API_KEY_ENV_VAR)

    if not api_key_value:
        st_lottie(LOTTIE_ERROR_URL, height=150, width=150, key="api_error")
        st.error("API key is missing in the configuration.")
        return

    groq_client_instance = create_groq_client(api_key_value)

    initialize_db()  # Initialize the database
    initialize_chat_history()

    # Main Title
    logo_image = Image.open("assets/logo-removebg-preview.png")
    st.image(logo_image)

    # Load model descriptions
    models_info = parse_models_info("assets/models_info.md")

    # Sidebar with settings and chat history
    with st.sidebar:
        st.header("LLAMABOT Settings ⚙️")
        st_lottie(LOTTIE_WELCOME_URL, height=100, width=100, key="welcome")
        groq_models = get_groq_models()
        selected_model = st.selectbox("Select a Model", groq_models, format_func=lambda model: model["name"])
        # Display model description from models_info.md
        if selected_model:
            model_id = selected_model['id']
            model_description = models_info.get(model_id, "No description available.")
            st.markdown(f"**Model Description:** {model_description}")
        else:
            st.warning("No model selected. Please select a model to start chatting.")
            st.markdown("---")

        # Chat History
        st.subheader("Chat History 📜")
        with st.expander("Expand Chat History", expanded=False):
            if st.session_state.chat_history:
                query = st.text_input("Search Chat History", placeholder="Enter your search term")
                if query:
                    filtered_history = search_chat_history(query)
                    for chat_message in filtered_history:
                        formatted_timestamp = format_timestamp(chat_message["timestamp"])
                        with st.chat_message(chat_message["role"]):
                            st.markdown(f"{chat_message['content']}<br><small>{formatted_timestamp} ⏰</small>",
                                        unsafe_allow_html=True)
                        st.markdown("---")
                else:
                    display_chat_history()
            else:
                st_lottie(LOTTIE_NO_DATA_URL, height=150, width=150, key="no_data")
                st.info("No chat history available.")

        # Add a button to start a new chat
        if st.button("🆕", help="Start a new chat session"):
            clear_chat_history()
            st.rerun()

        # Speech-to-Text Section
        st.markdown("---")
        st.header("Speech-to-Text 🎙️")
        uploaded_audio = st.file_uploader("Upload an audio file",
                                          type=["mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm"])
        selected_language = st.selectbox("Select audio language (optional)", ["", "en", "fr", "es", "de"],
                                         help="Leave blank for auto-detect")

    # Display the chat history
    if st.session_state.chat_history:
        display_chat_history()
    else:
        st_lottie(LOTTIE_NO_DATA_URL, height=200, width=200, key="no_chat_history")
        st.info("No chat history to display.")

    # Main Chat Area
    handle_user_input(groq_client_instance, selected_model)

    # Display feedback buttons (outside the if block)
    if st.session_state.chat_history:
        chat_message_id = st.session_state.chat_history[-1].get("id")

        # Use Unicode characters for thumbs up/down instead of emojis
        col1, col2 = st.columns(2)
        with col1:
            if st.button("👍", key=f"positive_feedback_{chat_message_id}"):  # Unicode thumbs up
                st_lottie(LOTTIE_SUCCESS_URL, height=100, width=100, key="positive_feedback")
                comment = st.text_input(f"Feedback for message {chat_message_id}")
                save_feedback(chat_message_id, True, comment)
        with col2:
            if st.button("👎", key=f"negative_feedback_{chat_message_id}"):  # Unicode thumbs down
                st_lottie(LOTTIE_ERROR_URL, height=100, width=100, key="negative_feedback")
                comment = st.text_input(f"Feedback for message {chat_message_id}")
                save_feedback(chat_message_id, False, comment)

    if uploaded_audio is not None:
        # Save the uploaded file to the uploads directory
        audio_file_path = os.path.join(UPLOADS_DIR, uploaded_audio.name)
        with open(audio_file_path, "wb") as f:
            f.write(uploaded_audio.read())

        # Display the uploaded audio
        st.audio(uploaded_audio, format='audio/wav')

        if st.button("Transcribe"):
            with st.spinner("Transcribing..."):
                transcript = transcribe_audio(groq_client_instance, audio_file_path, language=selected_language)
            if transcript:
                st.success("Transcription successful!")
                st.text_area("Transcription:", value=transcript)
            else:
                st.error("Transcription failed. Please try again.")


if __name__ == "__main__":
    main()
