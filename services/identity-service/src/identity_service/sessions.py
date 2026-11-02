"""Remove expired session rows; expiry is enforced even if cleanup has never run."""
import argparse
from datetime import timedelta
from sqlalchemy import create_engine, delete
from .config import Settings
from .models import LoginSession, utcnow


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--retention-days", type=int, default=30)
    args = parser.parse_args()
    if args.retention_days < 1:
        parser.error("Retention must be at least one day")
    engine = create_engine(Settings().database_url)
    with engine.begin() as conn:
        result = conn.execute(delete(LoginSession).where(
            LoginSession.expires_at < utcnow()-timedelta(days=args.retention_days)))
        print("Expired sessions removed:", result.rowcount)
    engine.dispose()


if __name__ == "__main__":
    main()
