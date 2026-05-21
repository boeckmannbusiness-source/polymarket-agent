FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml .
RUN mkdir -p backend && pip install --no-cache-dir -e ".[dev]"

COPY backend/app/ app/

ENV PYTHONPATH=/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000"]
