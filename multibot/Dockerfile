FROM python:3.11-slim AS builder

WORKDIR /app

RUN pip install uv

COPY pyproject.toml .
COPY app/ app/

RUN uv sync --no-dev --frozen


FROM python:3.11-slim AS runtime

WORKDIR /app

RUN adduser --disabled-password --gecos "" appuser

COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
