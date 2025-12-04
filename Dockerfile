FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if needed
# RUN apt-get update && apt-get install -y ...

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run expects the container to listen on port defined by PORT env var (default 8080)
ENV PORT=8080
ENV GRADIO_SERVER_NAME="0.0.0.0"

# Run the application
CMD ["python", "app_candidac.py"]
