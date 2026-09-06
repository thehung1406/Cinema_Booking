import re
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = BACKEND_ROOT / "docker-compose.yml"


def _service_block(source: str, service_name: str) -> str:
    pattern = rf"^  {re.escape(service_name)}:\n(?:^    .*\n?)*"
    match = re.search(pattern, source, flags=re.MULTILINE)
    assert match is not None
    return match.group(0)


def test_compose_app_services_use_redis_service_hostname():
    source = COMPOSE_FILE.read_text(encoding="utf-8")

    for service_name in ("fastapi", "celery_worker", "celery_beat", "flower"):
        block = _service_block(source, service_name)
        assert "REDIS_HOST=redis" in block
        assert "REDIS_URL=redis://redis:6379/0" in block
