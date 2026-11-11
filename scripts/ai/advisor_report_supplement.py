"""Measured follow-up and portability sections for the AI Word evidence report."""
import json
from pathlib import Path
from docx.shared import Cm


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def append_supplement(doc,evidence,page,paragraph,table):
    ablation=load(evidence/'bank-ablation/results.json')
    page(doc,'Chương 3 Thực nghiệm bổ sung về learning rate và cân bằng lớp')
    paragraph(doc,'Đã chạy thêm sáu lượt ViSoBERT trên cùng Bank với seed 17, 42, 73. ViSoBERT được chọn sau khi xem baseline nên đây là phân tích thích nghi trên tập phát triển, chưa phải phép thử độc lập. Ma trận chính vẫn 18 trong 72 ô; sáu lượt phụ không bổ sung dataset hay tăng số ô đã hoàn tất.')
    table(doc,['Cấu hình','LR','Mean Macro F1','SD ba seed','Mean F1 neutral'],[
        [r['variant'],'1e-5' if r['variant']=='lower-lr' else '2e-5',f"{r['macro_f1_mean']:.6f}",f"{r['macro_f1_std']:.6f}",f"{r['neutral_f1_mean']:.4f}"] for r in ablation['summary']],
        [4.7,2,3.9,3.4,3.7],9)
    paragraph(doc,'sqrt-balanced dùng căn bậc hai của N chia support lớp trên train, chuẩn hóa để kỳ vọng trọng số bằng 1. Loss là mean trọng số nhân cross entropy, chia số mẫu để không triệt tiêu tác dụng khi microbatch bằng 1. LR thấp và trọng số lớp chưa cải thiện mean Macro F1; cả ba cấu hình vẫn có neutral F1 bằng 0. Validation chỉ có ba mẫu neutral nên không suy rộng kết luận chất lượng phim.')
    doc.add_picture(str(evidence/'bank-ablation.png'),width=Cm(17))
    paragraph(doc,'Đã lưu protocol trước khi chạy, cấu hình/loss/trọng số thực tế, lịch sử train, confusion và chênh lệch theo cặp seed. Không mở final test, không chọn model Bank đưa vào Review phim production.',9.5)

    page(doc,'Chương 4 Kiểm tra truy xuất và từ chối mở rộng')
    after=load(evidence/'rag-generation-final/run.json')['summary']
    paragraph(doc,'Bộ phát triển có 24 câu do AI soạn, gồm 14 câu dự kiến có đáp án và 10 câu thiếu thông tin. Ba cấu hình chunking 600 không overlap, 1200 không overlap và 1200 overlap 120 ký tự đã chạy với năm chiến lược. Các tỷ lệ trên bộ nhỏ này bằng nhau giữa ba cấu hình; chưa đủ cơ sở chọn chunking tối ưu.')
    retrieval=load(evidence/'rag-chunk-ablation/summary.json')['results']
    table(doc,['Chiến lược','Recall tại 3','MRR tại 3','Trả đoạn khi thiếu đáp án'],[
        [r['strategy'],f"{r['recall_at_k']:.4f}",f"{r['mrr_at_k']:.4f}",f"{r['unanswerable_retrieval_rate']:.2%}"] for r in retrieval if r['size_characters']==1200 and r['overlap_characters']==0],
        [4.3,3.7,3.7,6],9)
    paragraph(doc,'Reranker tìm đoạn liên quan chưa đủ để quyết định có câu trả lời. Bản generation đầu vẫn trả lời sáu trong mười câu thiếu thông tin. Đã thêm lọc số/năm/đơn vị cụ thể và kiểm tra source span; giữ từng bước lỗi/thay đổi trong snapshot. Kiểm tra literal span và ID không chứng minh diễn giải đúng nghĩa.')
    doc.add_picture(str(evidence/'rag-development-before-after.png'),width=Cm(17))
    paragraph(doc,f"Bản cuối chạy {after['completed']} câu, lỗi kỹ thuật {after['failed']}; có câu trả lời trên nhóm dự kiến answerable {after['answerable_development_answer_rate']:.0%}, từ chối trên nhóm dự kiến unanswerable {after['unanswerable_development_abstention_rate']:.0%}. Median {after['latency_ms_median']:.0f} ms, P95 {after['latency_ms_p95']:.0f} ms trong lượt local. Đây là các câu đã dùng để chỉnh code/prompt, không phải accuracy hay gold held out.",9.5)
    paragraph(doc,'human-review.csv còn trống tên/điểm. Nhóm cần đọc nguồn rồi chấm correctness, groundedness, citation, refusal; đồng thời soạn câu độc lập chưa dùng để phát triển.',9.5)

    page(doc,'Cài đặt trên máy khác và phần còn thiếu')
    portable=load(evidence/'integration/portable-stack.json')
    paragraph(doc,'Đã kiểm tra bản sao chỉ gồm file Git nhìn thấy, không mang env riêng, cache model hay volume DB cũ. Ollama Docker CPU tự tải model khớp digest; owner DB mới và web/API hoạt động. Đây là Linux containers trên host Windows hiện tại; chưa kiểm thử nhiều máy vật lý hay mọi hệ điều hành.')
    table(doc,['Kiểm tra','Kết quả thật'],[
        ['Chat model',portable['chat']['mode']],['Dữ liệu demo',f"{portable['demo']['films']} phim, {portable['demo']['showtimes']} suất, {portable['demo']['seats']} ghế"],
        ['Card hai người',portable['chat']['cards'][0]['minimum_total']+' VND'],
        ['Cache hoặc credential tác giả','Không sao chép'],['Thanh toán giả','Không tạo']], [6,11.7],9.5)
    ui=load(evidence/'integration/portable-ui.json')
    paragraph(doc,f"Trình duyệt thật: đăng nhập, hỏi model, thấy card, mở trang ghế; browser errors = {len(ui['browser_errors'])}. Không giữ ghế, tạo đơn hoặc gọi Payment.")
    checks=load(evidence/'integration/python-tests.json')
    paragraph(doc,f"Regression Python: {checks['tests']} bài, failures={checks['failures']}, errors={checks['errors']}, skipped={checks['skipped']}; có RabbitMQ riêng. Web unit, lint, build và portable UI đã qua. Luồng Review dùng artifact thật với Bank validation trong schema test, không giả danh người duyệt hay chứng minh chất lượng cảm xúc phim.")
    paragraph(doc,'Máy mới: python scripts/ai/local_stack.py prepare, sau đó up và status. Tạo admin riêng bằng admin, bổ sung references rồi demo khi muốn dữ liệu thử. Chi tiết ở docs/AI_PORTABLE_SETUP.md. Profile phục vụ chatbot/chọn ghế; Payment, Reporting, Notification theo runbook runtime riêng.')
    doc.add_heading('Nhóm cần hoàn thành',2)
    paragraph(doc,'Hai người đọc 600 review phim độc lập, người thứ ba phân xử bất đồng. Nhãn hiện chưa xác nhận, Cohen kappa ban đầu null. Mẫu cân bằng theo gợi ý không phải phân bố test tự nhiên. Còn dữ liệu/quyền cho ba dataset, 54 ô baseline, final test, duyệt KB và gold RAG độc lập trước khi nhận đủ yêu cầu học thuật.')
    paragraph(doc,'Source, cấu hình, script tải và snapshot gọn đã chuẩn bị để nhóm tự commit/pull. Không đưa secret/raw review/weights vào Git. Trợ lý chưa commit hoặc push; phần thiếu vẫn ghi trong checklist.')
