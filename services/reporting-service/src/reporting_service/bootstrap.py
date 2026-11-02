import argparse, json, hashlib
from datetime import datetime
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from cinema_platform.reporting import Fact, digest_facts
from .config import Settings, SOURCES
from . import projection


def bootstrap(engine, cfg, source, http=None):
    own = http is None
    http = http or httpx.Client(timeout=30, trust_env=False)
    try:
        headers = {"X-Service-Key": cfg.service_key}
        origin = cfg.source_origins[source]
        response = http.post(
            origin + "/internal/v1/reporting/snapshots", headers=headers
        )
        response.raise_for_status()
        manifest = response.json()
        if manifest["source"] != source:
            raise ValueError("Wrong snapshot source")
        cursor = -1
        values = []
        while len(values) < manifest["count"]:
            page = http.get(
                origin + "/internal/v1/reporting/snapshots/" + manifest["snapshot_id"],
                headers=headers,
                params={"after": cursor, "limit": 250},
            )
            page.raise_for_status()
            page = page.json()
            if not page["items"] or page["next_cursor"] <= cursor:
                raise ValueError("Incomplete snapshot")
            values.extend(
                Fact.model_validate(row).model_dump(mode="json")
                for row in page["items"]
            )
            cursor = page["next_cursor"]
        if (
            len(values) != manifest["count"]
            or digest_facts(values) != manifest["sha256"]
        ):
            raise ValueError("Snapshot checksum mismatch")
        if any(
            v["source"] != source or v["generation"] != manifest["generation"]
            for v in values
        ):
            raise ValueError("Snapshot generation mismatch")
        if len({(v["kind"], v["key"]) for v in values}) != len(values):
            raise ValueError("Duplicate snapshot identity")
        # One local transaction seals the complete source snapshot. Stream replay
        # can run first/after: per-entity revisions keep the newer replacement.
        with Session(engine) as db, db.begin():
            state = projection.source_state(db, source, manifest["generation"])
            for value in values:
                projection.apply(db, value)
            state.bootstrapped = True
            state.verified_at = None
            state.snapshot_id = manifest["snapshot_id"]
            state.snapshot_sha256 = manifest["sha256"]
            state.snapshot_at = datetime.fromisoformat(manifest["as_of"])
            state.observed_at = projection.now()
        return dict(
            source=source, count=len(values), sha256=manifest["sha256"], verified=True
        )
    finally:
        if own:
            http.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=[*SOURCES, "all"], default="all")
    args = parser.parse_args()
    cfg = Settings()
    if cfg.writes_enabled:
        raise RuntimeError("Freeze Reporting bootstrap before cutover")
    engine = create_engine(cfg.database_url, pool_pre_ping=True)
    for source in SOURCES if args.source == "all" else [args.source]:
        print(json.dumps(bootstrap(engine, cfg, source)))


if __name__ == "__main__":
    main()
