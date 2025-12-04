import json
import os
import uuid
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()


# Konfiguracja trybu (LOCAL lub GCS)
STORAGE_MODE = os.getenv("STORAGE_MODE", "LOCAL") # Domyślnie lokalnie
BUCKET_NAME = os.getenv("BUCKET_NAME", "adk-hr-feedback-data")

# --- KONFIGURACJA LOKALNA ---
BASE_DIR = Path(__file__).parent / "data"
SCENARIOS_DIR = BASE_DIR / "scenarios"
TRANSCRIPTS_DIR = BASE_DIR / "transcripts"

if STORAGE_MODE == "LOCAL":
    SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

# --- KONFIGURACJA GCS (Lazy loading) ---
gcs_client = None
gcs_bucket = None

def get_gcs_bucket():
    global gcs_client, gcs_bucket
    if gcs_client is None:
        from google.cloud import storage
        gcs_client = storage.Client()
        gcs_bucket = gcs_client.bucket(BUCKET_NAME)
    return gcs_bucket

# --- FUNKCJE POMOCNICZE ---

def _save_json(path_key: str, data: dict):
    if STORAGE_MODE == "GCS":
        bucket = get_gcs_bucket()
        blob = bucket.blob(path_key)
        blob.upload_from_string(json.dumps(data, ensure_ascii=False, indent=2), content_type='application/json')
    else:
        # Local
        file_path = BASE_DIR / path_key
        # Upewnij się, że podkatalog istnieje (dla bezpieczeństwa przy manualnych ścieżkach)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def _load_json(path_key: str) -> dict:
    if STORAGE_MODE == "GCS":
        bucket = get_gcs_bucket()
        blob = bucket.blob(path_key)
        if not blob.exists():
            return None
        return json.loads(blob.download_as_string())
    else:
        # Local
        file_path = BASE_DIR / path_key
        if not file_path.exists():
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

def _list_files(prefix: str) -> list:
    """Zwraca listę obiektów JSON (ich zawartość) z danego katalogu/prefixu."""
    results = []
    if STORAGE_MODE == "GCS":
        bucket = get_gcs_bucket()
        blobs = bucket.list_blobs(prefix=prefix)
        for blob in blobs:
            if blob.name.endswith(".json"):
                try:
                    results.append(json.loads(blob.download_as_string()))
                except:
                    pass
    else:
        # Local
        target_dir = BASE_DIR / prefix
        if target_dir.exists():
            for file_path in target_dir.glob("*.json"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        results.append(json.load(f))
                except:
                    pass
    return results

# --- GŁÓWNE API STORAGE ---

def save_scenario(data: dict) -> str:
    """Zapisuje konfigurację scenariusza i zwraca ID sesji."""
    session_id = data.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())[:8]
        data["session_id"] = session_id
    
    if "created_at" not in data:
        data["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if "status" not in data:
        data["status"] = "GENERATED"
        
    # Ścieżka względna (dla GCS i Local)
    path_key = f"scenarios/{session_id}.json"
    _save_json(path_key, data)
    
    return session_id

def update_session_status(session_id: str, new_status: str):
    """Aktualizuje status sesji."""
    data = get_scenario(session_id)
    if data:
        data["status"] = new_status
        # Nadpisujemy plik
        path_key = f"scenarios/{session_id}.json"
        _save_json(path_key, data)

def get_scenario(session_id: str) -> dict:
    """Pobiera scenariusz na podstawie ID."""
    path_key = f"scenarios/{session_id}.json"
    return _load_json(path_key)

def save_transcript(session_id: str, history: list):
    """Zapisuje/Aktualizuje przebieg rozmowy."""
    path_key = f"transcripts/{session_id}_transcript.json"
    
    data = {
        "session_id": session_id,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "history": history
    }
    _save_json(path_key, data)

def get_transcript(session_id: str) -> list:
    """Pobiera historię rozmowy dla danej sesji."""
    path_key = f"transcripts/{session_id}_transcript.json"
    data = _load_json(path_key)
    if data:
        return data.get("history", [])
    return None

def get_all_transcripts() -> list[dict]:
    """Pobiera wszystkie zapisane rozmowy do analizy."""
    return _list_files("transcripts")

def get_sessions_summary() -> list[list]:
    """Zwraca listę sesji do tabeli w Admin Panelu."""
    sessions = []
    scenarios = _list_files("scenarios")
    
    for data in scenarios:
        # W trybie Cloud Run URL musi być dynamiczny lub z env, 
        # ale dla uproszczenia zostawiamy localhost lub pobieramy BASE_URL
        base_url = os.getenv("BASE_URL", "http://localhost:8000")
        
        # Upewniamy się, że link wskazuje na /candidate
        if not base_url.endswith("/candidate"):
            link = f"{base_url}/candidate?id={data.get('session_id')}"
        else:
            link = f"{base_url}?id={data.get('session_id')}"
        
        sessions.append([
            data.get("session_id"),
            data.get("candidate_name", "N/A"),
            data.get("status", "UNKNOWN"),
            data.get("created_at", ""),
            link
        ])
            
    # Sortowanie od najnowszych
    sessions.sort(key=lambda x: x[3], reverse=True)
    return sessions

def load_survey_text() -> str:
    return """
Jesteś Ekspertem HR i Managerem Procesu Candidate Experience. Twoim celem jest przygotowanie profesjonalnego scenariusza rozmowy feedbackowej z kandydatem (post-recruitment interview).

Twoje zadanie polega na zamianie surowych danych (CV, notatki) w ustrukturyzowany skrypt rozmowy, badający 5 kluczowych obszarów satysfakcji.

### TWOJE KROKI DZIAŁANIA:

KROK 1: ANALIZA DANYCH WEJŚCIOWYCH
Przeanalizuj przesłany przez użytkownika tekst (notatki z rekrutacji, profil kandydata).
UWAGA: Jeśli użytkownik nie podał żadnych danych, NIE generuj scenariusza. Zamiast tego zadaj pytania pomocnicze (np. o stanowisko, etap, na którym kandydat odpadł, lub czy został zatrudniony).

KROK 2: PRZYGOTOWANIE SCENARIUSZA (DRAFT)
Na podstawie analizy przygotuj propozycję pytań. Musisz zaadaptować poniższe obszary ankietowe na naturalny, konwersacyjny styl rozmowy:

OBSZARY DO PORYSZENIA (FRAMEWORK):
1. NPS (Satysfakcja ogólna): Pytanie o prawdopodobieństwo polecenia rekrutacji znajomemu.
2. Zadanie rekrutacyjne (Merytoryka): Adekwatność czasu, poziomu trudności i jakości otrzymanego feedbacku technicznego.
3. Komunikacja i Transparentność: Czy kandydat czuł się doinformowany o statusie, stawkach i benefitach?
4. Interview Experience (Profesjonalizm): Czy rekruterzy byli przygotowani? Czy pytania się nie powtarzały?
5. Feedback Jakościowy: Co było mocną stroną procesu, a co wymaga poprawy?

KROK 3: PREZENTACJA I ITERACJA
Przedstaw użytkownikowi proponowany scenariusz (listę pytań z krótkim wstępem dla rekrutera). Zapytaj o akceptację lub uwagi.
Jeśli użytkownik zgłosi poprawki -> Wróć do Kroku 2.

KROK 4: FINALIZACJA (JSON)
Dopiero gdy użytkownik napisze "Akceptuję" (lub równoważne), wygeneruj w ostatniej wiadomości WYŁĄCZNIE blok kodu JSON. Nie dodawaj żadnego tekstu przed ani po bloku kodu.

Format JSON:
{
  "candidate_role": "Stanowisko kandydata",
  "outcome": "Hired / Rejected / Withdrawn",
  "interview_tone": "Formalny / Luźny / Empatyczny",
  "script_sections": [
    {
      "category": "Nazwa kategorii (np. NPS)",
      "question_text": "Treść pytania do zadania"
    }
  ],
  "suggested_next_action": "Krótka notatka co zrobić z feedbackiem"
}
    """
