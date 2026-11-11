"""Chapter 3 progress report from 24 completed runs; no planned numbers as results."""
import argparse
import json
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm,Pt,RGBColor

from build_advisor_report import configure,table,paragraph,page,hyperlink,append_kb_section


def load(path):return json.loads(path.read_text(encoding='utf-8'))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence',type=Path,default=Path('docs/reports/evidence/2026-11-04-four-vi'))
    p.add_argument('--output',type=Path,default=Path('docs/reports/AI_GVHD_4_DATASET_2026-11-04.docx'))
    p.add_argument('--kb-evidence',type=Path,default=Path('docs/reports/evidence/2026-11-04'))
    args=p.parse_args();e=args.evidence;summary=load(e/'summary.json');config=load(e/'protocol.json')['config']
    if not summary['all_cells_completed'] or summary['completed']!=24 or summary['dataset_count']!=4:
        raise ValueError('All 24 real runs on four corpora are required')
    datasets=config['datasets'];models=config['models'];results=summary['results']
    names={'uts2017-bank':'Bank','uit-visfd-general':'ViSFD GENERAL','shopee':'Shopee','cinema-silver':'Phim silver'}
    short={'uts2017-bank':'B','uit-visfd-general':'V','shopee':'S','cinema-silver':'P'}
    def result(dataset,model):return next(r for r in results if r['dataset']==dataset and r['model']==model)
    audits={d['id']:load(e/'datasets'/d['id']/'audit.json') for d in datasets}
    sources={d['id']:load(e/'datasets'/d['id']/'source_manifest.json') for d in datasets}
    tokens={d['id']:load(e/'datasets'/d['id']/'tokenization-audit.json') for d in datasets}
    doc=Document();configure(doc.sections[0])
    for name in ('Normal','Title','Subtitle','Heading 1','Heading 2'):
        style=doc.styles[name];style.font.name='Calibri';style.font.color.rgb=RGBColor(0,0,0)
        style.font.size=Pt(11 if name=='Normal' else 19 if name=='Title' else 14 if name=='Heading 1' else 12)
        style.paragraph_format.space_after=Pt(7)
    doc.styles['Normal'].paragraph_format.line_spacing=1.08
    title_style=doc.styles['Title']
    for border in list(title_style.element.findall('.//'+qn('w:pBdr'))):border.getparent().remove(border)
    footer=doc.sections[0].footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    footer.add_run('Cinema Booking | So sánh bốn bộ dữ liệu | ')
    field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');footer._p.append(field)
    doc.add_paragraph('Báo cáo tiến độ thực nghiệm AI và Knowledge Base Cinema Booking','Title')
    paragraph(doc,'Báo cáo tiến độ phục vụ đợt nộp ngày 04 tháng 11 năm 2026')
    paragraph(doc,'Đã hoàn tất 24 lượt huấn luyện và đánh giá validation: năm Transformer và một baseline Logistic Regression trên bốn nguồn dữ liệu tiếng Việt, seed 42. Đây là kết quả chạy thật với dữ liệu và cấu hình được khóa trước khi huấn luyện. Báo cáo trình bày riêng nguồn nhãn, số lớp và giới hạn của từng bộ, để người đọc đánh giá được ý nghĩa của phép so sánh.')
    paragraph(doc,'Chương 3 cập nhật so sánh bốn corpus, bảng cấu hình ngang và hình từ kết quả thực. Chương 4 nối tiếp bằng chứng KB đa nguồn, PDF, một trang output và IN OUT RAG đã lưu ở mốc trước cùng ngày; không nhận là lượt RAG mới hoặc đánh giá độc lập đã hoàn tất. AI Service đọc dữ liệu động qua API của các service sở hữu; huấn luyện offline tách khỏi hệ thống đặt vé.')
    paragraph(doc,'Bank và ViSFD sử dụng nhãn nhà phát hành; Shopee giữ nhãn nhị phân do nhà phát hành cung cấp. Bộ phim dùng nhãn AI chưa được người duyệt để train, cùng nhãn người thật cho validation và pilot. Vì vậy bốn nguồn trong báo cáo này không được gọi là bốn bộ gold ba lớp. Ma trận ba seed với dữ liệu gold trong plan gốc vẫn là mục tiêu riêng, chưa được nhận hoàn tất bằng 24 lượt này.')
    doc.add_heading('Chương 3 Câu hỏi nghiên cứu và phạm vi',1)
    paragraph(doc,'Thí nghiệm xem các encoder tiếng Việt và đa ngôn ngữ khác nhau thế nào về nhận biết cảm xúc trên miền ngân hàng, sản phẩm và phim; đồng thời khảo sát trường hợp train bằng nhãn AI khi nhãn người còn ít. Mỗi mô hình được fine tune riêng trên từng dataset. Không phải một model Bank được đem suy luận trên bốn bộ rồi tính thành bốn lượt huấn luyện.')
    paragraph(doc,'PhoBERT dùng tách từ VnCoreNLP trước tokenization. ViSoBERT, ViDeBERTa, mBERT và XLM R dùng chuẩn hóa NFC và khoảng trắng. Các checkpoint được khóa commit SHA; classifier có số đầu ra đúng hai hoặc ba lớp. LR dùng char TF IDF n gram 2 đến 5 và Logistic Regression balanced. Đây là nghiên cứu fine tuning và tích hợp, không tự nhận kiến trúc DL mới.')
    paragraph(doc,'Chỉ so sánh thứ hạng trong cùng một dataset. Shopee không có lớp neutral; Macro F1 được tính trên hai lớp gốc. Không lấy trung bình các điểm hai lớp và ba lớp để tạo một bảng xếp hạng chung.')
    if (e/'hardware.json').is_file():
        hardware=load(e/'hardware.json')
        paragraph(doc,f"Môi trường thực nghiệm: {hardware['os']}; Python {hardware['python']}, PyTorch {hardware['torch']}, Transformers {hardware['transformers']}, CUDA {hardware['cuda_runtime']}; GPU {hardware.get('gpu',{}).get('name','N/A')}. Phiên bản thư viện từng run được trích từ pip freeze theo whitelist, không đưa env hoặc đường dẫn cài riêng vào hướng dẫn tái lập.",9.5)

    page(doc,'Nguồn dữ liệu và điều kiện sử dụng')
    source_rows=[['Bank','Ngân hàng','3','Nhãn nhà phát hành','Apache 2.0 theo card'],
        ['ViSFD GENERAL','Phản hồi smartphone','3','GENERAL do người gán theo tác giả','Tác giả công bố dùng nghiên cứu; không tự gán SPDX'],
        ['Shopee','Review sản phẩm','2','Nhãn nhà phát hành theo nội dung; chưa xác minh người gán từng dòng','Apache 2.0 theo card; quyền nền tảng chưa thẩm định độc lập'],
        ['Phim silver','Bình luận phim','3','Train bằng Qwen; validation và pilot do người xác nhận','CC BY 4.0 theo README nguồn']]
    table(doc,['Dataset','Miền','Lớp','Nguồn nhãn','Điều kiện đã ghi nhận'],source_rows,[2.5,2.7,.8,5.6,6.1],9.5)
    for d in datasets:
        s=sources[d['id']];paragraph(doc,names[d['id']]+':',10)
        url=s.get('source') or 'https://huggingface.co/datasets/undertheseanlp/UTS2017_Bank/tree/'+s['revision']
        hyperlink(doc.add_paragraph(),url,url)
        paragraph(doc,'Phiên bản: '+str(s.get('revision',s.get('version'))),9)
    paragraph(doc,'ViSFD chỉ giữ dòng có nhãn GENERAL được ghi rõ trong file gốc, không suy nhãn chung từ sao hoặc từ các aspect khác; thiếu GENERAL được loại, không chuyển thành neutral. Shopee chỉ dùng file review gốc, bỏ toàn bộ bản augmentation không dấu. Bộ phim có 136 quyết định của người thật ở hai phần phát triển, không giả danh người duyệt cho 426 nhãn AI.')

    page(doc,'Dữ liệu trước và sau chuẩn bị')
    table(doc,['Nguồn gốc','Quy tắc xử lý','Kết quả đưa vào nghiên cứu'],[
        ['Bank: train gốc 1.977, test 494','Loại 162 train gần test; chia phần còn lại theo họ văn bản','Train 1.543, validation 272; test 494 giữ nguyên'],
        ['ViSFD: 11.122 comment ABSA','Giữ 6.936 dòng có GENERAL; loại 15 mẫu train hoặc validation gần phần giữ lại','Train 4.852, validation 688, test 1.381; tổng 6.921'],
        ['Shopee: 9.599 review gốc','Không dùng augmentation; chia trọn họ gần trùng','Train 6.719, validation 1.440, test 1.440'],
        ['ViMovieABSA: 10.797 dòng nguồn','7.935 dòng hợp lệ overall; chọn 600 ứng viên phát triển theo protocol; 462 đưa AI, 38 giữ phát triển, 100 pilot','426 silver hợp lệ cho train; 36 nhãn người validation; 100 nhãn người pilot. Các câu trì hoãn hoặc họ dự phòng không ép thành neutral']
    ],[4.3,6.8,6.6],9.5)
    paragraph(doc,'Các số sau xử lý mô tả tập thực dùng, không nhận đã huấn luyện trên toàn bộ nguồn 10.797 hoặc 11.122 dòng. Chi tiết ID loại, file gốc, SHA, quy tắc chọn và source manifest được giữ trong bằng chứng. Không loại một mẫu chỉ vì dự đoán model sai trên validation.')
    paragraph(doc,'Chuẩn hóa NFC và khoảng trắng giữ lại dấu tiếng Việt, emoji và biểu đạt mang cảm xúc; không xóa phủ định hoặc stopword bằng một danh sách chung. TF IDF chỉ fit trên train. PhoBERT tách từ bằng VnCoreNLP trước tokenizer; các encoder còn lại không dùng tách từ này. Tokenizer của từng checkpoint tạo token IDs và attention mask, padding theo batch, truncation ở 256 token.')
    paragraph(doc,'LR không có learning rate, epoch hay batch DL. C được chọn từ 0,25; 1; 4 theo Macro F1 validation. Số vòng LBFGS và số đặc trưng của từng corpus được lưu trong metadata. Các encoder có 12 layer; embedding và classification head không tính thành encoder layer.')
    paragraph(doc,'Số tham số Transformer đếm trọng số và bias của encoder, embedding và head. LR đếm coef cộng intercept của classifier; vocabulary/IDF lưu riêng. Hệ nhị phân scikit learn dùng một vector logit và sigmoid, không nhân giả số trọng số thành hai vector chỉ vì có hai nhãn.',10)

    page(doc,'Phân bố dữ liệu trước khi đưa vào mô hình')
    rows=[]
    for d in datasets:
        for split,stats in audits[d['id']]['splits'].items():
            display='pilot phát triển' if d['id']=='cinema-silver' and split=='test' else split
            rows.append([names[d['id']],display,stats['count'],stats['labels'].get('negative',0),
                stats['labels'].get('neutral','N/A'),stats['labels'].get('positive',0),stats['characters']['median']])
    table(doc,['Dataset','Phần','Tổng','Negative','Neutral','Positive','Trung vị ký tự'],rows,[3.1,2.7,1.3,1.9,1.8,1.9,3],9.5)
    paragraph(doc,'Bảng thể hiện nhãn thực trong mỗi phần, không áp đặt tỷ lệ cân bằng. Bank có rất ít neutral nên Macro F1 phải đọc cùng F1 từng lớp và support. Dữ liệu phim được lấy từ 600 ứng viên vốn cân bằng theo gợi ý nhà phát hành, sau khi người thật xác nhận thì phân bố thay đổi; đây không phải mẫu ngẫu nhiên đại diện mọi bình luận phim.')
    paragraph(doc,'Train và validation được kiểm tra trùng ID, họ văn bản và gần trùng với ngưỡng SequenceMatcher 0,88. Với bộ có split chính thức, loại mẫu train gần validation hoặc test; giữ split test gốc trong phạm vi nhãn đã chọn. Shopee được chia khoảng 70 phần trăm train, 15 validation, 15 test theo cả họ văn bản. Không dùng ba split để tính thành ba dataset.')
    paragraph(doc,'Test của Bank, ViSFD và Shopee chưa dùng để đo chất lượng mô hình trong đợt này. Phần mang tên test trong thư mục phim là 100 câu pilot phát triển đã được dùng từ trước, phải ghi đúng tính chất này trong mọi bảng đánh giá; không gọi là final test độc lập.')

    configure(doc.add_section(WD_SECTION_START.NEW_PAGE),True)
    doc.add_heading('Bảng ngang cấu hình thực chạy',1)
    paragraph(doc,'Tất cả 24 artifact đã hoàn tất. Bảng lấy số layer và tham số trực tiếp từ model đang train; head hai lớp của Shopee được đếm riêng. Seed 42; train đầy đủ các phần đã chuẩn bị, không cắt lấy một vài batch làm kết quả. B là Bank, V là ViSFD, S là Shopee, P là phim.')
    rows=[]
    for m in models:
        runs=[result(d['id'],m['id']) for d in datasets];a=runs[0]['architecture'];t=runs[0]['training']
        if m['id']=='lr':
            params='; '.join(short[r['dataset']]+': '+f"{r['architecture']['total_parameters']:,}" for r in runs)
            arch='TF IDF + Logistic Regression';features='Char n gram 2–5; vocabulary fit train';layer='N/A';lr='N/A';epoch='N/A';batch='N/A';optimizer='LBFGS; C chọn val'
        else:
            params=f"3 lớp: {a['total_parameters']:,}\n2 lớp: {result('shopee',m['id'])['architecture']['total_parameters']:,}"
            arch=f"{a['model_type']} encoder\nh={a['hidden_size']}; heads={a['attention_heads']}\nclassification head 2 hoặc 3 lớp";features='Token IDs + attention mask; '+m['preprocessing']
            layer=a['encoder_layers'];lr=t['learning_rate'];epoch=str(t['epochs_completed']);batch='; '.join(sorted({str(r['training']['batch_size'])+'/'+str(r['training']['effective_batch_size']) for r in runs}));optimizer=t['optimizer']
        rows.append([m['id'],features,arch,layer,params,lr,epoch,batch,optimizer])
    table(doc,['Mô hình','Đặc trưng đầu vào','Kiến trúc','Layer','Số tham số','Learning rate','Epoch','Batch / hiệu dụng','Optimizer'],rows,
        [2,3.5,4.2,1.2,4.3,2,1.2,2.2,2.7],9.5)
    paragraph(doc,'Transformer dùng max length 256, AdamW, weight decay 0, scheduler linear, warmup 0; batch hiệu dụng giữ 8. Nếu thực sự hết VRAM, protocol cho giảm batch 4 xuống 2 hoặc 1 và tăng tích lũy tương ứng, đồng thời giữ log lỗi. Metadata từng lượt ghi batch, số bước và checkpoint thực dùng. Việc giảm batch chỉ xử lý bộ nhớ, không chọn theo điểm số.')

    configure(doc.add_section(WD_SECTION_START.NEW_PAGE))
    doc.add_heading('So sánh kết quả validation trên bốn dataset',1)
    rows=[]
    for m in models:rows.append([m['id'],*[f"{result(d['id'],m['id'])['macro_f1']:.4f}" for d in datasets]])
    table(doc,['Mô hình',*[names[d['id']] for d in datasets]],rows,[3.2,3.3,4.1,3.3,3.8],10)
    paragraph(doc,'Chỉ số trong bảng là Macro F1 trên validation, sau khi chọn epoch hoặc C bằng chính validation. Đây là so sánh phát triển; điểm có thể lạc quan hơn kết quả trên test chưa mở. Bộ phim chỉ có 36 mẫu validation nên chênh lệch nhỏ chưa chứng minh mô hình nào tốt hơn một cách ổn định.')
    doc.add_picture(str(e/'four-dataset-macro-f1.png'),width=Cm(17.6))
    for d in datasets:
        best=max([r for r in results if r['dataset']==d['id']],key=lambda r:r['macro_f1'])
        paragraph(doc,f"{names[d['id']]}: {best['model']} có Macro F1 validation quan sát cao nhất, {best['macro_f1']:.4f}. Nhận xét chỉ áp dụng cho split và seed đang báo cáo; không kết luận ưu thế tổng quát.",10)

    page(doc,'F1 từng lớp và tác động mất cân bằng')
    doc.add_picture(str(e/'per-class-f1.png'),width=Cm(17.6))
    paragraph(doc,'Neutral của Shopee không tồn tại nên không thêm mẫu hoặc gán điểm 0 cho lớp giả. Accuracy cần đọc cùng F1 từng lớp: một model ưu tiên lớp đông có thể có accuracy cao nhưng bỏ qua lớp ít mẫu. Các bảng này chưa thay thế kiểm chứng trên nhãn người độc lập hoặc đánh giá sản phẩm.')
    page(doc,'Bảng chi tiết accuracy và F1 từng lớp')
    paragraph(doc,'B là Bank, V là ViSFD GENERAL, S là Shopee, P là phim silver. N/A là không có lớp đó trong dataset, không phải chưa chạy.')
    rows=[]
    for d in datasets:
        for m in models:
            r=result(d['id'],m['id'])
            rows.append([short[d['id']],m['id'],f"{r['accuracy']:.4f}",*[f"{r['per_class'][label]['f1-score']:.4f}" if label in d['labels'] else 'N/A' for label in ('negative','neutral','positive')]])
    table(doc,['Bộ','Model','Accuracy','F1 negative','F1 neutral','F1 positive'],rows,[1,2.9,3,3.6,3.5,3.7],9.5)

    page(doc,'Diễn biến validation theo epoch')
    doc.add_picture(str(e/'validation-curves.png'),width=Cm(17.6))
    paragraph(doc,'Mỗi điểm được lấy từ training_history của lượt chạy thật, không vẽ đường lý tưởng hay tạo thêm epoch. Artifact cuối là checkpoint có Macro F1 validation tốt nhất trong ba epoch. LR không có đường theo epoch DL nên được so sánh bằng kết quả chọn C. Một seed không đủ để vẽ độ lệch chuẩn giữa seed hoặc khẳng định ý nghĩa thống kê.')
    history=load(e/'runs/cinema-silver/xlmr/42/training_history.json')
    points=[r for r in history if 'eval_macro_f1' in r];best=max(points,key=lambda r:r['eval_macro_f1']);last=points[-1]
    paragraph(doc,f"Ví dụ XLM R trên phim: F1 validation cao nhất {best['eval_macro_f1']:.4f} ở epoch {best['epoch']:.0f}; tại epoch {last['epoch']:.0f} là {last['eval_macro_f1']:.4f}. Bảng kết quả dùng checkpoint được chọn, không mặc định dùng trạng thái epoch cuối hoặc sửa đường cong để khớp một xu hướng mong muốn. Với validation 36 câu, cần thêm seed và đánh giá độc lập trước khi kết luận về mức ổn định.")

    for pair in (datasets[:2],datasets[2:]):
        page(doc,'Ma trận nhầm lẫn theo từng bộ dữ liệu')
        for d in pair:
            doc.add_picture(str(e/'datasets'/d['id']/'confusion-matrices.png'),width=Cm(16.7))
            paragraph(doc,names[d['id']]+' — hàng là nhãn tham chiếu, cột là nhãn dự đoán; dùng đúng hai hoặc ba lớp của bộ đó.',9)

    film_evaluation=e/'film-development-evaluation'
    if (film_evaluation/'protocol.json').is_file():
        page(doc,'Đối chiếu riêng với một trăm nhãn phim người thật')
        paragraph(doc,'Sáu artifact phim sau huấn luyện được suy luận bằng CPU trên cùng 100 câu người dùng đã hoàn tất. Các câu này không dùng train hoặc chọn epoch trong lượt so sánh mới; tuy nhiên mẫu đã được dùng phát triển từ trước nên vẫn ghi pilot, không biến thành final test độc lập. Một người đã xác nhận 50 negative, 27 neutral và 23 positive.')
        rows=[]
        for m in models:
            r=load(film_evaluation/(m['id']+'-metrics.json'))
            rows.append([m['id'],f"{result('cinema-silver',m['id'])['macro_f1']:.4f}",r['correct'],f"{r['macro_f1']:.4f}",
                *[f"{r['per_class'][label]['f1']:.4f}" for label in ('negative','neutral','positive')]])
        if (film_evaluation/'qwen-reference-metrics.json').is_file():
            r=load(film_evaluation/'qwen-reference-metrics.json')
            rows.append(['Qwen tham chiếu','N/A',r['correct'],f"{r['macro_f1']:.4f}",*[f"{r['per_class'][label]['f1']:.4f}" for label in ('negative','neutral','positive')]])
        table(doc,['Model','F1 val 36','Khớp / 100','F1 pilot 100','F1 neg','F1 neu','F1 pos'],rows,[2.6,2.5,2.6,2.7,2.4,2.4,2.5],9.5)
        paragraph(doc,'Hai cột Macro F1 trả lời hai câu hỏi khác nhau: validation 36 đã tham gia chọn C hoặc epoch, còn pilot 100 mô tả sự khớp với một người ở mẫu phát triển khác. Không chọn riêng cột tốt hơn rồi gọi là chất lượng cuối. Các file metrics giữ confusion, ID bất đồng và bootstrap theo họ văn bản; không tự kết luận nhãn người sai khi model không khớp.')
        paragraph(doc,'Những lượt train này vẫn dùng nhãn AI silver. Chưa có đồng thuận người thứ hai, final phim độc lập, hoặc đánh giá hiệu chỉnh xác suất/ngưỡng chuyển người duyệt, nên không tự bật model phim vào sản phẩm.')
        if (film_evaluation/'qwen-reference-metrics.json').is_file():
            paragraph(doc,'Qwen là kết quả tham chiếu đã chạy ở phase pilot trước trên đúng snapshot 100 câu, kiểm tra bằng SHA. Model có 10 câu từ chối, vẫn tính sai trong chỉ số chính; không chỉ tính trên các câu model chịu trả lời. Đây không phải thêm một lượt fine tune hoặc một model thứ bảy chạy đủ bốn dataset. Kết quả cho thấy học từ 426 nhãn Qwen chưa bảo đảm tái tạo được chất lượng của chính model gợi ý.',10)

    page(doc,'Kiểm tra token sau tiền xử lý thực tế')
    rows=[]
    for d in datasets:
        for m in tokens[d['id']]['models']:
            stats=m['splits']['train']
            rows.append([names[d['id']],m['model'],stats['median'],stats['p95'],stats['maximum'],f"{stats['truncation_rate']:.2%}"])
    table(doc,['Dataset','Tokenizer','Trung vị','P95','Dài nhất','Vượt 256'],rows,[3.4,2.9,2.6,2.3,2.7,2.8],9.5)
    paragraph(doc,'Độ dài được đo sau đúng bước chuẩn hóa hoặc tách từ của từng model, có special tokens, trước truncation. Câu dài đúng 256 không được tính là bị cắt. Max length 256 đã khóa trước huấn luyện; không xem thống kê test để chọn lại tham số. Audit có cả các split và histogram trong gói bằng chứng.')

    page(doc,'Phân tích lỗi và giới hạn của kết quả')
    paragraph(doc,'Ma trận nhầm lẫn và F1 cho phép xác định cặp lớp thường bị lẫn. File validation errors chỉ chứa ID, nhãn tham chiếu và nhãn dự đoán; cột phân loại lỗi định tính để trống cho người đọc xác nhận. Không suy đoán rằng một câu là mỉa mai, phủ định hay sai nhãn chỉ từ việc model không khớp nhãn.')
    for name in ('uts2017-bank','uit-visfd-general'):
        values=[(m['id'],result(name,m['id'])['per_class']['neutral']['f1-score']) for m in models]
        low=min(values,key=lambda x:x[1]);high=max(values,key=lambda x:x[1]);support=audits[name]['splits']['validation']['labels']['neutral']
        observation=f"Cả sáu mô hình có F1 neutral {low[1]:.4f}." if abs(low[1]-high[1])<1e-12 else f"F1 neutral quan sát từ {low[1]:.4f} ở {low[0]} đến {high[1]:.4f} ở {high[0]}."
        paragraph(doc,f"{names[name]} có {support} câu neutral trong validation. {observation} Chỉ số của lớp ít mẫu phải đọc cùng support; một điểm Macro F1 chung không thể hiện hết việc model có nhận ra neutral hay không.")
    shopee_best=max([r for r in results if r['dataset']=='shopee'],key=lambda r:r['macro_f1'])
    shopee_worst=min([r for r in results if r['dataset']=='shopee' and r['model']!='lr'],key=lambda r:r['macro_f1'])
    paragraph(doc,f"Trên Shopee, {shopee_best['model']} đạt Macro F1 {shopee_best['macro_f1']:.4f}, LR đạt {result('shopee','lr')['macro_f1']:.4f}, còn {shopee_worst['model']} đạt {shopee_worst['macro_f1']:.4f}. Vì vậy lựa chọn encoder phải dựa trên thực nghiệm từng miền; tên kiến trúc hoặc số tham số lớn chưa bảo đảm vượt baseline. Đây là quan sát một seed, chưa phải kết luận có ý nghĩa thống kê.")
    paragraph(doc,'Bộ phim có ít dữ liệu train và dùng nhãn silver; kết quả trên 100 câu người thật cho thấy phương án hiện tại còn hạn chế. Chưa có đối chứng train bằng 426 nhãn người tương ứng, nên chưa tách được ảnh hưởng riêng của số lượng dữ liệu, chất lượng nhãn và kiến trúc. Không gán nguyên nhân cho một yếu tố chỉ từ chênh lệch điểm giữa các bộ.')
    paragraph(doc,'Có bốn nguồn corpus độc lập về xuất xứ, nhưng mức giám sát và số lớp khác nhau. Nhãn Shopee chưa được nhóm xác minh cách gán từng dòng; nhãn phim train là silver từ Qwen. Vì vậy điểm số không chứng minh mọi nhãn train đúng hoặc model có thể phân loại review phim thật trong sản phẩm. Bộ phim chưa có đánh giá đồng thuận người thứ hai.')
    paragraph(doc,'Chưa mở test chính thức của ba bộ nhà phát hành; 100 câu phim là pilot đã dùng để phát triển. Chưa đo độ biến động ba seed cho ma trận mới. Không nhận 24 lượt này là hoàn tất toàn bộ plan gốc hoặc nghiệm thu final. Tuy vậy mỗi ô trong bảng so sánh bốn dataset đều có artifact và thông số thực chạy, không còn là ô dự kiến chưa train.')
    page(doc,'Tái lập sau khi pull source')
    paragraph(doc,'Các script fetch và prepare tải lại đúng revision hoặc version, giữ nguồn, checksum và split. Nhãn phim đi cùng source ở dạng ID và label; văn bản được khôi phục từ CSV gốc đã khóa SHA. Tên thật, ghi chú và thời điểm người duyệt không nằm trong snapshot chia sẻ. Pseudonym chỉ đại diện cho người đã xác nhận ở nguồn, không phải AI ký tên thay người.')
    paragraph(doc,'Bản khôi phục giữ nguyên thứ tự, văn bản đầu vào, nhãn và họ văn bản; hash toàn file JSONL khác vì đã bỏ trường riêng tư. Manifest ghi riêng semantic SHA và SHA file private gốc để không tuyên bố hai file giống từng byte. Có lệnh chạy LR bằng CPU; full Transformer có thể dùng CPU nhưng thời gian dài, nên ưu tiên môi trường GPU nghiên cứu.')
    paragraph(doc,'Đã kiểm chứng cả bốn nguồn trong container Linux CPU mới, tự tải nguồn và kiểm semantic SHA của đủ 12 split; không sử dụng annotation private, model cache hoặc DB trên host. Kết quả khớp đầu vào, nhãn, thứ tự và họ văn bản. Các bài pipeline cũng đã chạy trong Linux; kiểm chứng này xác nhận tái lập dữ liệu/công cụ, không tuyên bố đã train lại toàn bộ Transformer trên một máy vật lý thứ hai.')
    paragraph(doc,'Hướng dẫn chi tiết: docs/AI_FOUR_DATASET_COMPARISON.md. Bằng chứng công khai: docs/reports/evidence/2026-11-04-four-vi. Mỗi model có metadata, validation, cấu hình, lịch sử, code hash và checksum. Model weights, env và bình luận gốc không đưa vào Git.')
    provenance=e/'source-provenance-summary.json'
    if provenance.exists() and load(provenance)['hash_capture_races']:
        paragraph(doc,'Hồ sơ provenance giữ nguyên một trường hợp CLI ghi SHA tệp ở cuối lượt sau khi tham số segmenter không dùng cho model normalize được sửa. Cả hai bản CLI được lưu và khớp SHA; sidecar đánh dấu suy luận phiên bản đã nạp từ namespace thực lưu. Mã fitting, dữ liệu, siêu tham số và điểm số không thay đổi. Driver hiện chạy từ snapshot nguồn bất biến; không sửa metadata cũ để che lịch sử.',9.5)
    checks=e/'full-checks.json'
    if checks.exists():paragraph(doc,'Kiểm tra hồi quy: '+load(checks)['result']+'. Không commit hoặc push trong lượt triển khai này.')
    append_kb_section(doc,load(args.kb_evidence/'kb/knowledge-inventory.json'),load(args.kb_evidence/'rag-in-out.json'),
        Path.cwd(),args.kb_evidence,args.output,show_visible_urls=True,compact_context=True)
    page(doc,'Đối chiếu thiết kế microservices với code và bằng chứng')
    paragraph(doc,'Web gọi Gateway; AI Service lập kế hoạch với Qwen rồi kiểm tra dữ kiện động qua API của Catalog, Cinema, Booking và Review. Mỗi service sở hữu database riêng. KB giữ kiến thức tĩnh có nguồn và provenance; giá, ghế và suất chiếu lấy từ owner API. Trợ lý trả gợi ý và đường dẫn chọn ghế, không tự hoàn tất thanh toán.')
    table(doc,['Phần thiết kế','Code hiện hành','Bằng chứng đối chiếu'],[
        ['Chia dữ liệu và provenance','prepare_four_datasets.py; reproduce_cinema_labels.py; ml/data.py','Source manifest, 12 split semantic SHA; khôi phục cả bốn nguồn trong Linux'],
        ['Fine tune và cấu hình thật','ml/train_sentiment.py; ml/train_four_dataset.py; run_four_comparison.py','24 metadata, validation, training arguments/history; source snapshots và provenance'],
        ['Bảng và hình báo cáo','export_four_comparison.py; build_four_dataset_report.py','CSV, F1 từng lớp, confusion, learning curves, tokenization; Word này'],
        ['Nhập KB và provenance PDF','scripts/ai/prepare_knowledge.py; services/ai-service/src/ai_service/rag.py','Inventory ba nguồn, PDF 94 trang, chunk trang 26, 226 chunks'],
        ['RAG và trả lời có nguồn','ai_service/llm.py; grounding.py; rag.py','rag-in-out.json: query, điểm, context, output và source/page'],
        ['Tích hợp nghiệp vụ','ai_service/chat.py; recommendations.py; Booking private API','Owner contracts/tests, chatbot tư vấn suất và link chọn ghế; không bật classifier phim tự động']
    ],[3.8,7.2,6.7],9.5)
    paragraph(doc,'Bản này hoàn tất bảng so sánh trên bốn corpus theo phạm vi tiến độ đã công bố. Phần chưa hoàn tất gồm lặp ba seed của ma trận mới, final test độc lập, duyệt KB/chính sách và chấm RAG độc lập. Việc có một corpus train bằng silver và một corpus nhị phân cần được trình bày rõ với GVHD; không khẳng định thầy đã duyệt thay đổi phương án hoặc sản phẩm đã nghiệm thu.')
    for element in (doc.styles.element,doc.element):
        for border in list(element.xpath('.//w:pBdr')):border.getparent().remove(border)
    doc.styles['Title'].font.underline=False
    args.output.parent.mkdir(parents=True,exist_ok=True);doc.save(args.output)
    md=['# Báo cáo AI với so sánh trên bốn dataset tiếng Việt','',
        'Đã hoàn tất **24/24** lượt: 5 Transformer + LR × 4 corpus × seed 42. Đây là validation phục vụ báo cáo tiến độ, không phải final test. Ba nguồn dùng nhãn nhà phát hành; phim train bằng AI silver, validation/pilot có nhãn người thật. Shopee giữ hai lớp; ba bộ còn lại ba lớp. Không nhận là bốn bộ gold ba lớp hoặc hoàn tất protocol ba seed gốc.','',
        '| Model | '+ ' | '.join(names[d['id']] for d in datasets)+' |','| --- | ---: | ---: | ---: | ---: |']
    for m in models:md.append('| '+m['id']+' | '+' | '.join(f"{result(d['id'],m['id'])['macro_f1']:.4f}" for d in datasets)+' |')
    md += ['', 'Bảng là Macro F1 validation; mỗi ô từ model được fine tune riêng. Chọn epoch/C bằng validation nên không gọi các điểm này là kết quả test cuối độc lập.', '',
        '![Kết quả](evidence/2026-11-04-four-vi/four-dataset-macro-f1.png)','',
        'Cấu hình thực chạy, EDA, tokenization, confusion, per-class F1, learning curves và lỗi theo ID nằm trong thư mục evidence cùng SHA256SUMS. File Word cùng tên có phần Chương 3 mới và Chương 4 KB/RAG từ bằng chứng đã đo cùng ngày để ghép vào quyển. Hướng dẫn tái lập và điều chỉnh phạm vi: ../AI_FOUR_DATASET_COMPARISON.md.','']
    args.output.with_suffix('.md').write_text('\n'.join(md),encoding='utf-8')
    print(args.output)


if __name__=='__main__':main()
