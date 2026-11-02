"""Route ownership is explicit; each domain switches only after its cutover gate."""

import re

DOMAINS = {"identity", "catalog", "cinema", "booking", "payment", "review", "ai", "reporting"}


def owner(path: str) -> str:
    path = path.rstrip("/") or "/"
    if path == "/admin/catalog":
        return "legacy"  # GET is composed in the gateway when Catalog is enabled.
    if path == "/films/positive-trending" or re.match(r"^/films/[^/]+/(reviews(?:/.*)?|sentiment-summary)$", path):
        return "review"
    for domain, prefixes in (
        ("identity", ("/auth", "/access-control", "/admin/session", "/admin/employees")),
        ("review", ("/reviews",)),
        ("catalog", ("/films", "/food-items", "/admin/films", "/admin/food-items")),
        ("cinema", ("/theaters", "/cinema-rooms", "/showtimes", "/seat-types", "/admin/rooms", "/admin/showtimes", "/admin/prices", "/admin/cinema-operations", "/admin/theaters")),
        ("booking", ("/seats", "/bookings", "/tickets")),
        ("payment", ("/payment", "/admin/payment-reconciliation")),
        ("ai", ("/ai", "/admin/documents")),
        ("reporting", ("/admin/reports", "/admin/reports.csv")),
    ):
        if any(path == prefix or path.startswith(prefix + "/") for prefix in prefixes):
            return domain
    return "legacy"
