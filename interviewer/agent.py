from google.adk.agents.llm_agent import Agent
import datetime
import os
from .gcs_service import GCSService
from dotenv import load_dotenv

load_dotenv()

MODEL = "gemini-3-pro-preview"

def save_transcript(transcript: str):
    """Zapisuje transkrypcję rozmowy do pliku w Google Cloud Storage.
    
    Args:
        transcript: Pełna treść rozmowy do zapisania.
    """
    bucket_name = os.getenv("GCS_BUCKET_NAME")
    if not bucket_name:
        return "Błąd: Zmienna środowiskowa GCS_BUCKET_NAME nie jest ustawiona."

    try:
        gcs_service = GCSService(bucket_name=bucket_name)
        filename = f"transcriptions/transcript_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        gcs_path = gcs_service.upload_string(transcript, filename, content_type="text/plain; charset=utf-8")
        return f"Zapisano transkrypcję do: {gcs_path}"
    except Exception as e:
        error_message = f"Błąd podczas zapisu do GCS: {e}"
        print(error_message)
        return error_message

def create_interview_agent(scenario_data: dict, history_context: list = None):
    candidate_name = scenario_data.get("candidate_name", "Kandydacie")
    context = scenario_data.get("context", "feedback")
    tone = scenario_data.get("tone", "neutralny")
    questions = "\n".join([f"- {q}" for q in scenario_data.get("key_questions", [])])

    with open(os.path.join(os.path.dirname(__file__), 'examples', 'transcript_template.txt'), 'r', encoding='utf-8') as f:
        transcript_example = f.read()

    instruction = f"""
    Jesteś pracownikiem HR zbierającym feedback o procesie rekrutacji.
    Prowadzisz CZAT TEKSTOWY z kandydatem: {candidate_name}.
    Kontekst sytuacji: {context}.
    Twój ton: {tone}.
    
    Twoje cele w tej rozmowie:
    {questions}
    
    Zasady:
    1. Na samym początku rozmowy przedstaw się jako asystent AI i zapytaj o zgodę na przeprowadzenie i przetworzenie rozmowy. Jeśli kandydat się nie zgodzi, podziękuj i zakończ rozmowę. Dopiero po uzyskaniu zgody możesz przejść do właściwej rozmowy.
    2. Bądź empatyczny i słuchaj uważnie.
    3. Zadawaj jedno pytanie na raz.
    4. Nie oceniaj kandydata, tylko zbieraj opinie.
    5. Jeśli zadajesz pytanie o ocenę w skali (np. 1-5), a kandydat poda odpowiedź spoza tej skali, grzecznie poproś o ponowne podanie odpowiedzi, która mieści się w zakresie.
    6. To jest CZAT, a nie telefon. Nie pisz "dzwonię", "słyszę". Pisz "kontaktuję się", "piszę".
    7. Nie używaj żadnych technicznych tagów typu [CZEKAM_NA_ODPOWIEDŹ]. Po prostu zadaj pytanie.
    8. Po zadaniu wszystkich pytań (lub gdy kandydat chce kończyć) podziękuj i zakończ rozmowę.
    9. WAŻNE: Gdy rozmowa jest zakończona, MUSISZ wywołać narzędzie `save_transcript`, aby zapisać transkrypcję.
       - Transkrypcja MUSI być przekazana jako argument do narzędzia `save_transcript`.
       - NIE umieszczaj transkrypcji w swojej odpowiedzi tekstowej do użytkownika.
       - Twoja ostatnia wiadomość powinna być tylko podziękowaniem i pożegnaniem.
       Format transkrypcji:
          - Każda wiadomość w nowej linii, poprzedzona `AI: ` lub `Kandydat: `.
          - Puste linie między wypowiedziami.
          - Na końcu podsumowanie (stanowisko na jakie kandydat rekrutował, data przeprowadzenia czatu).
          Przykład:
          ```
          {transcript_example}
          ```
    """

    # Jeśli mamy historię (np. po restarcie serwera), dodajemy ją do kontekstu
    if history_context:
        history_str = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in history_context])
        instruction += f"""
        
        !!! WAŻNE - KONTYNUACJA ROZMOWY !!!
        To jest kontynuacja przerwanej sesji. Poniżej znajduje się dotychczasowa historia rozmowy.
        Twoim zadaniem jest PŁYNNIE KONTYNUOWAĆ od ostatniego punktu.
        
        ZASADY KONTYNUACJI:
        1. NIE przedstawiaj się ponownie - użytkownik już Cię zna.
        2. NIE witaj się ponownie (chyba że użytkownik zrobił to pierwszy po długiej przerwie, ale krótko).
        3. Przeanalizuj ostatnie pytanie lub odpowiedź z historii i nawiąż do niej.
        4. Jeśli użytkownik napisał "hej" lub inne powitanie w środku rozmowy, nie resetuj kontekstu. Zapytaj w czym pomóc lub wróć do tematu.

        [HISTORIA ROZMOWY]:
        {history_str}
        [KONIEC HISTORII]
        """
    
    return Agent(model=MODEL, name="interview_agent", instruction=instruction, tools=[save_transcript])

mock_scenario = {
  "candidate_name": "Jan Kowalski",
  "context": "Rozmowa feedbackowa po negatywnej decyzji rekrutacyjnej. Ton neutralny.",
  "tone": "neutralny",
  "key_questions": [
    "Jakie są Pana/Pani ogólne wrażenia z procesu rekrutacji?",
    "Czy coś w procesie było niejasne lub problematyczne?",
    "Czy ma Pan/Pani jakieś sugestie dotyczące usprawnień procesu rekrutacji?",
    "W skali od 1 do 5, jak ocenia Pan/Pani przebieg rozmowy rekrutacyjnej?"
  ],
  "session_id": "1f518253",
  "created_at": "2025-12-03 11:32:14",
  "status": "GENERATED"
}

root_agent = create_interview_agent(mock_scenario)
