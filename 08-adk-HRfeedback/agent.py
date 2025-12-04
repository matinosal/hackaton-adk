from agents import create_interview_agent, create_setup_agent
from dotenv import load_dotenv
import os

load_dotenv()

# --- KONFIGURACJA TESTOWA DLA ADK ---
# Ten plik pozwala uruchomić agenta w standardowym środowisku ADK (np. adk run / adk web)
# Służy do izolowanych testów logiki agenta bez interfejsu Gradio.

# Przykładowe dane dla rekrutera
mock_scenario = {
    "candidate_name": "Jan Testowy",
    "context": "Symulacja rozmowy w celu przetestowania promptu.",
    "tone": "Profesjonalny, ale przyjazny",
    "key_questions": [
        "Co skłoniło Cię do aplikacji?",
        "Jakie jest Twoje największe osiągnięcie?"
    ]
}

# Aby ADK widziało agenta, musi on być przypisany do zmiennej `root_agent`.
# Możesz tutaj podmienić funkcję na create_setup_agent(), aby testować managera.

root_agent = create_interview_agent(mock_scenario)
# root_agent = create_setup_agent()
