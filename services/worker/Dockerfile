FROM python:3.11-slim
WORKDIR /app
COPY services/worker/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
COPY libs/ /app/libs/
COPY services/verifier/ /app/services/verifier/
COPY services/worker/ /app/services/worker/
ENV PYTHONPATH=/app
CMD ["celery", "-A", "services.worker.tasks.celery_app", "worker", "--loglevel=info", "--concurrency=2", "-Q", "screening"]
