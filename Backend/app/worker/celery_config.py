from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "cinema_booking",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.worker.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Ho_Chi_Minh",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Schedule periodic tasks
celery_app.conf.beat_schedule = {
    'cleanup-expired-bookings-every-minute': {
        'task': 'app.worker.tasks.cleanup_expired_bookings',
        'schedule': 60.0,  # Chạy mỗi 60 giây (1 phút)
    },
}
