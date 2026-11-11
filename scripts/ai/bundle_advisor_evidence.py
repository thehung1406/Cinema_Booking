"""Package an allowlist of report evidence and collected KB sources, without credentials/weights."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output", default=".local/evidence/advisor-v4/AI_GVHD_2026-11-04.zip")
    args=parser.parse_args()
    root=Path.cwd(); evidence=root/".local/evidence/advisor-v3"
    files={}
    def add(path, name):
        path=Path(path)
        if not path.is_file(): raise ValueError(f"Missing required evidence: {path}")
        files[name]=path
    add(root/"docs/reports/AI_GVHD_2026-11-04.docx", "AI_GVHD_2026-11-04.docx")
    add(root/".local/knowledge/raw/exploring-movie-construction.pdf", "sources/exploring-movie-construction.pdf")
    add(root/"pipelines/knowledge/sources.json", "sources/source-manifest.json")
    for path in (root/"pipelines/knowledge").glob("*.md"): add(path,"sources/"+path.name)
    for name in ["AI_GVHD_CHECKLIST.md","AI_DATA_SOURCES.md","AI_ARCHITECTURE.md","AI_RUNBOOK.md","AI_FEATURE_PLAN.md","AI_PORTABLE_SETUP.md","AI_HUMAN_REVIEW.md"]:
        add(root/"docs"/name, "docs/"+name)
    snapshot=root/'docs/reports/evidence/2026-11-04'
    for path in snapshot.rglob('*'):
        if path.is_file():add(path,'shareable-evidence/'+str(path.relative_to(snapshot)).replace('\\','/'))
    for name in ('compose.ai-local.yml','compose.ai-gpu.yml'):
        add(root/name,'code/'+name)
    for folder, patterns in {"research":["*.json","*.csv","*.md","validation-errors.jsonl"],
            "kb":["*.json","*.jsonl","*.md"], "figures":["*.png"], "eda":["*.json","*.md","*.png"]}.items():
        for pattern in patterns:
            for path in (evidence/folder).glob(pattern):add(path,folder+"/"+path.name)
    for path in evidence.glob("rag-*.json"): add(path,"rag/"+path.name)
    for path in (root/"pipelines/ml/runs/advisor-v3").glob("*/*/*/metadata.json"):
        for name in ["metadata.json","validation.json","training_arguments.json","model_config.json","training_history.json"]:
            candidate=path.with_name(name)
            if candidate.exists(): add(candidate,"runs/"+str(candidate.relative_to(root/"pipelines/ml/runs/advisor-v3")).replace("\\","/"))
    for path in (root/"pipelines/ml").glob("*.py"):add(path,"code/pipelines/ml/"+path.name)
    for path in (root/"pipelines/configs").glob("*.json"):add(path,"code/pipelines/configs/"+path.name)
    add(root/"pipelines/requirements-research.txt","code/pipelines/requirements-research.txt")
    for path in (root/"scripts/ai").glob("*.py"):add(path,"code/scripts/ai/"+path.name)
    for path in (root/"services/ai-service/src/ai_service").rglob("*.py"):
        add(path,"code/"+str(path.relative_to(root)).replace("\\","/"))
    manifest={name:{"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()} for name,p in sorted(files.items())}
    readme="""# Gói minh chứng AI Cinema Booking ngày 04 tháng 11 năm 2026

Mở AI_GVHD_2026-11-04.docx để đọc bảng mô hình nằm ngang, trang KB và trace RAG thật.
PDF đã thu thập nằm ở sources/exploring-movie-construction.pdf. Link nguồn HTTPS trong Word dùng được trên máy khác; đường dẫn local C:/code trong Word là vị trí trên máy làm dự án.

Các mục research, figures, eda và runs chứa kết quả validation thật. Có 18 run baseline trên một dataset và sáu run ablation bổ sung; ma trận chính vẫn 18/72, chưa đủ bốn dataset và chưa mở final test. shareable-evidence chứa snapshot đi theo Git, RAG cuối, lịch sử lỗi, nghiên cứu chunking và bằng chứng chạy CPU Docker từ source/DB mới. RAG là development pilot, chưa có người chấm groundedness.

docs/AI_GVHD_CHECKLIST.md liệt kê phần đã đủ/còn thiếu. docs/AI_DATA_SOURCES.md có link tải trực tiếp và cách duyệt review phim công khai. code/ chứa mã đối chiếu; cài và chạy toàn bộ dự án theo repository/runbook. Weights lớn và dữ liệu review gốc vẫn nằm trên máy làm dự án.

## Nguồn và giấy phép KB

Exploring Movie Construction and Production, John Reich / Open SUNY Textbooks, 2017: CC BY NC SA 4.0, trừ phần được ghi chú riêng. Giữ attribution và điều kiện của tài liệu nguồn; bản PDF được thu thập từ mirror cơ sở giáo dục ghi trong source-manifest.json.
Tóm tắt dịch Cinematography từ Wikibooks: attribution Wikibooks contributors, CC BY SA 4.0, permalink oldid 3335736. Hướng dẫn đặt vé do dự án soạn vẫn chờ duyệt nghiệp vụ.
Metadata từng chunk giữ tác giả/nguồn/license/page. Đây là tập hợp nhiều nguồn với điều kiện riêng; không thay giấy phép của tài liệu gốc.

Không có private env, token, credential DB, dữ liệu tài khoản dự án, ảnh render QA hoặc model weights trong gói. SHA256SUMS.json cho phép kiểm tra từng file.
"""
    target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(target,"w",compression=zipfile.ZIP_DEFLATED) as archive:
        for name,path in sorted(files.items()):archive.write(path,name)
        archive.writestr("README.md",readme.encode("utf-8"))
        archive.writestr("SHA256SUMS.json",json.dumps(dict(created_at=datetime.now(timezone.utc).isoformat(),files=manifest),indent=2))
    print(json.dumps({"output":str(target.resolve()),"files":len(files)+2,"bytes":target.stat().st_size}))


if __name__ == "__main__":
    main()
