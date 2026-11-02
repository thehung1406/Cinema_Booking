"""Explicit, audited ownership transitions; the service state is terminal."""

import argparse
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.migration_ownership import DomainOwnership, OwnershipAudit


def set_owner(db, owner, reason, *, domain="ai", actor="local-operator"):
    if owner not in {"monolith", "maintenance", "service"} or not reason.strip() or len(reason) > 500:
        raise ValueError("Valid state and audit reason required")
    row = db.execute(select(DomainOwnership).where(DomainOwnership.domain == domain).with_for_update()).scalar_one()
    if row.owner == "service" and owner != "service":
        raise ValueError("Transferred ownership cannot be reopened without explicit data reconciliation")
    if row.owner == "monolith" and owner == "service":
        raise ValueError("Freeze and verify migration before transferring ownership")
    if row.owner != owner:
        db.add(OwnershipAudit(domain=domain, old_owner=row.owner, new_owner=owner, actor=actor, reason=reason))
        row.owner, row.updated_at = owner, datetime.now(timezone.utc)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("owner", choices=["monolith", "maintenance", "service"])
    parser.add_argument("--reason", required=True)
    parser.add_argument("--domain", choices=["ai", "review", "identity", "catalog", "cinema", "booking"], default="ai")
    args = parser.parse_args()
    with Session(engine) as db, db.begin():
        set_owner(db, args.owner, args.reason, domain=args.domain)
    print(args.domain, "ownership state:", args.owner)


if __name__ == "__main__":
    main()
