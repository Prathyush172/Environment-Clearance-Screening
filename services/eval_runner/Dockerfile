FROM python:3.11-slim
WORKDIR /app
COPY services/eval_runner/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY libs/ /app/libs/
COPY services/verifier/ /app/services/verifier/
COPY services/worker/ /app/services/worker/
COPY eval/ /app/eval/
ENV PYTHONPATH=/app
ENTRYPOINT ["python", "-m", "eval.run"]
