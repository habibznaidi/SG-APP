FROM python:3.12-slim

WORKDIR /app

# Dependencies first so this layer is cached across code-only changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY frontend ./frontend

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Used locally by Docker/Compose and, in prod, by the platform's own
# health probe (App Runner / ECS) to decide whether to route traffic
# here and whether to restart the container.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
