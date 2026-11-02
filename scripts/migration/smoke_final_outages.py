"""Read-only local outage drill; run as a short-lived Identity operator container.

The host stops/restarts only the selected local API/broker and supplies /tmp
markers. A temporary session on an existing admin is removed in finally. No
orders, charges, tickets, emails or customer accounts are created.
"""

import json, time
from datetime import timedelta
from pathlib import Path
from uuid import uuid4
import httpx
from sqlalchemy import create_engine, select, delete
from sqlalchemy.orm import Session
from identity_service.config import Settings
from identity_service.models import User, Role, LoginSession, utcnow
from identity_service.tokens import mint


def marker(name):
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        if Path("/tmp/" + name).exists():
            return
        time.sleep(0.2)
    raise TimeoutError(name)


def business(data):
    return {
        key: value
        for key, value in data.items()
        if key not in {"as_of", "watermarks", "stale"}
    }


def main():
    cfg = Settings()
    engine = create_engine(cfg.database_url)
    sid = str(uuid4())
    result = {}
    try:
        with Session(engine) as db:
            user = db.scalar(
                select(User)
                .join(Role)
                .where(Role.code == "ADMIN", User.is_active.is_(True))
                .order_by(User.id)
            )
            if user is None:
                raise RuntimeError(
                    "Existing active admin is required for read-only smoke"
                )
            uid = user.id
            db.add(
                LoginSession(
                    id=sid,
                    user_id=uid,
                    refresh_digest="0" * 64,
                    expires_at=utcnow() + timedelta(minutes=10),
                )
            )
            db.commit()
        token = mint(cfg, uid, sid, "access", utcnow() + timedelta(minutes=10))
        with httpx.Client(
            base_url="http://gateway:8080",
            timeout=10,
            trust_env=False,
            headers={"Authorization": "Bearer " + token},
        ) as http:
            path = "/api/admin/reports?start_date=2026-01-01&end_date=2026-12-31"
            baseline = http.get(path)
            baseline.raise_for_status()
            baseline = baseline.json()
            assert not baseline["stale"]
            Path("/tmp/ready").touch()
            marker("identity-down")
            assert http.get(path).status_code == 503
            assert http.get("/api/films/").status_code == 200
            assert http.get("/health/ready").status_code == 503
            result["identity_outage_fail_closed"] = True
            Path("/tmp/identity-checked").touch()
            marker("identity-restored")
            assert http.get(path).status_code == 200
            Path("/tmp/identity-recovered").touch()
            marker("ai-down")
            assert http.get("/api/ai/conversations").status_code in {502, 503, 504}
            assert http.get("/api/bookings").status_code == 200
            assert http.get("/health/ready").status_code == 200
            result["optional_ai_outage_preserves_core"] = True
            Path("/tmp/ai-checked").touch()
            marker("ai-restored")
            assert http.get("/api/ai/conversations").status_code == 200
            Path("/tmp/ai-recovered").touch()
            marker("broker-down")
            deadline = time.monotonic() + 85
            stale = False
            while time.monotonic() < deadline:
                response = http.get(path)
                response.raise_for_status()
                data = response.json()
                assert business(data) == business(baseline)
                assert http.get("/health/ready").status_code == 200
                if data["stale"]:
                    stale = True
                    break
                time.sleep(2)
            assert stale, "Broker outage must be visible in report freshness"
            result["broker_outage_preserves_projection_and_exposes_staleness"] = True
            Path("/tmp/broker-checked").touch()
            marker("broker-restored")
            deadline = time.monotonic() + 100
            while time.monotonic() < deadline:
                response = http.get(path)
                response.raise_for_status()
                data = response.json()
                assert business(data) == business(baseline)
                if not data["stale"]:
                    break
                time.sleep(2)
            else:
                raise AssertionError("Source checkpoints did not recover")
            result["broker_recovery_verified_all_sources"] = True
        Path("/workspace/tmp/m10-outage-result.json").write_text(
            json.dumps(result, indent=2) + "\n"
        )
        print(json.dumps(result), flush=True)
    finally:
        with engine.begin() as conn:
            conn.execute(delete(LoginSession).where(LoginSession.id == sid))
        engine.dispose()


if __name__ == "__main__":
    main()
