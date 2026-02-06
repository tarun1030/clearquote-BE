FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "if [ \"${RUN_DB_SEED:-1}\" = \"1\" ] || [ \"${RUN_DB_SEED:-1}\" = \"true\" ]; then echo \"[entrypoint] Seeding Postgres (idempotent)...\"; python scripts/seed_dataset.py; else echo \"[entrypoint] Skipping seed (RUN_DB_SEED=${RUN_DB_SEED:-})\"; fi; echo \"[entrypoint] Starting API...\"; exec uvicorn main:app --host 0.0.0.0 --port 8000"]