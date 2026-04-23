FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml .
RUN uv pip install --system -e ".[dev]"

COPY src/ ./src/
COPY scripts/ ./scripts/
COPY alembic/ ./alembic/
COPY alembic.ini .

ENV PYTHONPATH=/app/src

CMD ["uvicorn", "ffl.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
