"""Live-model development smoke, explicitly separate from held-out evaluation."""
import argparse
from datetime import date
import json
from pathlib import Path
import time

from ai_service.config import Settings
from ai_service.schemas import ToolContext
from ai_service.llm import plan


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=".local/evidence/planner-pilot.json")
    parser.add_argument("--today", default=date.today().isoformat())
    args = parser.parse_args()
    settings = Settings(database_url="sqlite://", redis_url="redis://localhost/0",
                        llm_provider="ollama", llm_timeout_seconds=20)
    examples = ["Tối mai tôi muốn xem phim hài, hai người, tổng tiền vé dưới 250k, sau 19h.",
                "Thể loại phim kinh dị là gì?", "Giữ ghế và thanh toán hộ tôi nhé"]
    results = []
    for question in examples:
        started = time.perf_counter()
        try:
            output = plan(settings, question, ToolContext(), date.fromisoformat(args.today)).model_dump(mode="json")
            results.append(dict(question=question, output=output, seconds=time.perf_counter()-started))
        except Exception as error:
            results.append(dict(question=question, error=type(error).__name__, seconds=time.perf_counter()-started))
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"stage": "development-smoke-not-held-out-benchmark", "reference_date": args.today,
                                 "model": settings.llm_model, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=True))


if __name__ == "__main__":
    main()
