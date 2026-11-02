"""Immutable initial messaging DDL. Future changes belong in new migrations."""

import sqlalchemy as sa


def create(op):
    op.create_table("outbox_events",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("aggregate_id", sa.String(150), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("destination", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_type", "aggregate_id", "aggregate_version", name="uq_outbox_aggregate_event"))
    op.create_index("ix_outbox_events_status", "outbox_events", ["status"])
    op.create_index("ix_outbox_events_available_at", "outbox_events", ["available_at"])
    op.create_table("inbox_events",
        sa.Column("consumer", sa.String(100), primary_key=True),
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("message_replay_audits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("record_id", sa.String(36), nullable=False),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_message_replay_audits_record_id", "message_replay_audits", ["record_id"])


def drop(op):
    for table in ("message_replay_audits", "inbox_events", "outbox_events"):
        op.drop_table(table)
