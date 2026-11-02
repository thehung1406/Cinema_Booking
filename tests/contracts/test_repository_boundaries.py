"""Keep production and verification builds independent of the retired application."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_no_retired_application_or_bare_app_imports():
    assert not (ROOT / "Backend").exists()
    violations = []
    for folder in ["services", "gateway", "packages", "scripts", "tests", "pipelines"]:
        for path in (ROOT / folder).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.level == 0
                    and ((node.module or "").split(".")[0] in {"app", "main"})
                ):
                    violations.append(str(path.relative_to(ROOT)))
                if isinstance(node, ast.Import) and any(
                    a.name.split(".")[0] == "app" for a in node.names
                ):
                    violations.append(str(path.relative_to(ROOT)))
    assert not violations, violations


def test_verification_image_and_compose_use_only_owner_packages():
    source = (ROOT / "infra/compose/Dockerfile.tests").read_text()
    config = (ROOT / "infra/compose/compose.migration-tests.yml").read_text()
    assert "Backend/" not in source + config
    assert ".env:ro" not in config
    assert "/workspace:/workspace/pipelines" in config
    assert "source-schema/alembic.ini" in config
    assert "service-tests:" in config
