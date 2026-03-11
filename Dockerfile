FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./api ./api

# Запуск FastAPI
CMD ["uvicorn", "api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]