"""Prevent accidental credential leakage and conflicting API/worker image tags."""

import copy
import importlib.util
from pathlib import Path
import json
import pytest

spec = importlib.util.spec_from_file_location(
    "runtime_audit",
    Path(__file__).resolve().parents[2] / "scripts/dev/audit_runtime.py",
)
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


def configuration():
    services = {}
    for owner in runtime.OWNERS:
        api = owner + "-service" if owner != "notification" else "notification-api"
        services[api] = {
            "environment": {
                owner.upper()
                + "_DATABASE_URL": f"postgresql://{owner}_owner:synthetic@{owner}-db/owned"
            }
        }
        services[owner + "-db"] = {}
        services[owner + "-migrate"] = {}
    services["gateway"] = {
        "environment": {
            "GATEWAY_LEGACY_ENABLED": "false",
            "GATEWAY_ENABLED_DOMAINS": json.dumps(
                sorted(runtime.OWNERS - {"notification"})
            ),
        }
    }
    for owner in ["ai", "review"]:
        services[owner + "-service"]["environment"][
            owner.upper() + "_DIRECT_READS_ENABLED"
        ] = "true"
    return {"services": services}


def test_runtime_audit_rejects_foreign_credentials_without_printing_values():
    config = configuration()
    assert runtime.audit(config)["independent_domains"] == 9
    config["services"]["reporting-service"]["environment"][
        "REPORTING_DATABASE_URL"
    ] = "postgresql://booking_owner:do-not-print-private-value@booking-db/booking"
    with pytest.raises(ValueError) as error:
        runtime.audit(config)
    assert "foreign DB credential" in str(error.value)
    assert "do-not-print-private-value" not in str(error.value)


def test_runtime_audit_rejects_api_worker_builds_overwriting_the_same_tag():
    config = configuration()
    api = config["services"]["review-service"]
    api.update(
        image="cinema-review:local",
        build={
            "context": ".",
            "dockerfile": "services/review-service/Dockerfile",
            "target": "api",
        },
    )
    config["services"]["review-report-source"] = copy.deepcopy(api)
    del config["services"]["review-report-source"]["build"]["target"]
    with pytest.raises(ValueError, match="conflicting build targets"):
        runtime.audit(config)
    config["services"]["review-report-source"]["build"]["target"] = "api"
    assert runtime.audit(config)["verified"]
