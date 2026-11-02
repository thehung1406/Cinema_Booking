# Identity v1

Public contract: [OpenAPI](../openapi/identity.v1.json). Gateway routes `/auth/*`, `/access-control/*`, `/admin/session`, `/admin/employees*` to Identity after cutover. HTTP paths, login form, user/employee/session shapes and refresh response are compatible with the existing frontend. Registration accepts only customer profile/password fields, always assigns USER, rejects role/status injection and enforces the existing employee password bounds (8–72 bytes).

## Token and session

Identity alone holds an HS256 signing key ring. Header `kid` selects an allowlisted key; algorithm is fixed, never selected from an arbitrary token. Required claims: `iss=cinema-identity`, `aud=cinema-api`, positive numeric string `sub`, `sid`, `jti`, `iat`, `nbf`, `exp`, `type=access|refresh`. Default access lifetime 15 minutes, session/refresh 7 days (configurable 1–30). A role claim is not authorization data.

Every authenticated decision validates signature, issuer, audience, expiry/type, the session row, current active account and current RBAC grants. Introspection is uncached; revocation/permission changes take effect at the next check after commit. Already authorized in-flight work is not retroactively canceled. HTTP timeout is 5 seconds; unavailable/invalid Identity response fails closed with 503. Public unauthenticated browsing remains available; an explicit invalid optional bearer cannot gain a user identity.

`/auth/refresh` accepts only the exact refresh token whose SHA256 digest is stored in that session; returns a fresh access token and preserves the original fixed refresh/session expiry. Logout revokes that session and all access tokens minted for it, plus its refresh token. Other login sessions remain active. Locking an account revokes all sessions; unlocking requires a fresh login. Expired tokens cannot be used to logout; refresh a valid session first. Expired rows may be removed after the retention interval without affecting expiry enforcement.

No legacy JWT, Redis refresh key or blacklist is imported. At M5 cutover all clients must sign in again with their existing credentials. This is an intentional one-time reset; no password reset or account recreation is required.

Rotation: add the new key to the ring in Identity, retain old key(s), then select the new `current_kid`. Tokens signed by a retained key keep working with current session/RBAC checks. Remove the old key after its last refresh/session lifetime has elapsed (or earlier to revoke that key's tokens). Consumers require no signing-key rollout. Session/signing-key backup must follow Identity DB/secret handling, never the frontend.

## Private API

All paths require `X-Service-Key` with at least 32 configured characters; gateway blocks `/internal`. TLS/mTLS remains a production deployment requirement; these Compose origins are private local HTTP.

| Method/path | Request | Response |
| --- | --- | --- |
| POST `/internal/v1/auth/introspect` | `{token}` | Unchanged Principal v1: `user_id`, `role`, `is_active`, `permissions` |
| POST `/internal/v1/auth/context` | `{token}` | Current profile plus `role_id`, `is_active`, `permissions`; for legacy protected routes |
| POST `/internal/v1/users/profiles` | `{user_ids:[...]}`, max 100 | Allowlisted `id,username,email,full_name,phone,role`; missing IDs omitted |
| GET `/internal/v1/migration/state` | — | `{writes_enabled}` |

No API response exposes hashes, session digests or stored tokens. Auth/profile payloads are never logged. Monolith holds no new signing key and has no Identity DB credential; AI, Review and Notification use Principal v1 directly. A temporary monolith introspection facade forwards to Identity when its persistent owner state is `service`, including if environment configuration was reset.

Booking stores `customer_full_name/customer_email/customer_phone` at creation. Historical orders/payment-confirmation/email use this snapshot, including during Identity outage. Migration backfills existing bookings before removing external user FKs. Review author display uses the profile API; purchase evidence remains Booking-owned. Locking an account preserves business histories. No hard-delete-user endpoint is introduced; future lifecycle/purge workflows must explicitly handle each owner's retention rules.
