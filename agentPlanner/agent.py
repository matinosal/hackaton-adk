from google.adk.agents import Agent
from dotenv import load_dotenv
from storage import load_survey_text

load_dotenv()

MODEL = "gemini-2.0-flash-001"

def create_planner_agent():
  
  instruction = load_survey_text()
  
  return Agent(
    model=MODEL,
    name='agentPlanner',
    description='Asystent feedbacku HR, który pomaga w planowaniu i tworzeniu scenariuszy rozmów feedbackowych z kandydatami.',
    instruction=instruction
  )

