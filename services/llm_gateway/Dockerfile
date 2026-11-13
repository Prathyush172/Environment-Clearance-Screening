FROM python:3.11-slim
WORKDIR /app
COPY services/llm_gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY libs/ /app/libs/
COPY services/llm_gateway/ /app/services/llm_gateway/
ENV PYTHONPATH=/app
EXPOSE 8002
CMD ["uvicorn", "services.llm_gateway.main:app", "--host", "0.0.0.0", "--port", "8002"]
