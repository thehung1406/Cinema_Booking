"""Build the Word evidence report from measured local artifacts, without inventing results.

Run with the bundled document Python, after export_evidence/export_knowledge.
"""
import argparse
import json
import os
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION_START
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def configure(section, landscape=False):
    section.orientation = WD_ORIENT.LANDSCAPE if landscape else WD_ORIENT.PORTRAIT
    section.page_width, section.page_height = (Cm(29.7), Cm(21)) if landscape else (Cm(21), Cm(29.7))
    section.top_margin = section.bottom_margin = Cm(1.5)
    section.left_margin = section.right_margin = Cm(1.6)
    section.header_distance = section.footer_distance = Cm(.6)


def hyperlink(paragraph, label, url):
    link = OxmlElement("w:hyperlink")
    rid = paragraph.part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)
    link.set(qn("r:id"), rid)
    run = OxmlElement("w:r")
    props = OxmlElement("w:rPr")
    color = OxmlElement("w:color"); color.set(qn("w:val"), "174A72"); props.append(color)
    run.append(props)
    text = OxmlElement("w:t"); text.text = label; run.append(text); link.append(run)
    paragraph._p.append(link)


def table(doc, headers, rows, widths, size=9):
    result = doc.add_table(rows=1, cols=len(headers))
    result.autofit = False
    for column, width in zip(result.columns, widths): column.width = Cm(width)
    for cell, value in zip(result.rows[0].cells, headers): cell.text = str(value)
    repeat = OxmlElement("w:tblHeader"); result.rows[0]._tr.get_or_add_trPr().append(repeat)
    for row in rows:
        for cell, value in zip(result.add_row().cells, row): cell.text = str(value)
    borders = OxmlElement("w:tblBorders")
    for side in ["top", "left", "bottom", "right", "insideH", "insideV"]:
        item = OxmlElement("w:"+side); item.set(qn("w:val"), "single"); item.set(qn("w:sz"), "4"); item.set(qn("w:color"), "D9D9D9"); borders.append(item)
    result._tbl.tblPr.append(borders)
    for i, row in enumerate(result.rows):
        for column_index, (cell, width) in enumerate(zip(row.cells, widths)):
            cell.width = Cm(width); cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            props = cell._tc.get_or_add_tcPr()
            margins = OxmlElement("w:tcMar")
            for side in ["top", "left", "bottom", "right"]:
                margin = OxmlElement("w:"+side); margin.set(qn("w:w"), "70"); margin.set(qn("w:type"), "dxa"); margins.append(margin)
            props.append(margins)
            if i == 0 or i % 2 == 0:
                shade = OxmlElement("w:shd"); shade.set(qn("w:fill"), "E3EBF2" if i == 0 else "F5F7F9"); props.append(shade)
            for paragraph in cell.paragraphs:
                numeric_header = headers[column_index].lower()
                if column_index and any(term in numeric_header for term in
                        ["layer", "tham số", "rate", "epoch", "batch", "grad", "max len", "seed", "macro", "lệch chuẩn", "lr ban", "f1 ", "negative", "neutral", "positive", "tổng", "trung vị", "train ", "vượt", "tỷ lệ", "trang pdf", "điểm"]):
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                paragraph.paragraph_format.space_after = Pt(2)
                paragraph.paragraph_format.line_spacing = 1.05
                for run in paragraph.runs:
                    run.font.size = Pt(size); run.bold = i == 0
    doc.add_paragraph().paragraph_format.space_after = Pt(1)
    return result


def paragraph(doc, text, size=None):
    p = doc.add_paragraph(text)
    if size:
        for run in p.runs: run.font.size = Pt(size)
    return p


def page(doc, heading):
    heading_paragraph = doc.add_heading(heading, 1)
    heading_paragraph.paragraph_format.page_break_before = True


def append_kb_section(doc, kb, trace, root, evidence, output, show_visible_urls=False, compact_context=False):
    page(doc, "Chương 4 Nguồn KB và file PDF đã thu thập")
    for item in kb["inventory"]:
        source=item["source"]; doc.add_heading(source["title"],2)
        p=doc.add_paragraph(); hyperlink(p,"Mở nguồn đã thu thập",source["source_url"])
        if show_visible_urls:paragraph(doc,'URL nguồn: '+source['source_url'],9)
        if source.get("publisher_url"):
            p.add_run(" | ");hyperlink(p,"Trang nhà xuất bản",source["publisher_url"])
            if show_visible_urls:paragraph(doc,'URL nhà xuất bản: '+source['publisher_url'],9)
        paragraph(doc,f"Tác giả: {source['author']}. Phiên bản: {source['version']}. Ngôn ngữ: {source['language']}. Scope: {source['scope']}.")
        paragraph(doc,f"Giấy phép và điều kiện ghi nhận: {source['license']}. Trạng thái: draft, approved={item['approved']}. Block: {item['blocks']}; chunk: {item['chunks']}.")
        raw=item.get("raw_file",{})
        if raw:
            p=doc.add_paragraph(); p.add_run("File đã thu thập: "); hyperlink(p,raw["local_file"],os.path.relpath(root/raw['local_file'],Path(output).resolve().parent).replace('\\','/'))
            paragraph(doc,f"SHA 256: {raw['sha256']}",9)
            if raw.get("pdf_pages"): paragraph(doc,f"PDF có {raw['pdf_pages']} trang; dung lượng {raw['bytes']:,} byte. Số trang provenance là số trang PDF, có thể khác số in trong sách.")
    paragraph(doc, "PDF Open SUNY được tải từ mirror cơ sở giáo dục khi URL nhà xuất bản không tải được. Trích xuất 84 block trang có text; có 11 cảnh báo ít text, chưa OCR toàn bộ. Wikibooks là bản tóm tắt/dịch có attribution, không phải toàn bộ website. Nguồn nội bộ cần người phụ trách xác nhận chính sách.",9)

    page(doc, "Chương 4 Một trang output Knowledge Base")
    sample=kb["representative_chunk"]; prov=sample["provenance"]
    paragraph(doc, f"Bản xuất có {kb['document_count']} documents và {kb['chunk_count']} chunks, tạo bằng code AI Service trong SQLite RAM. Các tài liệu vẫn chưa được duyệt trong file gốc và KB live.")
    table(doc,["Trường", "Giá trị thực tế"],[
        ["source_id / version",sample["source_id"]+" / "+sample["version"]],
        ["chunk ID / document ID",f"{sample['id']} / {sample['document_id']}"],
        ["approved / scope",f"{sample['approved']} / {prov['scope']}"],
        ["PDF page / block",f"{prov.get('page_start')} / {prov.get('block_index')}"],
        ["Vị trí ký tự trong block",f"{prov['character_start']} đến {prov['character_end']}"],
        ["Embedding",f"{sample['embedding_version']}; {sample['embedding_dimension']} chiều"],
        ["Sáu tọa độ khác 0 đầu tiên","; ".join(f"{v['index']}: {v['value']:.4f}" for v in sample["embedding_nonzero_preview"])],
        ["Chunking",prov["chunking"]]], [5.3,12.4],9)
    doc.add_heading("Nội dung chunk nguyên văn",2)
    paragraph(doc,sample["text"],9.5)
    paragraph(doc,"source_id nhận diện nguồn qua các phiên bản; document_id/chunk ID thuộc bản replay này. block_index và vị trí ký tự bắt đầu từ 0; character_end không thuộc đoạn. page giúp quay lại PDF; approved kiểm soát nguồn được trả lời. Bảng chỉ xem trước sáu tọa độ vector; toàn bộ 256 giá trị nằm trong kb-chunks.jsonl. Đây là lexical hash JSON, khác embedding E5 tính điểm khi truy xuất.",9.5)
    p=doc.add_paragraph();hyperlink(p,"Đối chiếu trang PDF của chunk",sample["source_url"]+f"#page={prov['page_start']}")

    page(doc,"Chương 4 RAG kết nối KB và đầu vào thực tế")
    paragraph(doc,"Luồng: nguồn → trích text và provenance → chunk 1.200 ký tự → AI DB → lọc nguồn theo scope/ngày hiệu lực → truy xuất → kiểm tra dữ kiện cụ thể → source spans → Ollama → kiểm tra span và ánh xạ citation → trả câu trả lời. Giá/ghế/suất đọc qua owner API, không lấy từ KB tĩnh.")
    paragraph(doc,"Dense gửi query và nội dung chunk tới E5 qua /similarity. Hybrid kết hợp BM25 và dense bằng RRF; khi rerank, 20 ứng viên được BGE CrossEncoder chấm lại để lấy top 3. Chưa lưu chỉ mục dense bền vững hoặc dùng vector database. Draft chỉ được bật tạm trong RAM, không sửa DB live.")
    if trace.get("runtime",{}).get("reranker"):
        runtime=trace["runtime"]["reranker"]
        paragraph(doc,f"Runtime pilot: {runtime['reranker']}, revision {runtime['reranker_revision'][:12]}, {runtime['device']}, fp16={runtime['reranker_fp16']}, batch={runtime['reranker_batch_size']}, max length={runtime['reranker_max_length']}. Điểm reranker thể hiện mức liên quan, không phải xác suất câu trả lời đúng.",9.5)
    paragraph(doc,f"IN: {trace['question']} | scope={trace['scope']} | strategy={trace['strategy']} | model={trace['model']}")
    table(doc,["Thứ hạng", "Source và chunk", "Trang PDF", "Điểm"],[[i+1,s['source_id']+" / "+s['id'],s['provenance'].get('page_start','N/A'),f"{s['score']:.6f}"] for i,s in enumerate(trace['sources'])],[1.7,10.2,2.7,3.1],9)
    payload=trace["generation_trace"]["request_body"]
    doc.add_heading("System prompt thực gửi model",2)
    paragraph(doc,payload["messages"][0]["content"],9.5)
    paragraph(doc,f"Thông số: temperature={payload['options']['temperature']}, num_ctx={payload['options']['num_ctx']}, num_predict={payload['options']['num_predict']}, think={payload['think']}, stream={payload['stream']}. Trả JSON theo schema GroundedAnswer, mỗi câu có source_id.",9.5)
    paragraph(doc,"Context nguyên văn ở phần tiếp theo. Request_body, schema, response_content và ánh xạ span đến chunk nằm trong docs/reports/evidence/2026-11-04/rag-in-out.json, đi theo repository.",9.5)

    context=json.loads(payload["messages"][1]["content"])
    page(doc,"Chương 4 Context thực gửi model")
    paragraph(doc,"Question trong cùng request: "+context["question"],9.5)
    seen_sources=set()
    for i, source in enumerate(context["evidence"]):
        original=next(s for s in trace["sources"] if s["id"]==source["id"].split(':span:')[0])
        if compact_context:
            if original['id'] not in seen_sources:
                seen_sources.add(original['id'])
                p=paragraph(doc,f"Nguồn {original['id']}  PDF trang {original['provenance'].get('page_start','N/A')}",10)
                p.runs[0].bold=True;p.paragraph_format.keep_with_next=True
                p=doc.add_paragraph();hyperlink(p,'Đối chiếu nguồn và trang',original['url'])
                p.paragraph_format.space_after=Pt(3);p.paragraph_format.keep_with_next=True
            p=doc.add_paragraph();r=p.add_run(source['id']+'  ');r.bold=True;r.font.size=Pt(9.5)
            p.add_run(source['text']).font.size=Pt(9.5)
            p.paragraph_format.space_after=Pt(2);p.paragraph_format.line_spacing=1.04
            continue
        p=paragraph(doc,f"Evidence {i+1}  {source['id']}",9);p.paragraph_format.space_after=Pt(2)
        p.paragraph_format.keep_with_next=True
        p.runs[0].bold=True
        p=paragraph(doc,source["text"],9.5);p.paragraph_format.space_after=Pt(3);p.paragraph_format.line_spacing=1.03;p.paragraph_format.keep_with_next=True
        p=doc.add_paragraph();hyperlink(p,"Nguồn và trang gốc",original["url"]);p.paragraph_format.space_after=Pt(3)
    p=paragraph(doc,"Các evidence thuộc cùng một request. Payload model chỉ nhận ID và text; điểm truy xuất/provenance lưu cùng trace. Không truyền credential hoặc URL do model tự chọn.",9)
    p.paragraph_format.space_after=Pt(0)

    doc.add_heading("Chương 4 Đầu ra thực tế và giới hạn đánh giá",1)
    paragraph(doc,"OUT đã render từ JSON được kiểm tra schema:")
    paragraph(doc,trace["answer"])
    paragraph(doc,f"Thời gian truy xuất ấm: {trace['retrieval_ms']:.1f} ms; tổng lượt pilot: {trace['elapsed_seconds']:.2f} giây. Đây là một lần chạy local, không phải SLA. Lượt đầu khởi tạo embedding đã vượt timeout 8 giây; lần ghi trace dùng cache đã ấm.")
    doc.add_heading("Kiểm tra đã làm",2)
    paragraph(doc,"Schema JSON hợp lệ; citation ID nằm trong context. Các kiểm tra này chưa chứng minh từng phát biểu được nguồn hỗ trợ đúng nghĩa. semantic_groundedness_human_reviewed=false. Không có chữ ký người duyệt giả.")
    doc.add_heading("Những phần cần hoàn thành",2)
    paragraph(doc,"Lượt dense trước khi chỉnh đã trả lời nhầm sang kỹ thuật quay phim dù citation ID hợp lệ. Bản lỗi giữ tại rag-in-out-dense-before-rerank.json; bản hiện tại bổ sung reranker và prompt yêu cầu trả lời trực tiếp, tối đa hai câu. Đây là sửa trong giai đoạn phát triển trên câu pilot đã biết, chưa phải bằng chứng tổng quát hóa.",9.5)
    paragraph(doc,"Nhóm cần duyệt nguồn/chính sách trước khi đưa vào KB live; chuẩn bị gold query độc lập, gồm câu không trả lời được, và chấm correctness/groundedness/citation. Pilot hiện có cho thấy retriever vẫn có thể trả đoạn gần chủ đề khi thiếu câu trả lời; điểm similarity dương chưa đủ để quyết định answerability.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", default="docs/reports/evidence/2026-11-04")
    parser.add_argument("--supplement")
    parser.add_argument("--output", default="docs/reports/AI_GVHD_2026-11-04.docx")
    args = parser.parse_args()
    root = Path.cwd(); evidence = Path(args.evidence)
    supplement=Path(args.supplement) if args.supplement else evidence
    research = load(evidence/"research/research-evidence.json")
    kb = load(evidence/"kb/knowledge-inventory.json")
    trace = load(evidence/"rag-in-out.json")
    eda = load(evidence/"eda/audit.json")
    errors = load(evidence/"research/error-summary.json")
    doc = Document(); configure(doc.sections[0])
    for name in ["Normal", "Title", "Subtitle", "Heading 1", "Heading 2"]:
        style = doc.styles[name]; style.font.name = "Calibri"; style.font.color.rgb = RGBColor(0,0,0)
        style.font.size = Pt(10.5 if name == "Normal" else 18 if name == "Title" else 14 if name == "Heading 1" else 11)
        style.paragraph_format.space_after = Pt(7)
    doc.styles["Normal"].paragraph_format.line_spacing = 1.1
    for section in doc.sections:
        p = section.footer.paragraphs[0]; p.alignment = 2
        p.add_run("Cinema Booking | Minh chứng AI | ")
        field = OxmlElement("w:fldSimple"); field.set(qn("w:instr"), "PAGE"); p._p.append(field)
    doc.add_paragraph("Minh chứng triển khai và thực nghiệm AI Cinema Booking", "Title")
    paragraph(doc, "Báo cáo đối chiếu yêu cầu GVHD ngày 04 tháng 11 năm 2026")
    paragraph(doc, "Bản này cung cấp bảng cấu hình mô hình nằm ngang, nguồn KB và PDF đã thu thập, một trang output KB và IN OUT của RAG chạy thật. Kết quả lấy từ artifact trên máy; các phần pilot và chưa có dữ liệu được ghi riêng. Chưa đủ điều kiện nghiệm thu toàn bộ ma trận học thuật.")
    doc.add_heading("Kiến trúc và phạm vi", 1)
    paragraph(doc, "Web gọi Gateway. AI Service lập kế hoạch bằng Qwen3 qua Ollama, kiểm tra tham số rồi đọc Catalog, Cinema, Booking và Review qua API owner. AI chỉ tư vấn và đưa link chọn ghế; luồng ứng dụng tiếp tục giữ ghế, tạo đơn và thanh toán. Mỗi service có database riêng.")
    paragraph(doc, "Review Service quản lý review, worker cảm xúc có lease và quyết định nhãn của nhân viên. Huấn luyện diễn ra offline trong pipelines/ml; model chat, classifier cảm xúc và embedding có ba vai trò khác nhau.")
    doc.add_heading("Các bổ sung phục vụ báo cáo", 1)
    paragraph(doc, "Pipeline đã truyền learning rate từ config vào Trainer; ghi cấu hình thực chạy, kiến trúc, số layer, tham số, epoch hoàn tất, checkpoint được chọn và lỗi validation. LR lưu C và số vòng tối ưu; layer và epoch DL được ghi không áp dụng.")
    paragraph(doc, f"Ma trận chính có {len(research['completed_runs'])} lượt validation hoàn tất; sáu lượt ablation bổ sung được trình bày riêng ở cuối báo cáo. Final test: {'đã có file' if research['final_test_opened'] else 'chưa mở'}. KB gồm ba nguồn draft, chưa tự phê duyệt vào DB dự án. Trace sinh câu trả lời là pilot, chưa được người chấm groundedness.")
    paragraph(doc, "Code nền: 7d9ca6f; có thay đổi local. Manifest từng run giữ hash dữ liệu/code Python và môi trường. Tài liệu vận hành hiện hành: docs/AI_RUNBOOK.md; nguồn dữ liệu tải trực tiếp: docs/AI_DATA_SOURCES.md.")
    hardware_path=evidence/"research/hardware.json"
    if hardware_path.exists():
        hardware=load(hardware_path)
        paragraph(doc,f"Môi trường đo: {hardware['os']}; Python {hardware['python']}; PyTorch {hardware['torch']}; Transformers {hardware['transformers']}; GPU {hardware.get('gpu',{}).get('name','N/A')}; CUDA {hardware['cuda_runtime']}. Đây là thông số môi trường, chưa phải SLA hoặc benchmark tải.",9.5)

    configure(doc.add_section(WD_SECTION_START.NEW_PAGE), True)
    doc.add_heading("Chương 3 Bảng cấu hình mô hình dự kiến", 1)
    paragraph(doc, "Kiến trúc lấy từ config checkpoint đã pin; số tham số đếm trên classifier ba lớp bằng meta tensors, chưa chứng minh model đã được huấn luyện. Các giá trị LR và epoch ở bảng này là kế hoạch; kết quả thực chạy ở trang kế tiếp.")
    rows=[]
    for m in research["planned_models"]:
        names={"phobert":"PhoBERT", "visobert":"ViSoBERT", "videberta":"ViDeBERTa", "mbert":"mBERT", "xlmr":"XLM R", "lr":"LR"}
        architectures={"phobert":"RoBERTa encoder + head 3 lớp", "visobert":"XLM RoBERTa encoder + head 3 lớp",
            "videberta":"DeBERTa encoder + head 3 lớp", "mbert":"BERT encoder + head 3 lớp",
            "xlmr":"XLM RoBERTa encoder + head 3 lớp", "lr":"TF IDF + multinomial LogisticRegression"}
        rows.append([names[m["model_id"]], "TF IDF char 2–5" if m["model_id"] == "lr" else f"Token và mask; ngữ cảnh h={m.get('hidden_size', 'N/A')}; "+m["preprocessing"],
            architectures[m["model_id"]], m["encoder_layers"] or "N/A", f"{m['total_parameters']:,}" if m["total_parameters"] else "Theo vocabulary",
            m["learning_rate"] if m["learning_rate"] is not None else "N/A", m["epochs"] or "N/A",
            m["batch_size"] or "N/A", m["gradient_accumulation_steps"] or "N/A", m["max_length"] or "N/A",
            "LBFGS; chọn C" if m["model_id"] == "lr" else m["optimizer"]])
    table(doc, ["Mô hình", "Đặc trưng và xử lý", "Kiến trúc classifier", "Layer", "Số tham số", "Learning rate", "Epoch", "Batch", "Grad accum", "Max len", "Optimizer"],
        rows, [2.1,3.5,4.2,1.3,2.2,1.8,1.2,1.2,1.5,1.3,2.1], 9)
    paragraph(doc, "Batch hiệu dụng dự kiến = batch mỗi thiết bị × tích lũy gradient × số thiết bị = 1 × 8 × 1. Encoder layer không gồm embedding và classification head. Token ID là đầu vào; h là kích thước biểu diễn ngữ cảnh của encoder. LR là giá trị ban đầu; Trainer hiện dùng scheduler linear, warmup 0 và weight decay 0.")
    paragraph(doc, "PhoBERT dùng VnCoreNLP tách từ; các model còn lại dùng chuẩn hóa NFC/khoảng trắng. Cấu hình seed 17, 42, 73; chọn checkpoint theo Macro F1 validation, không chọn bằng test. Nguồn checkpoint và SHA config đầy đủ: research/research-evidence.json trong gói bằng chứng.")

    configure(doc.add_section(WD_SECTION_START.NEW_PAGE))
    doc.add_heading("Chương 3 Kết quả và cấu hình thực chạy", 1)
    rows=[]
    for result in research["validation_summary"]:
        runs=[r for r in research["completed_runs"] if r["dataset"]==result["dataset"] and r["model_id"]==result["model"]]
        training=runs[0].get("training") or {}
        rows.append([result["model"], result["seeds_completed"], f"{result['macro_f1_mean']:.4f}",
            f"{result['macro_f1_std']:.4f}" if result["macro_f1_std"] is not None else "N/A", training.get("learning_rate") or "N/A",
            training.get("epochs_completed") or "N/A", training.get("effective_batch_size") or "N/A"])
    table(doc,["Model", "Seed xong", "Macro F1 TB", "Độ lệch chuẩn", "LR ban đầu", "Epoch xong", "Batch hiệu dụng"],rows,[2.2,1.5,2.5,2.5,2.1,2.1,2.8])
    paragraph(doc, "Tất cả kết quả trên thuộc validation của UTS2017 Bank, không phải review phim. Lớp neutral chỉ có ba câu validation; cần đọc F1 từng lớp, không kết luận chỉ bằng accuracy. Các run thiếu không được tính bằng 0.")
    lr=next((r for r in research["completed_runs"] if r["model_id"]=="lr"),None)
    if lr:
        t=lr["training"]
        paragraph(doc,f"LR chọn C={t['selected_C']} trong {t['C_candidates']}, optimizer={t['optimizer']}, max_iter={t['max_iter']}; số vòng tối ưu của run minh họa seed {lr['seed']}: {t['iterations_completed']}. Số tham số LR thực fit: {lr['architecture']['total_parameters']:,}.",9)
    actual_rows=[]
    for result in research["validation_summary"]:
        runs=[r for r in research["completed_runs"] if r["dataset"]==result["dataset"] and r["model_id"]==result["model"]]
        actual_rows.append([result["model"], *[f"{sum(r['per_class'][label]['f1-score'] for r in runs)/len(runs):.4f}" for label in ["negative","neutral","positive"]], sum(r["error_count"] for r in runs)])
    table(doc,["Model", "F1 negative", "F1 neutral", "F1 positive", "Lỗi qua các seed"],actual_rows,[2.7,3.1,3.1,3.1,3.7])
    image=evidence/"figures/validation-matrix.png"
    if image.exists(): doc.add_picture(str(image),width=Cm(16))
    paragraph(doc, "Bảng ma trận giữ ô not run cho dữ liệu/model chưa có kết quả. Không có đủ năm transformer trên bốn dataset. Log, metadata và training_arguments.json lưu theo từng dataset/model/seed.", 9)

    page(doc, "Chương 3 Dữ liệu tiền xử lý và phân tích lỗi")
    rows=[]
    for split, stats in eda["splits"].items(): rows.append([split,stats["count"],*[stats["labels"].get(label,0) for label in ["negative","neutral","positive"]],stats["characters"]["median"]])
    table(doc,["Split", "Tổng", "Negative", "Neutral", "Positive", "Ký tự trung vị"],rows,[2.7,2,2.4,2.4,2.4,3.8])
    paragraph(doc, "Importer giữ test do tác giả phát hành; loại 162 câu train gần trùng với test và gom họ gần trùng trước khi chia validation. Chuẩn hóa Unicode NFC và khoảng trắng; không đổi nhãn thành nhãn nhóm. Raw train 1.977 câu; test 494 câu. Mọi ID bị loại được lưu trong source manifest.")
    image=evidence/"eda/distribution.png"
    if image.exists(): doc.add_picture(str(image),width=Cm(16.6))
    image=evidence/"figures/class-and-learning-uts2017-bank.png"
    if image.exists(): doc.add_picture(str(image),width=Cm(16.6))
    paragraph(doc, f"Có {errors['observation_count']} quan sát lỗi validation qua model/seed đã xuất; một câu có thể lặp qua các run. File chỉ giữ ID, nhãn thật và nhãn dự đoán, không xuất review riêng tư. Các nhóm lỗi phủ định, mỉa mai, không dấu cần người đọc phân loại; công cụ không tự ghi tên người chấm.", 9)

    if (evidence/"eda/tokenization-audit.json").exists():
        token_audit=load(evidence/"eda/tokenization-audit.json")
        page(doc,"Chương 3 Phân bố token theo từng mô hình")
        paragraph(doc,"Độ dài được đo sau chuẩn hóa và tách từ riêng của model, có tính special tokens. Max length 256 được cố định trước; thống kê test chỉ mô tả dữ liệu, không chạy dự đoán hoặc chọn tham số bằng test.")
        rows=[]
        for m in token_audit["models"]:
            s=m["splits"]["train"]
            rows.append([m["model"],s["median"],s["p95"],s["maximum"],s["over_max_length"],f"{s['truncation_rate']:.2%}"])
        table(doc,["Model", "Train median", "Train P95", "Train max", "Vượt 256", "Tỷ lệ"],rows,[2.8,3,2.6,2.5,2.5,2.3])
        doc.add_picture(str(evidence/"eda/token-lengths.png"),width=Cm(15))

    append_kb_section(doc,kb,trace,root,evidence,args.output)
    paragraph(doc,"Phần thực nghiệm cảm xúc còn thiếu dataset độc lập đủ điều kiện và ma trận đầy đủ. Nhóm ưu tiên nguồn tải trực tiếp thay VLSP; Shopee đã tải nhưng binary, corpus phim công khai đã chuẩn bị để người kiểm tra nhãn. Các lựa chọn này không được tự tính là bốn dataset ba lớp đã hoàn tất.")
    doc.add_heading("Đối chiếu code và đầu ra",2)
    table(doc,["Chức năng", "Code hoặc artifact"],[
        ["Config và thông số thực chạy","pipelines/ml/train_sentiment.py; benchmark.py; export_evidence.py"],
        ["Phân bố và hình thực nghiệm","dataset_audit.py; research_figures.py; evidence/advisor-v3"],
        ["KB và provenance","scripts/ai/export_knowledge.py; ai_service/rag.py"],
        ["Context và câu trả lời thực","llm.py; grounding.py; benchmark_rag_answers.py"],
        ["Checklist và nguồn dữ liệu","docs/AI_GVHD_CHECKLIST.md; docs/AI_DATA_SOURCES.md"]],[5,12.7],9)
    if (supplement/'bank-ablation/results.json').exists():
        from advisor_report_supplement import append_supplement
        append_supplement(doc,supplement,page,paragraph,table)
    # Bundled Word templates can inherit an accent rule on Title paragraphs.
    for element in [doc.styles.element, doc.element]:
        for border in list(element.xpath(".//w:pBdr")):
            border.getparent().remove(border)
    doc.styles["Title"].font.underline=False
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);doc.save(out)
    print(out.resolve())


if __name__ == "__main__":
    main()
