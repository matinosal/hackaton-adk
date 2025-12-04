from google.adk.agents.llm_agent import Agent

MODEL = "gemini-2.0-flash-001"

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

mock_scenario = {
    "candidate_name": "Jan Testowy",
    "context": "Symulacja rozmowy w celu przetestowania promptu.",
    "tone": "Profesjonalny, ale przyjazny",
    "key_questions": [
        "Co skłoniło Cię do aplikacji?",
        "Jakie jest Twoje największe osiągnięcie?"
    ]
}

root_agent = create_interview_agent(mock_scenario)
