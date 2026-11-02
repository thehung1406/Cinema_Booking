"""Inspect resolved Compose in memory; never print environment values/secrets."""

import argparse, json, subprocess
from pathlib import Path
from urllib.parse import urlparse

OWNERS = {
    "identity",
    "catalog",
    "cinema",
    "booking",
    "payment",
    "review",
    "ai",
    "notification",
    "reporting",
}


def audit(config):
    services = config["services"]
    issues = []
    forbidden = {
        "fastapi",
        "postgres",
        "redis",
        "celery_worker",
        "celery_beat",
        "outbox-relay",
        "flower",
        "pgadmin",
    }
    image_builds = {}
    for name, service in services.items():
        build = service.get("build")
        if build and service.get("image"):
            spec = (build.get("context"), build.get("dockerfile"), build.get("target"))
            prior = image_builds.setdefault(service["image"], spec)
            if prior != spec:
                issues.append(name + ": shared image tag has conflicting build targets")
        env = service.get("environment", {})
        owner = name.split("-")[0]
        if name in forbidden:
            issues.append(name + ": legacy runtime enabled")
        if service.get("env_file"):
            issues.append(name + ": broad env_file import")
        for key, value in env.items():
            if "fastapi:8000" in str(value):
                issues.append(name + ": legacy origin " + key)
            if key.endswith("DATABASE_URL"):
                url = urlparse(value)
                if (
                    owner not in OWNERS
                    or url.hostname != owner + "-db"
                    or url.username != owner + "_owner"
                ):
                    issues.append(name + ": foreign DB credential " + key)
            if ("SIGNING_KEYS" in key or key == "SECRET_KEY") and owner != "identity":
                issues.append(name + ": identity signing key " + key)
            if (
                key.endswith(("HASH_SECRET", "TMN_CODE"))
                and value
                and name != "payment-service"
            ):
                issues.append(name + ": merchant credential " + key)
            if (
                key.endswith("SMTP_PASSWORD")
                and value
                and name != "notification-dispatcher"
            ):
                issues.append(name + ": SMTP credential " + key)
        if service.get("build", {}).get("dockerfile") == "Backend/Dockerfile":
            issues.append(name + ": legacy backend image")
    gateway = services["gateway"]["environment"]
    if str(gateway.get("GATEWAY_LEGACY_ENABLED")).lower() != "false":
        issues.append("gateway: legacy fallback enabled")
    if set(json.loads(gateway["GATEWAY_ENABLED_DOMAINS"])) != {
        "identity",
        "catalog",
        "cinema",
        "booking",
        "payment",
        "review",
        "ai",
        "reporting",
    }:
        issues.append("gateway: incomplete domain cutover")
    for domain in ["ai", "review"]:
        if (
            str(
                services[domain + "-service"]["environment"].get(
                    domain.upper() + "_DIRECT_READS_ENABLED"
                )
            ).lower()
            != "true"
        ):
            issues.append(domain + ": retired read facade remains enabled")
    for owner in OWNERS:
        api = owner + "-service" if owner != "notification" else "notification-api"
        if (
            api not in services
            or owner + "-db" not in services
            or owner + "-migrate" not in services
        ):
            issues.append(owner + ": independent API/store/migration missing")
    if issues:
        raise ValueError("; ".join(issues))
    return dict(
        verified=True,
        independent_domains=9,
        services=len(services),
        legacy_runtime=False,
        foreign_db_credentials=0,
        signing_provider_smtp_role_isolation=True,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compose", default="compose.yml")
    parser.add_argument("--env-file", default=".env.microservices")
    parser.add_argument("--output", default="tmp/runtime-audit.json")
    args = parser.parse_args()
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            args.env_file,
            "-f",
            args.compose,
            "config",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(
            "Compose configuration failed; inspect locally without publishing environment output"
        )
    report = audit(json.loads(result.stdout))
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
