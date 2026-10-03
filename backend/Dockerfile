FROM python:3.11-slim AS backend

WORKDIR /app

COPY backend/pyproject.toml backend/
COPY backend/.venv backend/.venv/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-deps -e /app/backend

COPY backend/app ./app
COPY scripts ./scripts

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
