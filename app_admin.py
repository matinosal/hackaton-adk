import gradio as gr
from agents import create_setup_agent #, create_analytics_agent, MODEL
from analyst.agent import create_analytic_agent

from storage import save_scenario, get_all_transcripts, get_sessions_summary
from google.adk.agents import Agent
from google.genai import types
import json
import re
import os
import pypdf

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService

# --- ZMIENNE STANU ---
setup_agent = create_setup_agent()
analytics_agent = None 

session_service = InMemorySessionService()
artifact_service = InMemoryArtifactService()
setup_runner = Runner(app_name="setup_app", agent=setup_agent, session_service=session_service, artifact_service=artifact_service)


# --- LOGIKA ZAKŁADKI 1: NOWY PROCES (SETUP) ---

async def run_setup_agent_internal(message):
    user_id = "admin_user"
    sessions_response = await session_service.list_sessions(app_name="setup_app", user_id=user_id)
    if sessions_response.sessions:
        session = sessions_response.sessions[0]
    else:
        session = await session_service.create_session(app_name="setup_app", user_id=user_id)
    
    content = types.Content(role='user', parts=[types.Part(text=message)])
    events = setup_runner.run(user_id=user_id, session_id=session.id, new_message=content)
    
    final_text = ""
    for event in events:
        if event.is_final_response():
            final_text = event.content.parts[0].text
    return final_text

async def chat_setup(message, history):
    if not message.strip():
        return history, ""
        
    response_text = await run_setup_agent_internal(message)
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": response_text})
    return history, "" # Zwracamy pusty string, aby wyczyścić input

async def generate_link_logic(history):
    """
    Pobiera ostatni blok JSON z historii czatu i generuje link.
    Gwarantuje to zgodność 1:1 z tym co widział użytkownik.
    """
    if not history:
        return "❌ Historia jest pusta."

    # Szukamy od końca wiadomości asystenta
    last_assistant_msg = None
    for msg in reversed(history):
        if msg['role'] == 'assistant':
            last_assistant_msg = msg['content']
            break
    
    if not last_assistant_msg:
        return "❌ Nie znaleziono odpowiedzi agenta."

    # Próba wyciągnięcia JSON z bloku kodu ```json ... ```
    json_match = re.search(r"```json\s*(\{.*?\})\s*```", last_assistant_msg, re.DOTALL)
    
    if not json_match:
        # Fallback: próba znalezienia czegokolwiek co wygląda jak JSON
        json_match = re.search(r"(\{.*\})", last_assistant_msg, re.DOTALL)

    if json_match:
        json_str = json_match.group(1)
        try:
            scenario_data = json.loads(json_str)
            session_id = save_scenario(scenario_data)
            
            # Dynamiczny URL zależny od środowiska
            # Domyślnie localhost:8000 dla uvicorn --reload, ale można nadpisać zmienną env
            base_url = os.getenv("BASE_URL", "http://localhost:8000")
            # Upewniamy się, że link wskazuje na /candidate
            if not base_url.endswith("/candidate"):
                link = f"{base_url}/candidate?id={session_id}"
            else:
                link = f"{base_url}?id={session_id}"
            
            return f"✅ Scenariusz zapisany!\nID Sesji: {session_id}\n\n🔗 LINK DLA KANDYDATA:\n{link}"
        except json.JSONDecodeError:
            return f"❌ Błąd parsowania JSON. Upewnij się, że agent wygenerował poprawny format.\nZnaleziono: {json_str[:50]}..."
    else:
        return "❌ Nie znaleziono bloku JSON w ostatniej wiadomości agenta. Poproś agenta o wygenerowanie podsumowania."


def reset_setup():
    global setup_agent
    setup_agent = create_setup_agent()
    return [], "Rozpoczęto nową sesję konfiguracji."

def refresh_sessions_list():
    return get_sessions_summary()

# --- LOGIKA ZAKŁADKI 2: ANALITYKA ---

async def chat_analytics(message, history):
    if not message.strip():
        return history, ""

    global analytics_agent
    
    analytics_agent = create_analytic_agent()
    
    # Tworzymy tymczasowego runnera dla analityka
    analytics_runner = Runner(app_name="analytics_app", agent=analytics_agent, session_service=session_service, artifact_service=artifact_service)
    
    user_id = "admin_user"
    # Zawsze nowa sesja dla analityka, żeby nie mieszać kontekstów
    session = await session_service.create_session(app_name="analytics_app", user_id=user_id)
    
    content = types.Content(role='user', parts=[types.Part(text=message)])
    events = analytics_runner.run(user_id=user_id, session_id=session.id, new_message=content)
    
    final_text = ""
    for event in events:
        if event.is_final_response():
            final_text = event.content.parts[0].text
            
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": final_text})
    return history, ""


# --- INTERFEJS ---

with gr.Blocks(title="HR Admin Dashboard", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 👔 HR Admin Dashboard")
    
    with gr.Tabs():
        # ZAKŁADKA 1: SETUP
        with gr.TabItem("📝 Nowy Proces (Setup)"):
            with gr.Row():
                with gr.Column(scale=3):
                    chatbot_setup = gr.Chatbot(height=600, type="messages", label="Asystent HR")
                    msg_setup = gr.Textbox(
                        label="Twoja wiadomość", 
                        placeholder="Opisz kandydata, stanowisko i cel rozmowy...",
                        lines=5,
                        max_lines=10
                    )
                    
                    with gr.Row():
                        btn_send = gr.Button("Wyślij", variant="primary", scale=2)
                        btn_upload = gr.UploadButton("📎 Wgraj CV/Notatki", file_types=[".txt", ".pdf", ".docx"], scale=1)
                
                with gr.Column(scale=1):
                    gr.Markdown("### ⚙️ Akcje")
                    gr.Markdown("1. Ustal szczegóły z Asystentem.\n2. Zaakceptuj wygenerowany JSON.\n3. Kliknij Generuj Link.")
                    btn_generate = gr.Button("Generuj Link", variant="stop")
                    link_output = gr.Textbox(label="Wygenerowany Link", interactive=False, lines=3)
                    btn_reset = gr.Button("🔄 Resetuj Rozmowę")

            # Obsługa zdarzeń
            msg_setup.submit(chat_setup, [msg_setup, chatbot_setup], [chatbot_setup, msg_setup])
            btn_send.click(chat_setup, [msg_setup, chatbot_setup], [chatbot_setup, msg_setup])
            
            # Obsługa pliku
            def handle_file(file):
                try:
                    if file.name.lower().endswith('.pdf'):
                        reader = pypdf.PdfReader(file.name)
                        content = ""
                        for page in reader.pages:
                            content += page.extract_text() + "\n"
                    else:
                        with open(file.name, 'r', encoding='utf-8') as f:
                            content = f.read()
                    return f"Przesyłam plik z danymi kandydata:\n\n{content[:2000]}..." 
                except Exception as e:
                    return f"Błąd odczytu pliku: {str(e)}"
            
            btn_upload.upload(handle_file, btn_upload, msg_setup)
            
            btn_generate.click(generate_link_logic, chatbot_setup, link_output)
            btn_reset.click(reset_setup, None, [chatbot_setup, link_output])

        # ZAKŁADKA 2: LISTA SESJI
        with gr.TabItem("📋 Lista Sesji"):
            gr.Markdown("### Przegląd wszystkich procesów rekrutacyjnych")
            btn_refresh = gr.Button("🔄 Odśwież listę")
            sessions_table = gr.Dataframe(
                headers=["ID Sesji", "Kandydat", "Status", "Data Utworzenia", "Link"],
                datatype=["str", "str", "str", "str", "str"],
                value=get_sessions_summary(),
                interactive=False
            )
            btn_refresh.click(refresh_sessions_list, None, sessions_table)

        # ZAKŁADKA 3: ANALITYKA
        with gr.TabItem("📊 Analityka"):
            gr.Markdown("### Analiza zbiorcza")
            chatbot_analytics = gr.Chatbot(height=600, type="messages")
            msg_analytics = gr.Textbox(label="Pytanie do Analityka", placeholder="Jakie są najczęstsze powody odrzuceń?", lines=3)
            btn_send_analytics = gr.Button("Zapytaj", variant="primary")
            
            msg_analytics.submit(chat_analytics, [msg_analytics, chatbot_analytics], [chatbot_analytics, msg_analytics])
            btn_send_analytics.click(chat_analytics, [msg_analytics, chatbot_analytics], [chatbot_analytics, msg_analytics])

if __name__ == "__main__":
    demo.launch(server_port=7860)
