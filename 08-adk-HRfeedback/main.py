import os
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
import gradio as gr
from app_admin import demo as admin_demo
from app_candidate import demo as candidate_demo

print("Reloading main.py...")

app = FastAPI()

# Konfiguracja Auth dla Admina
# W Gradio mount_gradio_app auth jest przekazywane do launch(), ale tutaj montujemy aplikację.
# Gradio Blocks/Interface nie ma parametru auth w konstruktorze, tylko w launch().
# Jednak mount_gradio_app przyjmuje parametry launch().

# Montujemy aplikację admina pod "/admin" z autoryzacją
app = gr.mount_gradio_app(
    app, 
    admin_demo, 
    path="/admin",
    auth=("admin", "admin") # Prosta autoryzacja
)

# Montujemy aplikację kandydata pod "/candidate" aby uniknąć konfliktów routingu
app = gr.mount_gradio_app(app, candidate_demo, path="/candidate")

# Przekierowanie z głównego adresu "/" na "/candidate"
@app.get("/")
async def root(request: Request):
    query_params = request.query_params
    url = "/candidate"
    if query_params:
        url += f"?{query_params}"
    return RedirectResponse(url=url)

# Dodajemy prosty endpoint testowy, aby sprawdzić czy FastAPI działa
@app.get("/health")
def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    # Pobieramy port z env (dla Cloud Run) lub domyślnie 8080
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
