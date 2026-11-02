"""Read-only local HTTP smoke and small latency comparison, never creates bookings."""

import argparse
import json
from pathlib import Path
from statistics import median
from time import perf_counter
from uuid import UUID

import httpx

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default="http://127.0.0.1:8000")
    parser.add_argument("--gateway", default="http://127.0.0.1:8080")
    parser.add_argument("--frontend", default="http://127.0.0.1:5173")
    parser.add_argument("--ai", help="AI origin after M3 cutover; verify routing instead of legacy body parity")
    parser.add_argument("--review", help="Review origin after M4 cutover")
    args = parser.parse_args()
    results = []
    with httpx.Client(timeout=10, trust_env=False, follow_redirects=False) as client:
        paths = ["/", "/films/", "/food-items", "/films/positive-trending", "/auth/me", "/admin/session"]
        if args.review:
            paths.remove("/films/positive-trending")
        if not args.ai:
            paths.append("/ai/conversations")
        for path in paths:
            direct = client.get(args.backend + path)
            proxied = client.get(args.gateway + "/api" + path)
            assert direct.status_code == proxied.status_code, (path, direct.status_code, proxied.status_code)
            assert direct.json() == proxied.json(), path
            UUID(proxied.headers["x-request-id"])
            results.append({"path": path, "status": proxied.status_code, "body_matches_backend": True})
        if args.ai:
            for path in ["/ai/conversations", "/admin/documents"]:
                direct = client.get(args.ai + path)
                proxied = client.get(args.gateway + "/api" + path)
                assert direct.status_code == proxied.status_code == 401
                assert proxied.headers.get("x-service-name") == "ai"
                results.append({"path": path, "status": 401, "owner": "ai", "auth_required": True})
            assert client.get(args.backend + "/ai/conversations").status_code == 410
            assert client.get(args.gateway + "/api/internal/v1/ai-read/ownership").status_code == 404
        if args.review:
            proxied = client.get(args.gateway + "/api/films/positive-trending")
            assert proxied.status_code == 200 and isinstance(proxied.json(), list)
            assert proxied.headers.get("x-service-name") == "review"
            assert client.get(args.backend + "/films/positive-trending").status_code == 410
            assert client.get(args.gateway + "/api/reviews/moderation/pending").status_code == 401
            assert client.get(args.gateway + "/api/internal/v1/review-read/ownership").status_code == 404
            results.append({"path": "/films/positive-trending", "status": 200, "owner": "review"})
        slash = client.get(args.gateway + "/api/films")
        assert slash.status_code == 307 and slash.headers["location"].startswith("/api/films/")
        assert client.get(args.gateway + "/health/ready").status_code == 200
        through_vite = client.get(args.frontend + "/api/food-items")
        assert through_vite.status_code == 200
        UUID(through_vite.headers["x-request-id"])
        timings = {}
        for name, url in [("backend", args.backend + "/food-items"), ("gateway", args.gateway + "/api/food-items")]:
            client.get(url).raise_for_status()
            samples = []
            for _ in range(20):
                started = perf_counter()
                client.get(url).raise_for_status()
                samples.append((perf_counter() - started) * 1000)
            timings[name] = {"requests": 20, "median_ms": round(median(samples), 2), "p95_ms": round(sorted(samples)[18], 2)}
    report = {
        "scope": "Read-only localhost smoke; sequential warm connections, not a load/SLA test.",
        "http_checks": results, "vite_proxy_to_gateway": True, "internal_slash_redirect": True,
        "latency": timings,
    }
    output = ROOT / "docs/migration/latency-smoke.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
