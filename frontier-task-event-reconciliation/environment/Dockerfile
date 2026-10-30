FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app
COPY reconciliation_spec.md /app/reconciliation_spec.md
COPY episodes/ /app/episodes/
COPY reconcile.py /app/reconcile.py
RUN chmod +x /app/reconcile.py
