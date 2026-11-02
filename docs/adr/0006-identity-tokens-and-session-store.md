# ADR 0006 — Identity owns signing keys and revocable PostgreSQL sessions

Status: accepted for M5 local migration, 02/11/2026. Refines [ADR 0002](0002-private-auth-and-service-template.md).

Move users/RBAC into a separate DB. Use the existing HS256 stack with a `kid` key ring, explicit issuer/audience, type and required timing/session claims; only Identity gets the new signing keys. Consumers continue to use authenticated, uncached introspection so account locking, logout and permission updates do not wait for access expiry. Private profile/context APIs replace user-table joins without sharing ORM models.

Store sessions and refresh digests in PostgreSQL alongside Identity rather than retaining Redis authentication dependencies. This gives one durable revocation authority and avoids migrating unversioned Redis keys or retaining legacy signing credentials. Legacy JWT/refresh sessions are invalidated at cutover, with controlled sign-in again; existing user IDs and bcrypt hashes are copied unchanged. Refresh returns only a new access token, preserving frontend compatibility and a fixed session deadline.

The target design's Redis auth cache and `UserAccessChanged` invalidation event are unnecessary for this uncached implementation. No cache consumer or invalidation event is claimed at M5. If a later latency decision adds caching, it must define bounded staleness/invalidation and introduce the producer/outbox/consumer contract before relying on cached access decisions. PostgreSQL is now the session store in the implemented structure.

Keep contact snapshots on bookings; remove legacy user FKs and reverse ORM links, including AI/Review archives. Source Identity tables get transactional DB write guards and an audited terminal ownership fence. Runtime callers cannot fall back to those archive tables once transferred. Identity access failure denies protected work; anonymous film/menu browsing and provider callbacks using existing booking snapshots are independent.

Key overlap/retirement, session expiry/logout and API details are in [Identity v1](../../contracts/internal/identity.v1.md). Production TLS/mTLS, distributed availability/load thresholds and hard-delete/purge workflows remain separate deliverables. No asymmetric JWT/public-key verification is introduced in this phase.
