"""Summarize real validation errors; qualitative diagnoses require a reviewer."""
import argparse
from collections import Counter
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    rows, supports = [], {}
    for path in sorted(Path(args.runs).glob("*/*/*/validation.json")):
        result = json.loads(path.read_text(encoding="utf-8"))
        dataset, model, seed = path.parent.parts[-3:]
        supports.setdefault(dataset, {label: result["per_class"].get(label, {}).get("support", 0)
                                      for label in ("negative", "neutral", "positive")})
        for error in result.get("errors", []):
            rows.append(dict(dataset=dataset, model=model, seed=int(seed), **error,
                human_error_category=None, human_reviewer=None))
    counts = Counter((r["dataset"], r["model"], r["expected"], r["predicted"]) for r in rows)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "validation-errors.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False)+"\n" for r in rows), encoding="utf-8")
    report = dict(stage="validation-error-counts-not-human-adjudication", observation_count=len(rows),
        note="The same sample can occur once per seed/model. No private review text exported.",
        confusions=[dict(dataset=d, model=m, expected=y, predicted=p, count=n) for (d,m,y,p),n in sorted(counts.items())])
    (output / "error-summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Phân tích định lượng lỗi validation", "",
        "Nội dung do công cụ tổng hợp từ dự đoán thật; chưa có người chấm loại lỗi ngôn ngữ. Một câu có thể xuất hiện ở nhiều model/seed, không được xem các lần lặp là mẫu độc lập.", "",
        "| Dataset | Model | Nhãn nguồn | Dự đoán | Số quan sát lỗi |",
        "| --- | --- | --- | --- | ---: |"]
    for item in report["confusions"]:
        lines.append("| " + " | ".join(str(item[k]) for k in ["dataset","model","expected","predicted","count"]) + " |")
    lines += ["", "## Nhận xét dựa trên kết quả", "",
        "- Đọc confusion theo nhãn nguồn và dự đoán, không suy mọi bất đồng là nhãn nguồn sai.",
        *[f"- {dataset}: support validation theo nhãn {counts}; nếu model bỏ sót toàn bộ neutral thì F1 neutral bằng 0. Đọc support cùng accuracy và Macro F1."
          for dataset, counts in sorted(supports.items())],
        "- Không so thời gian train để xếp hạng tốc độ khi có tải máy/cold download khác nhau. Các thời gian này được giữ làm bằng chứng chạy, chưa phải benchmark hiệu năng có kiểm soát.",
        "- Chưa đủ cơ sở quy lỗi thành phủ định/mỉa mai/không dấu chỉ từ confusion. Cột human_error_category và human_reviewer trong JSONL để trống, dành cho lượt đọc độc lập.",
        "- So sánh cân bằng lớp/threshold cần được chạy riêng trên validation; không điều chỉnh bằng final test hoặc đưa model ngân hàng vào ứng dụng phim.", ""]
    (output / "VALIDATION_ERROR_ANALYSIS.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"error_observations": len(rows)}))


if __name__ == "__main__":
    main()
