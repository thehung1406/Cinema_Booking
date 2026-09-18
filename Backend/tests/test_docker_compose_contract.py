import re
import json
import shutil
import subprocess
from pathlib import Path

import pytest


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


def test_ai_overlay_resolves_paths_network_and_database():
    if not shutil.which("docker"):
        pytest.skip("Docker Compose CLI is required to validate the merged configuration")
    result = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE),
         "-f", str(BACKEND_ROOT.parent / "docker-compose.ai.yml"),
         "config", "--format", "json", "--no-env-resolution", "--no-interpolate"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    config = json.loads(result.stdout)
    worker = config["services"]["sentiment_worker"]
    assert Path(worker["build"]["context"]).resolve() == BACKEND_ROOT.resolve()
    assert (BACKEND_ROOT / worker["build"]["dockerfile"]).is_file()
    assert Path(worker["env_file"][0]["path"]).resolve() == (BACKEND_ROOT / ".env").resolve()
    artifact = next(v for v in worker["volumes"] if v["target"] == "/app/artifacts")
    assert Path(artifact["source"]).resolve() == (BACKEND_ROOT / "artifacts").resolve()
    assert artifact["read_only"] is True
    assert set(worker["networks"]) <= set(config["networks"])
    for service in ("fastapi", "celery_worker"):
        peer = config["services"][service]
        assert set(worker["networks"]) & set(peer["networks"])
        peer_environment = peer["environment"]
        if isinstance(peer_environment, list):
            peer_environment = dict(item.split("=", 1) for item in peer_environment)
        assert worker["environment"]["DATABASE_URL"] == peer_environment["DATABASE_URL"]
