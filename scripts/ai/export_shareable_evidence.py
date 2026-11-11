"""Publish a small allowlisted local evidence snapshot into Git-visible docs.

No model weights, raw user reviews, credentials, private environments or DB dumps.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
FINAL_GENERATION='rag-generation-final-normalized'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def canonical_trace():
    base=ROOT/'.local/evidence/advisor-v4'
    run=load(base/FINAL_GENERATION/'run.json')
    case=next(r for r in run['cases'] if r['id']=='genre-vi')
    trace=load(case['trace_file'])
    result=dict(stage=run['stage'],approval=run['approval'],created_at=run['created_at'],
        corpus_sha256={k:v for k,v in run['input_sha256'].items() if '/knowledge/' in k},
        question=trace['question'],scope=trace['scope'],strategy=run['strategy'],model=run['runtime']['model']['name'],
        runtime=run['runtime'],sources=trace['sources'],generation_trace=trace['generation_trace'],
        retrieval_ms=trace['retrieval_ms'],elapsed_seconds=trace['elapsed_ms']/1000,answer=trace['answer'],
        citation_ids_validated=trace['citation_ids_validated'],semantic_groundedness_human_reviewed=False)
    (base/'rag-in-out.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def plots(destination):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    base=ROOT/'.local/evidence/advisor-v4'
    rows=load(base/'bank-ablation/results.json')['summary']
    fig,ax=plt.subplots(figsize=(8,3.5))
    ax.bar([r['variant'] for r in rows],[r['macro_f1_mean'] for r in rows],
        yerr=[r['macro_f1_std'] for r in rows],capsize=5,color=['#35618D','#6C869D','#87A69B'])
    ax.set_ylim(0,.75)
    ax.set_ylabel('Validation Macro F1')
    ax.set_title('Bank adaptive follow-up, 3 paired seeds; neutral F1 = 0 for all')
    fig.tight_layout();fig.savefig(destination/'bank-ablation.png',dpi=170);plt.close(fig)
    before=load(base/'rag-generation/run.json')['summary']
    after=load(base/FINAL_GENERATION/'run.json')['summary']
    fig,ax=plt.subplots(figsize=(8,3.5))
    positions=[0,1]
    for shift,label,key,color in [(-.17,'Answer present, 14 expected answerable','answerable_development_answer_rate','#35618D'),
        (.17,'Abstained, 10 expected unanswerable','unanswerable_development_abstention_rate','#87A69B')]:
        ax.bar([x+shift for x in positions],[before[key],after[key]],width=.32,label=label,color=color)
    ax.set_xticks(positions,['Before guards','After guards and span IDs'])
    ax.set_ylim(0,1.22);ax.set_ylabel('Observed development rate');ax.legend(loc='upper center',fontsize=9)
    ax.set_title('AI-authored pilot, tuned on these cases; correctness not human-scored')
    fig.tight_layout();fig.savefig(destination/'rag-development-before-after.png',dpi=170);plt.close(fig)


def finish_report_inputs(target):
    """Generated inputs only; no private text or human decisions."""
    target=Path(target)
    old=ROOT/'.local/evidence/advisor-v3'
    for relative in ['research/research-evidence.json','research/error-summary.json','eda/tokenization-audit.json',
        'eda/token-lengths.png','figures/validation-matrix.png','figures/class-and-learning-uts2017-bank.png','kb/kb-chunks.jsonl']:
        if (old/relative).is_file():
            (target/relative).parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(old/relative,target/relative)
    hardware=load(old/'research/hardware.json')
    safe={k:hardware[k] for k in ('os','python','torch','transformers','cuda_runtime')}
    safe['gpu']={'name':hardware.get('gpu',{}).get('name')}
    (target/'research/hardware.json').write_text(json.dumps(safe,indent=2)+'\n',encoding='utf-8')
    ui=ROOT/'.local/evidence/portable-ui/report.json'
    if ui.exists():
        shutil.copy2(ui,target/'integration/portable-ui.json')
        for name in ('chat.png','seats.png'):
            shutil.copy2(ui.with_name(name),target/'integration'/('portable-ui-'+name))
    (target/'history').mkdir(exist_ok=True)
    for name in ('rag-in-out-dense-before-rerank.json','rag-in-out-rerank-initial.json'):
        shutil.copy2(old/name,target/'history'/name)
    source_paths=['services/ai-service/src/ai_service/'+name+'.py' for name in ('llm','grounding','rag','schemas')]
    source_paths+=['scripts/ai/benchmark_rag_answers.py','pipelines/ml/train_sentiment.py']
    (target/'source-code-at-export.json').write_text(json.dumps(dict(observed_at=datetime.now(timezone.utc).isoformat(),
        stage='post-run-export-check-not-a-pre-run-capture',normalization='Source spans use NFC whitespace normalization; PDF layout lines are joined and incomplete character-chunk boundary fragments are excluded.',
        sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in source_paths}),indent=2)+'\n',encoding='utf-8')
    junit=ROOT/'.local/evidence/ai-tests.xml'
    suite=ET.parse(junit).getroot()
    if suite.tag=='testsuites':
        suite=suite.find('testsuite')
    result={key:suite.get(key) for key in ('tests','failures','errors','skipped','time')}
    result.update(junit_sha256=hashlib.sha256(junit.read_bytes()).hexdigest(),broker='dedicated RabbitMQ test vhost and credential')
    (target/'integration/python-tests.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    files={str(p.relative_to(target)).replace('\\','/'):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in target.rglob('*') if p.is_file() and p.name!='SHA256SUMS.json'}
    (target/'SHA256SUMS.json').write_text(json.dumps(dict(created_at=datetime.now(timezone.utc).isoformat(),files=files),indent=2)+'\n',encoding='utf-8')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',default='docs/reports/evidence/2026-11-04')
    args=p.parse_args()
    target=(ROOT/args.output).resolve()
    if not target.is_relative_to((ROOT/'docs/reports/evidence').resolve()) or target.exists():
        raise ValueError('Use a new snapshot directory inside docs/reports/evidence')
    canonical_trace()
    target.mkdir(parents=True)
    def copy(source,name):
        source=Path(source);destination=target/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,destination)
    old=ROOT/'.local/evidence/advisor-v3'
    new=ROOT/'.local/evidence/advisor-v4'
    for name in ['validation-summary.json','validation-summary.csv','model-table-planned.csv','MODEL_TABLE.md','error-summary.json','VALIDATION_ERROR_ANALYSIS.md']:
        copy(old/'research'/name,'baseline/'+name)
    for path in (old/'figures').glob('*.png'):
        copy(path,'figures/baseline/'+path.name)
    for name in ['DATA_CARD.md','audit.json','distribution.png']:
        copy(old/'eda'/name,'eda/'+name)
    for name in ['knowledge-inventory.json','kb-page-sample.json','KB_SOURCES.md']:
        copy(old/'kb'/name,'kb/'+name)
    copy(new/'bank-ablation/protocol.json','bank-ablation/protocol.json')
    copy(new/'bank-ablation/results.json','bank-ablation/results.json')
    for path in (new/'bank-ablation/runs').glob('*/*/metadata.json'):
        for name in ('metadata.json','validation.json','training_arguments.json','model_config.json','training_history.json'):
            copy(path.with_name(name),'bank-ablation/runs/'+str(path.with_name(name).relative_to(new/'bank-ablation/runs')).replace('\\','/'))
    for path in (new/'rag-chunk-ablation').glob('*.json'):
        copy(path,'rag-chunk-ablation/'+path.name)
    for folder in ('rag-generation','rag-generation-guarded','rag-generation-spans','rag-generation-supported-spans','rag-generation-final',FINAL_GENERATION):
        exported_folder='rag-generation-final' if folder==FINAL_GENERATION else 'rag-generation-final-line-fragments' if folder=='rag-generation-final' else folder
        for path in (new/folder/'traces').glob('*.json'):
            copy(path,exported_folder+'/traces/'+path.name)
        run=load(new/folder/'run.json')
        for row in run['cases']:
            row['trace_file']='traces/'+Path(row['trace_file']).name
        (target/exported_folder/'run.json').write_text(json.dumps(run,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    copy(new/FINAL_GENERATION/'human-review.csv','rag-generation-final/human-review.csv')
    copy(new/'rag-in-out.json','rag-in-out.json')
    copy(new/'review-model-integration.json','integration/review-model-integration.json')
    copy(ROOT/'.local/portable-v2/result.json','integration/portable-stack.json')
    copy(ROOT/'.local/portable-v2/source-manifest.json','integration/portable-source-manifest.json')
    copy(ROOT/'.local/annotations/cinema-double-blind-v1/manifest.json','annotation/preparation-manifest.json')
    copy(ROOT/'.local/annotations/cinema-double-blind-v1/before-human-review/agreement.json','annotation/agreement-before-human-review.json')
    plots(target)
    (target/'README.md').write_text('''# Bằng chứng AI ngày 04 tháng 11 năm 2026

Các file này là kết quả thực đã xuất để đi theo repository. 18 run baseline thuộc ma trận chính 72 run; sáu run ablation là nghiên cứu bổ sung trên cùng Bank, không tăng số dataset hay tự đổi thành 24/72.

RAG có 24 câu do AI soạn và đã dùng để chỉnh hệ thống. Giữ cả lượt lỗi và các lần sửa; không gọi đây là gold độc lập. Trước guard có 6/10 câu thiếu thông tin vẫn được trả lời; bản cuối từ chối 10/10 và trả lời 14/14 câu dự kiến có đáp án. Đây chỉ là tỷ lệ trả lời/từ chối theo kỳ vọng phát triển, chưa phải accuracy hoặc chấm groundedness. Kiểm tra source span đúng không chứng minh diễn giải đúng nghĩa.

rag-generation-final/human-review.csv còn trống điểm và tên người chấm. Đường dẫn trace_file trong run.json tương đối với thư mục đó để đọc được sau khi pull. Các đường dẫn máy xuất hiện trong metadata huấn luyện là thông tin môi trường đã đo, không phải cấu hình cần sao chép.

integration/portable-stack.json kiểm tra bản copy chỉ gồm source Git nhìn thấy, DB/credential mới và model CPU Docker tự tải; chat thực trả card từ owner API. Chưa kiểm thử trên nhiều máy vật lý hay mọi hệ điều hành. Không dùng dữ liệu/tài khoản/thanh toán thật. Review model smoke dùng Bank artifact với Bank validation trong schema DB và RabbitMQ test, không chứng minh chất lượng cảm xúc phim.

Nguồn sách trích trong KB/context: John Reich, Exploring Movie Construction and Production, Open SUNY 2017, CC BY NC SA 4.0 trừ phần ghi chú riêng. Bản tóm tắt Cinematography theo Wikibooks contributors, CC BY SA 4.0, oldid 3335736. Giữ attribution và điều kiện nguồn trong từng metadata; không thay giấy phép của nguồn gốc. PDF tải lại bằng scripts/ai/fetch_knowledge_sources.py theo URL/SHA đã khóa.

Không có raw review, model weights, private env, token hay dump DB. SHA256SUMS.json kiểm tra nội dung snapshot. Phần thiếu và các quyết định cần người thật ở docs/AI_GVHD_CHECKLIST.md và docs/AI_HUMAN_REVIEW.md.
''',encoding='utf-8')
    files={str(p.relative_to(target)).replace('\\','/'):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in target.rglob('*') if p.is_file()}
    (target/'SHA256SUMS.json').write_text(json.dumps(dict(created_at=datetime.now(timezone.utc).isoformat(),files=files),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(files=len(files)+1,bytes=sum(r['bytes'] for r in files.values()),output=str(target))))
    finish_report_inputs(target)


if __name__=='__main__':
    main()
