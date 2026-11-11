"""Export only aggregate film-pilot evidence, never raw reviews/reviewer IDs."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'pipelines'))
from ml.evaluate_human_pilot import checked,load,sha,measure,LABELS
from ml.data import read_jsonl
from ml.auto_annotate import atomic_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,default=ROOT/'.local/annotations/cinema-ai-assisted-v1/evaluation-v1')
    p.add_argument('--output',type=Path,default=ROOT/'docs/reports/evidence/2026-11-04-film-human-pilot')
    args=p.parse_args();source=args.input;out=args.output
    protocol,rows=checked(source)
    if (protocol['human_label_counts']!={'negative':50,'neutral':27,'positive':23}
            or protocol['reviewer_count']!=1 or len({r['group_id'] for r in rows})!=99):
        raise ValueError('This dated narrative describes the frozen 100-case, single-reviewer pilot only')
    names=['qwen3-4b','lr','visobert','mbert','xlmr','videberta','phobert','lr-film-silver','visobert-film-silver']
    reports=[]
    for name in names:
        report=load(source/f'{name}-metrics.json')
        if report['count']!=len(rows):raise ValueError('Incomplete evaluation')
        predictions=read_jsonl(source/f'{name}-predictions.jsonl')
        if [r['id'] for r in rows]!=[r['id'] for r in predictions]:raise ValueError('Misaligned predictions')
        recalculated=measure([r['label'] for r in rows],[r.get('label') or 'abstain' for r in predictions])
        if any(report[k]!=recalculated[k] for k in ('correct','macro_f1','confusion_matrix')):
            raise ValueError('Metrics do not match frozen predictions')
        reports.append(report)
    out.mkdir(parents=True,exist_ok=True)
    for report in reports:atomic_json(out/(report['model']+'-metrics.json'),report)
    summary=dict(created_at=datetime.now(timezone.utc).isoformat(),stage=protocol['stage'],human_count=protocol['human_count'],
        reviewer_count=protocol['reviewer_count'],human_label_counts=protocol['human_label_counts'],
        human_snapshot_sha256=protocol['human_sha256'],partition_sha256=protocol['partition_sha256'],
        protocol_sha256=sha(source/'protocol.json'),prior_annotation_manifest_sha256=protocol['prior_annotation_manifest_sha256'],
        limitations=protocol['limitations'],primary_final_test_opened=False,production_promoted=False,
        primary_matrix_completed=18,primary_matrix_required=72,
        note='100-case development pilot, plus two supplementary silver-training runs; neither adds a cell to the primary four-dataset matrix.',
        qwen=dict(model=protocol['qwen']['model'],digest=protocol['qwen']['model_digest'],decoding=protocol['decoding'],
                  system_prompt=protocol['system_prompt'],gold_labels_sent_to_model=False))
    majority=measure([r['label'] for r in rows],['negative']*len(rows))
    summary['constant_negative_reference']=dict(majority,note='Descriptive reference, not a fitted or validated model.')
    atomic_json(out/'summary.json',summary)
    for filename in ('silver-pilot-preregistration.json',):
        atomic_json(out/filename,load(source/filename))
    for name in ('lr','visobert'):
        metadata=load(source/'models'/name/'metadata.json')
        atomic_json(out/f'{name}-silver-training-metadata.json',metadata)
        atomic_json(out/f'{name}-silver-validation.json',load(source/'models'/name/'validation.json'))
    test_log=source/'pipeline-tests.log'
    if test_log.exists():
        lines=test_log.read_text(encoding='utf-8').splitlines()
        atomic_json(out/'checks.json',dict(scope='pipelines/tests',result=lines[-1],log_sha256=sha(test_log),
            note='Focused research/annotation regression; does not claim a fresh complete microservice test run.'))
    with (out/'comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f)
        writer.writerow(['model','correct_of_100','accuracy_vs_one_human','macro_f1','negative_f1','neutral_f1','positive_f1','abstentions'])
        for r in reports:writer.writerow([r['model'],r['correct'],r['accuracy_vs_single_reviewer'],r['macro_f1'],
            *[r['per_class'][label]['f1'] for label in LABELS],r['abstentions']])
    with (out/'disagreements-to-review.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['model','row_id','human_label','predicted_label','human_error_category','second_reviewer_decision','notes'])
        for r in reports:
            for row,pred in zip(rows,read_jsonl(source/(r['model']+'-predictions.jsonl'))):
                label=pred.get('label') or 'abstain'
                if row['label']!=label:writer.writerow([r['model'],row['id'],row['label'],label,'','',''])
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    fig,axes=plt.subplots(1,2,figsize=(12,5),layout='constrained')
    labels=[r['model'] for r in reports];positions=np.arange(len(labels));width=.37
    axes[0].barh(positions-width/2,[r['accuracy_vs_single_reviewer'] for r in reports],height=width,label='Accuracy vs one human')
    axes[0].barh(positions+width/2,[r['macro_f1'] for r in reports],height=width,label='Macro F1 (3 classes)')
    axes[0].set_yticks(positions,labels);axes[0].set_xlim(0,1);axes[0].invert_yaxis();axes[0].legend(fontsize=8)
    axes[0].set_title('Film development pilot (n=100)')
    axes[1].bar(LABELS,[protocol['human_label_counts'][label] for label in LABELS]);axes[1].set_ylabel('Human labels');axes[1].set_title('One reviewer; enriched source sample')
    fig.savefig(out/'comparison-and-distribution.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(3,3,figsize=(13,10),layout='constrained')
    for ax,r in zip(axes.flat,reports):
        matrix=np.array(r['confusion_matrix']);ax.imshow(matrix,cmap='Blues',vmin=0,vmax=50)
        ax.set_xticks(range(4),['neg','neu','pos','abstain']);ax.set_yticks(range(3),['neg','neu','pos'])
        for i in range(3):
            for j in range(4):ax.text(j,i,str(matrix[i,j]),ha='center',va='center',color='white' if matrix[i,j]>25 else 'black')
        ax.set_title(r['model']);ax.set_xlabel('Predicted');ax.set_ylabel('Single human')
    fig.savefig(out/'confusion-matrices.png',dpi=160);plt.close(fig)
    lines=['# Đánh giá pilot cảm xúc phim sau 100 nhãn người thật','',
        'Ngày 04/11/2026. Đây là bằng chứng phát triển với **một người gán nhãn**, không phải final test hay nghiệm thu chất lượng sản phẩm.',
        '', '## Dữ liệu và cách đo','',
        '- Đã xác nhận 100/100 câu: 50 negative, 27 neutral, 23 positive; 99 họ văn bản.',
        '- Khóa bản chụp và SHA trước suy luận. Nhãn người, tên người và ghi chú không gửi Qwen.',
        '- Câu AI từ chối vẫn tính sai trong accuracy và recall; Macro-F1 giữ đủ ba lớp. Độ đúng trên riêng câu đã trả lời không thay thế chỉ số chính.',
        '- Bootstrap theo họ văn bản, 1.000 lần, seed 42; khoảng tin cậy chỉ mô tả mẫu này, không suy rộng thành độ đúng mọi bình luận phim.',
        '- Các mẫu được lấy từ bộ 600 cân bằng theo gợi ý nhà phát hành; phân bố nhãn người thực tế không cân bằng. Thiếu ID phim/tác giả, chỉ kiểm soát họ văn bản gần trùng.',
        '', '## Kết quả thật','',
        '| Mô hình | Khớp / 100 | Macro-F1 | F1 negative | F1 neutral | F1 positive | Từ chối |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in reports:lines.append(f"| {r['model']} | {r['correct']} | {r['macro_f1']:.4f} | "+' | '.join(f"{r['per_class'][label]['f1']:.4f}" for label in LABELS)+f" | {r['abstentions']} |")
    lines += ['', 'Quy tắc luôn đoán negative khớp 50/100 nhưng Macro-F1 chỉ 0,2222. Các mô hình Bank là 6 artifact seed 42 đã huấn luyện trên miền ngân hàng, không phải huấn luyện lại bằng 100 câu phim. Cả sáu model Bank có F1 neutral = 0 trên mẫu phim này; vì vậy accuracy 63% của ViSoBERT Bank không có nghĩa là nhận biết tốt đủ ba lớp.',
        '', '![So sánh và phân bố](evidence/2026-11-04-film-human-pilot/comparison-and-distribution.png)',
        '', '## Hai lượt huấn luyện silver bổ sung','',
        '426 bình luận thật mang nhãn **AI chưa được người duyệt** (140 negative, 161 neutral, 125 positive) chỉ dùng train. 36 quyết định người đã có từ trước (17/7/12) dùng chọn C hoặc checkpoint. 100 câu mới chỉ được suy luận sau khi lưu artifact. Đã kiểm tra ID, họ văn bản và near-duplicate giữa ba phần. Không sửa cờ nhãn AI để qua cổng dữ liệu human gold của benchmark chính.',
        '', 'LR thử C = 0,25 / 1 / 4 trên 36 câu phát triển; char TF-IDF n-gram 2–5, balanced, LBFGS. ViSoBERT pin revision theo config, 3 epoch, LR 2e-5, AdamW, batch 1, tích lũy 8, max length 256, seed 42. Chọn ViSoBERT dựa trên validation Bank đã có trước pilot; config đóng băng trước khi xem chỉ số 100 câu. Cấu hình chạy thật, số tham số, số bước, best checkpoint và SHA có trong metadata kèm theo.',
        '', 'Đây là hai lượt thử yếu giám sát, một seed; không tính thành hai ô hoàn tất của ma trận chính 4 dataset × 6 mô hình × 3 seed. Tập pilot đã phục vụ phát triển, không được dùng lại để tuyên bố final test độc lập.',
        '', '## Bất đồng và phần còn thiếu','',
        'Qwen có 45 câu không khớp nhãn người, gồm 10 câu từ chối; trong 50 câu người đánh negative, Qwen chuyển 17 câu sang neutral. Đây là bất đồng quan sát được, chưa phải kết luận người hay AI sai. Không tự sửa nhãn của bạn.',
        '', 'File `disagreements-to-review.csv` chỉ chứa ID/nhãn, để trống phân loại lỗi và quyết định người thứ hai. Muốn xem nội dung phải dùng dữ liệu local tương ứng; không đưa bình luận và danh tính người vào gói Git.',
        '', 'Chưa có người thứ hai để đo độ đồng thuận/adjudication. Chưa đủ cơ sở nhận toàn bộ 426 nhãn AI là gold hoặc bật model cảm xúc chính thức. Chưa có tập final phim độc lập. Benchmark chính giữ 18/72 lượt; ba dataset còn lại và 54 lượt chưa hoàn tất. Đánh giá KB/RAG độc lập là phần riêng, không được thay bằng 100 câu cảm xúc này.',
        '', '## Tái lập trên máy khác','',
        'Cài môi trường nghiên cứu theo `../AI_PORTABLE_SETUP.md`. Các lệnh dùng Python trong môi trường đó, PYTHONPATH gồm root và pipelines. Dữ liệu người thật không nằm trên Git: muốn tái lập đúng các chỉ số phải được chủ dữ liệu chia sẻ an toàn đúng snapshot/SHA. Có thể kiểm tra báo cáo công khai mà không tải model.',
        '', '```text',
        'python -m ml.evaluate_human_pilot --help',
        'python -m ml.train_film_silver_pilot --model lr --output .local/film-silver-rerun/lr',
        'python -m ml.train_film_silver_pilot --model visobert --output .local/film-silver-rerun/visobert',
        'python scripts/ai/report_human_pilot.py', '```',
        '', 'Dùng thư mục output mới khi huấn luyện lại; không ghi đè bằng chứng cũ. Hai lệnh train cần protocol, preregistration và snapshot được chia sẻ cùng dữ liệu. Không dùng artifact thí nghiệm này cho production nếu chưa qua duyệt.',
        '', 'Báo cáo Word/Gói bằng chứng trước mốc này là ảnh chụp lịch sử, không chứa kết quả mới của pilot. Tài liệu hiện tại và thư mục evidence đi kèm bổ sung kết quả, không sửa ngược số liệu quá khứ.', '']
    lines += ['## Bảng cấu hình hai lượt bổ sung (số thực chạy)', '',
        '| Mô hình | Đặc trưng | Kiến trúc | Encoder layer | Tham số | LR | Epoch | Batch / effective | Optimizer | Chọn trên validation |',
        '| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |']
    for name in ('lr','visobert'):
        m=load(source/'models'/name/'metadata.json');a=m['architecture'];t=m['training']
        feature='Char TF-IDF 2–5' if name=='lr' else 'Token IDs + mask, max 256'
        architecture='Multiclass logistic regression' if name=='lr' else 'ViSoBERT / XLM-R + classification head'
        layers=a['encoder_layers'] if a['encoder_layers'] is not None else 'N/A'
        lr=t['learning_rate'] if t['learning_rate'] is not None else 'N/A'
        epoch=t['epochs_completed'] if t['epochs_completed'] is not None else 'N/A (8 solver iterations)'
        batch='N/A' if name=='lr' else f"{t['batch_size']} / {t['effective_batch_size']}"
        selection=f"C={t['selected_C']}" if name=='lr' else f"step {t['global_step']}; best F1={t['best_validation_macro_f1']:.4f}"
        lines.append(f"| {name}-film-silver | {feature} | {architecture} | {layers} | {a['total_parameters']:,} | {lr} | {epoch} | {batch} | {t['optimizer']} | {selection} |")
    lines += ['', 'ViSoBERT hoàn tất 162 bước optimizer, chọn checkpoint cuối bằng validation. LR không có learning rate/epoch/batch theo nghĩa huấn luyện mini-batch; không tự điền các trường này bằng số dự kiến. Thời gian cục bộ gồm train/validation: LR 3,85 giây, ViSoBERT 71,56 giây; không dùng để kết luận tốc độ trên máy khác.',
        '', 'Kiểm tra hồi quy phần nghiên cứu/annotation sau thay đổi: `pipelines/tests` có 36 bài pass. Bằng chứng `checks.json` lưu SHA log. Đây không phải tuyên bố đã chạy lại toàn bộ test microservices ở mốc này.', '']
    (ROOT/'docs/reports/AI_FILM_HUMAN_PILOT_2026-11-04.md').write_text('\n'.join(lines),encoding='utf-8')
    files=sorted(path for path in out.iterdir() if path.is_file() and path.name!='SHA256SUMS')
    (out/'SHA256SUMS').write_text(''.join(f'{sha(path)}  {path.name}\n' for path in files),encoding='utf-8')
    print(json.dumps(dict(models=len(reports),human_count=len(rows),output=str(out))))


if __name__=='__main__':main()
