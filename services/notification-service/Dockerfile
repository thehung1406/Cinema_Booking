FROM python:3.11-slim
WORKDIR /app/service
COPY packages/python-platform /tmp/python-platform
RUN pip install --no-cache-dir /tmp/python-platform
COPY services/notification-service/ /app/service/
RUN pip install --no-cache-dir .
EXPOSE 8081
CMD ["uvicorn", "notification_service.main:application", "--factory", "--host", "0.0.0.0", "--port", "8081", "--no-proxy-headers", "--no-access-log"]
