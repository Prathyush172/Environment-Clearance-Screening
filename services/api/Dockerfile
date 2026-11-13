FROM python:3.11-slim
WORKDIR /app
COPY services/api/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
COPY libs/ /app/libs/
COPY services/api/ /app/services/api/
COPY services/worker/ /app/services/worker/
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["uvicorn", "services.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
