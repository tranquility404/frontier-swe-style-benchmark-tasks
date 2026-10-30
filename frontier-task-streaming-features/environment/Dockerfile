FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app
COPY streaming_spec.md /app/streaming_spec.md
COPY episodes/ /app/episodes/
COPY stream_engine.py /app/stream_engine.py
RUN chmod +x /app/stream_engine.py
