import gradio as gr
from agents import create_interview_agent
from storage import get_scenario, save_transcript, update_session_status, get_transcript
import time

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.genai import types

# Cache dla agentów w pamięci
active_runners = {}
session_service = InMemorySessionService()
artifact_service = InMemoryArtifactService()

DISCLAIMER_TEXT = """
👋 **Witaj!**

Dziękujemy za poświęcony czas. Chcielibyśmy poznać Twoją opinię o procesie rekrutacji.
Rozmowa jest prowadzona przez automatycznego asystenta AI.

🔒 **Poufność:**
Wszystkie informacje, które podasz, są zapisywane i będą analizowane przez nasz dział HR w celu poprawy jakości rekrutacji.
Jeśli nie wyrażasz zgody na przetwarzanie tej rozmowy, po prostu zamknij to okno.

Aby rozpocząć, napisz "Cześć" lub odpowiedz na pierwsze pytanie, jeśli się pojawi.
"""

def user_turn(message, history):
    if not message or not message.strip():
        return history, message
    history.append({"role": "user", "content": message})
    # Nie dodajemy placeholdera, Gradio samo pokaże "..." podczas przetwarzania bot_turn
    return history, ""

async def bot_turn(history, session_id_state, is_started_state):
    # Pobieramy ostatnią wiadomość użytkownika
    if not history or history[-1]['role'] != 'user':
        return history, is_started_state, gr.update(), gr.update()
        
    message = history[-1]['content']
    
    if not session_id_state:
        history.append({"role": "assistant", "content": "⚠️ BŁĄD: Brak ID sesji. Upewnij się, że link jest poprawny."})
        return history, is_started_state, gr.update(interactive=False), gr.update(interactive=False)

    # 1. Aktualizacja statusu na ONGOING przy pierwszej wiadomości
    if not is_started_state:
        update_session_status(session_id_state, "ONGOING")
        is_started_state = True

    # 2. Inicjalizacja agenta (jeśli nie istnieje w cache)
    if session_id_state not in active_runners:
        scenario_data = get_scenario(session_id_state)
        if not scenario_data:
            history.append({"role": "assistant", "content": "⚠️ BŁĄD: Nie znaleziono scenariusza."})
            return history, is_started_state, gr.update(interactive=False), gr.update(interactive=False)
        
        # Jeśli odtwarzamy agenta po restarcie, przekazujemy mu historię (bez ostatniej wiadomości, którą zaraz przetworzy)
        # Dzięki temu AI "pamięta" co było wcześniej, nawet jeśli pamięć RAM serwera została wyczyszczona.
        past_history = history[:-1] if len(history) > 1 else []
        agent = create_interview_agent(scenario_data, history_context=past_history)
        
        runner = Runner(app_name=f"interview_{session_id_state}", agent=agent, session_service=session_service, artifact_service=artifact_service)
        active_runners[session_id_state] = runner
    
    runner = active_runners[session_id_state]
    
    # 3. Rozmowa ADK
    user_id = f"candidate_{session_id_state}"
    
    adk_sessions_response = await session_service.list_sessions(app_name=f"interview_{session_id_state}", user_id=user_id)
    if adk_sessions_response.sessions:
        adk_session = adk_sessions_response.sessions[0]
    else:
        adk_session = await session_service.create_session(app_name=f"interview_{session_id_state}", user_id=user_id)

    content = types.Content(role='user', parts=[types.Part(text=message)])
    events = runner.run(user_id=user_id, session_id=adk_session.id, new_message=content)
    
    response_text = ""
    for event in events:
        if event.is_final_response():
            response_text = event.content.parts[0].text
    
    # 4. Sprawdzenie końca rozmowy
    is_finished = "[KONIEC]" in response_text
    clean_response = response_text.replace("[KONIEC]", "").strip()
    
    # Dodajemy odpowiedź bota
    history.append({"role": "assistant", "content": clean_response})
    
    # 5. Zapis historii
    save_transcript(session_id_state, history)
    
    if is_finished:
        update_session_status(session_id_state, "COMPLETED")
        return history, is_started_state, gr.update(interactive=False, placeholder="Rozmowa zakończona. Dziękujemy!"), gr.update(interactive=False)
    
    return history, is_started_state, gr.update(interactive=True), gr.update(interactive=True)

def load_session(request: gr.Request):
    params = dict(request.query_params)
    session_id = params.get('id')
    print(f"DEBUG: load_session called. Params: {params}, Session ID: {session_id}")
    
    history = []
    is_interactive = True
    placeholder_text = "Napisz wiadomość..."

    if session_id:
        # Sprawdzenie statusu sesji
        scenario = get_scenario(session_id)
        if scenario and scenario.get("status") == "COMPLETED":
            is_interactive = False
            placeholder_text = "Rozmowa zakończona. Dziękujemy!"

        # Próba załadowania istniejącej historii
        existing_history = get_transcript(session_id)
        if existing_history:
            history = existing_history
        else:
            # Początkowa historia z disclaimerem
            history = [
                {"role": "assistant", "content": DISCLAIMER_TEXT}
            ]
    else:
        history = [
            {"role": "assistant", "content": "⚠️ BŁĄD: Brak ID sesji w linku."}
        ]
        is_interactive = False
    
    return session_id, history, gr.update(interactive=is_interactive, placeholder=placeholder_text), gr.update(interactive=is_interactive)

# --- UI ---
# Definicja motywu
theme = gr.themes.Soft(
    primary_hue="blue",
    neutral_hue="slate",
    radius_size=gr.themes.sizes.radius_lg,
    font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"],
)

custom_css = """
/* 1. NADPISANIE ZMIENNYCH GRADIO (Dla Light i Dark mode) */
:root, .dark, body {
    --body-text-color: #1f2937 !important;
    --body-background-fill: #f3f4f6 !important;
    --background-fill-primary: white !important;
    --block-background-fill: white !important;
    --block-label-text-color: #374151 !important;
    --input-background-fill: #f9fafb !important;
    --block-border-color: #e5e7eb !important;
    --block-title-text-color: #1f2937 !important;
}

/* 2. STYLIZACJA KONTENERA */
.gradio-container { 
    max-width: 700px !important; 
    margin: 40px auto !important; 
    background: white !important; 
    border-radius: 20px !important; 
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
    padding: 20px !important;
}

/* 3. UKRYCIE ELEMENTÓW */
footer { display: none !important; }
.progress-text, .meta-text { display: none !important; }
#chatbot > .label-wrap { display: none !important; }

/* 4. STYLIZACJA CZATU */
#chatbot { 
    height: 60vh !important; 
    border: none !important; 
    background: transparent !important;
}

/* Dymki wiadomości */
.message-row.user-row .message,
.message-row.user-row .message * {
    background: #2563eb !important;
    color: white !important;
    border-radius: 15px 15px 0 15px !important;
}
.message-row.bot-row .message {
    background: #f1f5f9 !important;
    color: #1e293b !important; /* Ciemny tekst na jasnym tle */
    border-radius: 15px 15px 15px 0 !important;
    border: 1px solid #e2e8f0 !important;
}

/* Ukrycie przycisków akcji nad czatem (kosz, undo, retry) */
.chatbot-header, button[aria-label="Clear conversation"], button[aria-label="Undo"], button[aria-label="Retry"] {
    display: none !important;
}
"""

# Skrypt JS wymuszający usunięcie klasy 'dark' z body
js_force_light = """
function() {
    document.body.classList.remove('dark');
    document.body.classList.add('light');
}
"""

with gr.Blocks(title="Rozmowa Rekrutacyjna", theme=theme, css=custom_css, js=js_force_light) as demo:
    session_id_state = gr.State()
    is_started_state = gr.State(False)
    
    with gr.Column():
        # Nagłówek
        gr.Markdown(
            """
            <div style="text-align: center; margin-bottom: 20px;">
                <h1 style="font-size: 2rem; margin-bottom: 0.5rem;">🔵 Comarch Feedback Agent</h1>
                <p style="color: #64748b;">Asystent feedbacku rekrutacji</p>
            </div>
            """
        )
        
        chatbot = gr.Chatbot(
            height=500, 
            type="messages", 
            show_label=False,
            avatar_images=(None, "https://cdn-icons-png.flaticon.com/512/4712/4712027.png"), # Opcjonalnie: Avatar bota
            elem_id="chatbot",
            show_share_button=False,
            show_copy_button=False
        )
        
        with gr.Row():
            msg = gr.Textbox(
                show_label=False,
                placeholder="Napisz wiadomość...", 
                lines=1,
                max_lines=3,
                scale=4,
                autofocus=True,
                container=False
            )
            btn_send = gr.Button("➤", variant="primary", scale=1, min_width=50)
    
    # Ładowanie ID z URL przy starcie
    demo.load(load_session, None, [session_id_state, chatbot, msg, btn_send])
    
    # Obsługa wysyłania
    msg.submit(user_turn, [msg, chatbot], [chatbot, msg], queue=False).then(
        bot_turn, [chatbot, session_id_state, is_started_state], [chatbot, is_started_state, msg, btn_send]
    )
    btn_send.click(user_turn, [msg, chatbot], [chatbot, msg], queue=False).then(
        bot_turn, [chatbot, session_id_state, is_started_state], [chatbot, is_started_state, msg, btn_send]
    )

if __name__ == "__main__":
    print("Uruchamianie aplikacji kandydata na porcie 7861...")
    demo.launch(server_port=7861)
