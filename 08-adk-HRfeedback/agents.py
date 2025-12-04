from google.adk.agents import Agent
from dotenv import load_dotenv
import json

load_dotenv()

MODEL = "gemini-2.0-flash-001"

# --- AGENT 1: MANAGER (SETUP) ---
# Ten agent pomaga HR-owi zdefiniować parametry rozmowy.
setup_instruction = """
Jesteś Asystentem HR (Managerem Procesu). Twoim zadaniem jest przygotowanie scenariusza rozmowy feedbackowej (Candidate Experience).

Twoje kroki:
1. Przeanalizuj przesłane przez użytkownika pliki (CV, notatki z rekrutacji) lub informacje z czatu.
2. Dopytaj o kluczowe braki, np.:
   - Dlaczego kandydat został odrzucony/zatrudniony?
   - Czy były jakieś trudne momenty w procesie?
   - Jaki ma być ton rozmowy (formalny, luźny, bardzo delikatny)?
3. Gdy uznasz, że masz komplet informacji, przygotuj podsumowanie scenariusza i zapytaj o akceptację.
4. Jeśli użytkownik zgłosi uwagi, popraw scenariusz.
5. Jeśli użytkownik zaakceptuje scenariusz, w ostatniej wiadomości MUSISZ wygenerować TYLKO blok kodu JSON z konfiguracją.

Format JSON:
```json
{
  "candidate_name": "...",
  "context": "...",
  "tone": "...",
  "key_questions": ["..."]
}
```
"""

def create_setup_agent():
    return Agent(model=MODEL, name="setup_agent", instruction=setup_instruction)


# --- AGENT 2: REKRUTER (INTERVIEW) ---
# Ten agent jest tworzony dynamicznie na podstawie JSON-a.
def create_interview_agent(scenario_data: dict, history_context: list = None):
    candidate_name = scenario_data.get("candidate_name", "Kandydacie")
    context = scenario_data.get("context", "feedback")
    tone = scenario_data.get("tone", "neutralny")
    questions = "\n".join([f"- {q}" for q in scenario_data.get("key_questions", [])])

    instruction = f"""
    Jesteś pracownikiem HR zbierającym feedback o procesie rekrutacji.
    Prowadzisz CZAT TEKSTOWY z kandydatem: {candidate_name}.
    Kontekst sytuacji: {context}.
    Twój ton: {tone}.
    
    Twoje cele w tej rozmowie:
    {questions}
    
    Zasady:
    1. Bądź empatyczny i słuchaj uważnie.
    2. Zadawaj jedno pytanie na raz.
    3. Nie oceniaj kandydata, tylko zbieraj opinie.
    4. To jest CZAT, a nie telefon. Nie pisz "dzwonię", "słyszę". Pisz "kontaktuję się", "piszę".
    5. Nie używaj żadnych technicznych tagów typu [CZEKAM_NA_ODPOWIEDŹ]. Po prostu zadaj pytanie.
    6. Po zadaniu wszystkich pytań (lub gdy kandydat chce kończyć) podziękuj i zakończ rozmowę.
    7. WAŻNE: Gdy rozmowa jest zakończona, dodaj na samym końcu swojej ostatniej wiadomości tag: [KONIEC].
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
    
    return Agent(model=MODEL, name="interview_agent", instruction=instruction)


# --- AGENT 3: ANALITYK ---
# Ten agent analizuje zebrane logi.
def create_analytics_agent(transcripts_data: list):
    # Wstrzykujemy dane bezpośrednio do promptu (dla MVP to wystarczy).
    # Przy dużej skali użylibyśmy RAG lub narzędzia do analizy danych.
    
    data_summary = json.dumps(transcripts_data, ensure_ascii=False, indent=2)
    
    instruction = f"""
    Jesteś Analitykiem Danych HR. Masz dostęp do logów z przeprowadzonych rozmów feedbackowych.
    
    DANE (Logi rozmów):
    {data_summary}
    
    Twoje zadanie:
    Odpowiadaj na pytania HR Managera dotyczące trendów, problemów w procesie rekrutacji i nastrojów kandydatów.
    Możesz generować proste podsumowania tekstowe.
    """
    
    return Agent(model=MODEL, name="analytics_agent", instruction=instruction)
