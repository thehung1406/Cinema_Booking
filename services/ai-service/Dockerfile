FROM python:3.11-slim
WORKDIR /app/service
COPY packages/python-platform /tmp/python-platform
RUN pip install --no-cache-dir /tmp/python-platform
COPY services/ai-service/ /app/service/
RUN pip install --no-cache-dir .
EXPOSE 8082
CMD ["uvicorn", "ai_service.main:application", "--factory", "--host", "0.0.0.0", "--port", "8082", "--no-proxy-headers", "--no-access-log"]
