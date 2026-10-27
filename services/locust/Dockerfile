FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir locust==2.32.2
COPY . .
EXPOSE 8089
CMD ["locust", "-f", "locustfile.py"]
