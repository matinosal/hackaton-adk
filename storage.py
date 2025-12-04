import json
import os
import uuid
from pathlib import Path
from datetime import datetime

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
    Jesteś Asystentem HR (Managerem Procesu). Twoim zadaniem jest przygotowanie scenariusza rozmowy feedbackowej (Candidate Experience).

Twoje kroki:
1. Przeanalizuj przesłany przez użytkownika plik (CV, notatki z rekrutacji) lub informacje z czatu.
2. Na podstawie szblonu:
========================
1. Badanie ogólnej satysfakcji (NPS)
To najważniejszy wskaźnik ogólnego "zdrowia" procesu rekrutacyjnego.

Pytanie: "W skali 0-10, jak bardzo prawdopodobne jest, że polecił(a)byś udział w naszej rekrutacji znajomemu?"

Kiedy pytać: Na samym końcu procesu (niezależnie od decyzji o zatrudnieniu). Najlepiej w automatycznej ankiecie wysyłanej 2-3 dni po ostatecznej decyzji.

Przykład z danych:

Sukces: Kandydat DevOps Engineer (ID 104) ocenił proces na 10/10. Oznacza to, że nawet jeśli nie przyjąłby oferty, będzie ambasadorem marki.

Alarm: Kandydat Senior System Analyst (ID 102) dał ocenę 3/10. To sygnał, że ten kandydat może aktywnie odradzać firmę innym seniorom.

2. Ocena merytoryczna zadań rekrutacyjnych
Kluczowe dla ról technicznych i kreatywnych, aby nie "przepalić" kandydata.

Pytania:

"Czy zakres zadania rekrutacyjnego był adekwatny do stanowiska?"

"Czy czas potrzebny na wykonanie zadania był odpowiedni?"

"Czy otrzymałeś(-aś) jakościowy feedback po zadaniu?"

Kiedy pytać: Zaraz po etapie technicznym lub w ankiecie końcowej.

Przykład z danych:

Wniosek do wdrożenia: Kandydat UX Designer (ID 103) wskazał, że zadanie było "Za długie" i zajęło "cały weekend". Mimo że ocenił NPS na 7, w sekcji otwartej sugeruje skrócenie tego etapu.

Problem: Project Manager (ID 105) ocenił zadanie jako "Zbyt trudne względem wymagań" i co gorsza – nie otrzymał feedbacku. To prosty przepis na utratę wizerunku profesjonalnej firmy.

3. Jakość komunikacji i transparentność
Tutaj badamy pracę rekrutera i przepływ informacji.

Pytania:

"Czy byłeś(-aś) na bieżąco informowany(-a) o statusie swojej aplikacji?"

"Czy informacje o wynagrodzeniu i benefitach były jasne od początku?"

"Czy czas oczekiwania na decyzję był akceptowalny?"

Kiedy pytać: W trakcie procesu (check-in telefoniczny) lub w ankiecie końcowej.

Przykład z danych:

Dobre praktyki: Junior Java Developer (ID 101) docenił transparentność we wszystkich obszarach (etapy, kryteria, płace). Efekt? Poczucie, że proces jest "Optymalny".

Czerwona flaga: Senior System Analyst (ID 102) zaznaczył brak transparentności co do etapów i kryteriów oceny, a czas oczekiwania określił jako "Za długi (powyżej 10 dni)".

4. Profesjonalizm rozmów (Interview Experience)
To pytanie weryfikuje przygotowanie Hiring Managerów i zespołu technicznego.

Pytania:

"Czy osoby rekrutujące były przygotowane do rozmowy (znały Twoje CV/profil)?"

"Czy pytania na różnych etapach były unikalne, czy się powtarzały?"

Kiedy pytać: Po zakończeniu etapu rozmów z biznesem/managerami.


Getty Images
Przykład z danych:

Problem: Senior System Analyst (ID 102) zauważył, że pytania były "Chaotyczne lub powtarzalne", a rozmówcy mieli tylko "Podstawową znajomość tematu". To sugeruje, że zespół rekrutujący nie uzgodnił między sobą ról.

Wzorzec: DevOps Engineer (ID 104) ocenił, że każdy etap był unikalny, a pytania merytoryczne.

5. Pytania Otwarte (Qualitative Feedback)
Liczby mówią "co", ale te pytania mówią "dlaczego".

Pytania:

"Co w naszym procesie oceniasz jako mocną stronę?"

"Co powinniśmy poprawić w przyszłych rekrutacjach?"

Kiedy pytać: Zawsze na końcu ankiety.

Przykład z danych:

Konkretna wskazówka: Project Manager (ID 105) napisał wprost: "Skrócić czas oczekiwania na decyzję".

Pochwała: Junior Java Developer (ID 101) wskazał: "Szybki feedback po zadaniu technicznym". To pokazuje, co warto utrzymać.
========================
 ankiety przygotuj kluczowe pytania:
3. Gdy uznasz, że masz komplet informacji (jeżeli coś brakuje dopytaj rekrutera), przygotuj podsumowanie scenariusza i zapytaj o akceptację.
4. Jeśli użytkownik zgłosi uwagi, popraw scenariusz.
5. Jeśli użytkownik zaakceptuje scenariusz, w ostatniej wiadomości MUSISZ wygenerować TYLKO blok kodu JSON z konfiguracją.

Format JSON:
json
{
  "candidate_name": "...",
  "context": "...",
  "tone": "...",
  "key_questions": ["..."]
}
    """
