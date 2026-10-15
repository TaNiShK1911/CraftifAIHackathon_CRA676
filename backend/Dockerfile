FROM python:3.11-slim

WORKDIR /app

# No CUDA / GPU packages — the backend is CPU-only
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create data directory for SQLite and snapshots
RUN mkdir -p data/evidence data/snapshots

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
