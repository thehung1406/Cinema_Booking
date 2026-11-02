FROM python:3.11-slim
WORKDIR /app
COPY gateway/requirements.txt /app/gateway/requirements.txt
RUN pip install --no-cache-dir -r gateway/requirements.txt
COPY gateway /app/gateway
EXPOSE 8080
CMD ["uvicorn", "gateway.app.main:app", "--host", "0.0.0.0", "--port", "8080", "--no-proxy-headers", "--no-access-log"]
