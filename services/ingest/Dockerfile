FROM python:3.11-slim
RUN apt-get update && apt-get install -y tesseract-ocr poppler-utils curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Download sentence-transformers model at build time
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
COPY . .
ENV PYTHONPATH=/app
ENTRYPOINT ["python", "-m", "ingest"]
