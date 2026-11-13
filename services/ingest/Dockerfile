FROM python:3.11-slim
RUN apt-get update && apt-get install -y tesseract-ocr poppler-utils curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY services/ingest/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
COPY libs/ /app/libs/
COPY services/worker/ /app/services/worker/
COPY services/ingest/ /app/services/ingest/
ENV PYTHONPATH=/app
ENTRYPOINT ["python", "-m", "services.ingest"]
