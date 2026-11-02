"""Run regression tests, with no tolerated failures after the M10 contract refresh.

Any failure, collection error, missing report or interrupted run fails this command.
The report and pytest exit status remain visible; no test is marked xfail.
"""

from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
KNOWN_FAILURES = set()


def main():
    report = ROOT / "tmp/microservices-tests.xml"
    report.parent.mkdir(parents=True, exist_ok=True)
    # Use a unique report to avoid treating a stale previous run as this run's result.
    import tempfile
    with tempfile.TemporaryDirectory(prefix="cinema-pytest-") as directory:
        fresh = Path(directory) / "results.xml"
        result = subprocess.run([
            sys.executable, "-m", "pytest", "tests/contracts", "pipelines/tests", "gateway/tests", "tests/integration",
            "packages/python-platform/tests", "services/notification-service/tests",
            "services/ai-service/tests", "services/review-service/tests", "services/identity-service/tests", "services/catalog-service/tests", "services/cinema-service/tests", "services/booking-service/tests", "services/payment-service/tests", "services/reporting-service/tests",
            f"--rootdir={ROOT}",
            "-q", "--tb=short", f"--junitxml={fresh}",
        ], cwd=ROOT)
        if result.returncode not in {0, 1} or not fresh.exists():
            return result.returncode or 1
        report.write_bytes(fresh.read_bytes())
    cases = ET.parse(report).getroot().findall(".//testcase")
    unexpected = []
    known = []
    skipped = 0
    for case in cases:
        identity = (case.get("classname"), case.get("name"))
        if case.find("error") is not None:
            unexpected.append(identity)
        elif case.find("failure") is not None:
            (known if identity in KNOWN_FAILURES else unexpected).append(identity)
        skipped += case.find("skipped") is not None
    print(f"Regression report: {len(cases)} cases, {len(known)} recorded legacy failures, {len(unexpected)} unexpected failures, {skipped} skipped.")
    for identity in unexpected:
        print("UNEXPECTED:", "::".join(identity))
    return 1 if unexpected or not cases else 0


if __name__ == "__main__":
    raise SystemExit(main())
