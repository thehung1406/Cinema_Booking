"""Public report evidence for four Vietnamese corpora; require every run real."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'pipelines'))
from ml.auto_annotate import atomic_json
from ml.data import fingerprint,read_jsonl
from ml.dataset_audit import audit,write_report
from ml.evaluate_human_pilot import sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runs',type=Path,default=ROOT/'.local/research/four-vi-v1')
    p.add_argument('--output',type=Path,default=ROOT/'docs/reports/evidence/2026-11-04-four-vi')
    p.add_argument('--allow-incomplete',action='store_true',help='Explicit internal progress snapshot; never marked completed')
    args=p.parse_args();protocol=json.loads((args.runs/'protocol.json').read_text(encoding='utf-8'));config=protocol['config']
    records=[];missing=[]
    for dataset in config['datasets']:
        path=ROOT/dataset['path']
        if fingerprint(path)!=protocol['identity']['data_sha256'][dataset['id']]:raise ValueError('Frozen dataset changed')
        for model in config['models']:
            for seed in config['seeds']:
                folder=args.runs/'runs'/dataset['id']/model['id']/str(seed)
                files=['metadata.json','validation.json','comparison_protocol.json']
                if not all((folder/f).is_file() for f in files):
                    missing.append(dict(dataset=dataset['id'],model=model['id'],seed=seed));continue
                metadata=json.loads((folder/'metadata.json').read_text(encoding='utf-8'))
                result=json.loads((folder/'validation.json').read_text(encoding='utf-8'))
                if metadata['data_sha256']!=protocol['identity']['data_sha256'][dataset['id']] or metadata['labels']!=dataset['labels']:
                    raise ValueError('Run does not match frozen data/task')
                completed=json.loads((folder/'comparison_protocol.json').read_text(encoding='utf-8'))
                if completed['config_sha256']!=protocol['identity']['config_sha256']:raise ValueError('Run config differs')
                matrix=result['confusion_matrix'];classes=len(dataset['labels'])
                if len(matrix)!=classes or any(len(row)!=classes for row in matrix):raise ValueError('Wrong confusion label space')
                count=sum(map(sum,matrix));correct=sum(matrix[i][i] for i in range(classes))
                if count!=metadata['validation_count'] or len(result['errors'])!=count-correct:raise ValueError('Validation count/error mismatch')
                f1=[]
                for i in range(classes):
                    tp=matrix[i][i];fp=sum(matrix[j][i] for j in range(classes))-tp;fn=sum(matrix[i])-tp
                    f1.append(2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.)
                if abs(sum(f1)/classes-result['macro_f1'])>1e-12 or abs(correct/count-result['per_class']['accuracy'])>1e-12:
                    raise ValueError('Metrics do not match confusion matrix')
                record=dict(dataset=dataset['id'],model=model['id'],seed=seed,labels=dataset['labels'],supervision=dataset['supervision'],
                    accuracy=result['per_class']['accuracy'],macro_f1=result['macro_f1'],per_class=result['per_class'],
                    confusion_matrix=result['confusion_matrix'],label_order=result['label_order'],
                    architecture=metadata['architecture'],training=metadata['training'],model_version=metadata['model_version'],
                    train_count=metadata['train_count'],validation_count=metadata['validation_count'],
                    elapsed_seconds=result['elapsed_seconds'],metadata_sha256=sha(folder/'metadata.json'),
                    validation_sha256=sha(folder/'validation.json'),checkpoint_revision=metadata.get('revision'))
                records.append((record,folder))
    if missing and not args.allow_incomplete:raise ValueError(f'{len(missing)} missing cells; refusing a complete-report claim')
    args.output.mkdir(parents=True,exist_ok=True)
    atomic_json(args.output/'protocol.json',protocol)
    if (args.runs/'hardware.json').is_file():atomic_json(args.output/'hardware.json',json.loads((args.runs/'hardware.json').read_text(encoding='utf-8')))
    for dataset in config['datasets']:
        path=ROOT/dataset['path'];destination=args.output/'datasets'/dataset['id']
        report=audit(path)
        # Keep the primary audit's actual rejection of AI training labels. The
        # explicit weak-supervision protocol does not turn these labels to gold.
        write_report(report,destination)
        atomic_json(destination/'source_manifest.json',json.loads((path/'source_manifest.json').read_text(encoding='utf-8')))
        if (path/'task.json').exists():atomic_json(destination/'task.json',json.loads((path/'task.json').read_text(encoding='utf-8')))
        tokenization=args.runs/'tokenization'/dataset['id']
        if (tokenization/'tokenization-audit.json').is_file():
            atomic_json(destination/'tokenization-audit.json',json.loads((tokenization/'tokenization-audit.json').read_text(encoding='utf-8')))
            (destination/'token-lengths.png').write_bytes((tokenization/'token-lengths.png').read_bytes())
    for record,folder in records:
        destination=args.output/'runs'/record['dataset']/record['model']/str(record['seed']);destination.mkdir(parents=True,exist_ok=True)
        for filename in ['metadata.json','validation.json','comparison_protocol.json','source-provenance.json','training_history.json','training_arguments.json','model_config.json']:
            if (folder/filename).is_file():atomic_json(destination/filename,json.loads((folder/filename).read_text(encoding='utf-8')))
        environment=folder/'environment.txt'
        if environment.is_file():
            allowed={'torch','transformers','datasets','accelerate','scikit-learn','scipy','numpy','rapidfuzz','py-vncorenlp','tokenizers','safetensors','sentencepiece','protobuf'}
            versions={}
            for line in environment.read_text(encoding='utf-8').splitlines():
                package,separator,version=line.partition('==')
                if separator and package.casefold().replace('_','-') in allowed:versions[package.casefold().replace('_','-')]=version
            atomic_json(destination/'runtime-versions.json',dict(source_environment_sha256=sha(environment),packages=versions,
                note='Whitelist package versions from actual run pip freeze; editable paths and all environment variables excluded.'))
    for path in (args.runs/'source-snapshots').glob('*/ml/*.py'):
        destination=args.output/'source-snapshots'/path.relative_to(args.runs/'source-snapshots')
        destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(path.read_bytes())
    if (args.runs/'source-provenance-summary.json').is_file():
        atomic_json(args.output/'source-provenance-summary.json',json.loads((args.runs/'source-provenance-summary.json').read_text(encoding='utf-8')))
    if (args.runs/'source-freeze-check.json').is_file():
        atomic_json(args.output/'source-freeze-check.json',json.loads((args.runs/'source-freeze-check.json').read_text(encoding='utf-8')))
    summary=dict(stage=config['stage'],completed=len(records),required=len(config['models'])*len(config['datasets'])*len(config['seeds']),
        dataset_count=len(config['datasets']),all_cells_completed=not missing,missing=missing,seed_count=len(config['seeds']),
        scope=config['scope'],evaluation_stage='validation, not final test',primary_final_test_opened=False,production_promoted=False,
        protocol_sha256=sha(args.runs/'protocol.json'),results=[r for r,_ in records],
        validation_metrics_recomputed_from_confusion=True,all_data_and_config_fingerprints_verified=True,
        limitations=['Single seed; no across-seed variance or significance claim.',
            'Four distinct corpora do not mean four all-human three-class gold datasets.',
            'Shopee is binary; Macro-F1 uses its two original labels.',
            'ViSFD uses only explicitly human-labeled GENERAL aspect, not the full ABSA benchmark.',
            'Cinema trains on AI silver and selects on 36 earlier human development labels; its 100-case film pilot was already consumed.',
            'Best epochs and LR C are selected by these validation sets; results are exploratory and optimistic compared with untouched test.',
            'Original three-seed all-gold research protocol is retained separately; this progress comparison does not retroactively complete it.'])
    atomic_json(args.output/'summary.json',summary)
    film_evaluation=args.runs/'film-development-evaluation'
    if (film_evaluation/'protocol.json').is_file():
        destination=args.output/'film-development-evaluation';destination.mkdir(exist_ok=True)
        for file in film_evaluation.glob('*-metrics.json'):atomic_json(destination/file.name,json.loads(file.read_text(encoding='utf-8')))
        atomic_json(destination/'protocol.json',json.loads((film_evaluation/'protocol.json').read_text(encoding='utf-8')))
        prior=ROOT/'docs/reports/evidence/2026-11-04-film-human-pilot'
        if (prior/'summary.json').is_file():
            prior_summary=json.loads((prior/'summary.json').read_text(encoding='utf-8'))
            if prior_summary['human_snapshot_sha256']==protocol['identity']['data_sha256']['cinema-silver']['test']:
                atomic_json(destination/'qwen-reference-metrics.json',json.loads((prior/'qwen3-4b-metrics.json').read_text(encoding='utf-8')))
    with (args.output/'comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['dataset','model','seed','supervision','train_count','validation_count','accuracy','macro_f1','elapsed_seconds']
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(r for r,_ in records)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    matrix=np.full((len(config['models']),len(config['datasets'])),np.nan)
    for record,_ in records:
        i=next(i for i,m in enumerate(config['models']) if m['id']==record['model'])
        j=next(i for i,d in enumerate(config['datasets']) if d['id']==record['dataset'])
        matrix[i,j]=record['macro_f1']
    fig,ax=plt.subplots(figsize=(10,5),layout='constrained');cmap=plt.get_cmap('Blues').copy();cmap.set_bad('#eeeeee')
    image=ax.imshow(matrix,cmap=cmap,vmin=0,vmax=1,aspect='auto')
    dataset_names={'uts2017-bank':'Bank','uit-visfd-general':'ViSFD GENERAL','shopee':'Shopee (2 labels)','cinema-silver':'Film silver'}
    ax.set_xticks(range(len(config['datasets'])),[dataset_names[d['id']] for d in config['datasets']]);ax.set_yticks(range(len(config['models'])),[m['id'] for m in config['models']])
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            v=matrix[i,j];ax.text(j,i,'NOT RUN' if np.isnan(v) else f'{v:.4f}',ha='center',va='center',color='white' if v>.6 else 'black')
    ax.set_title('Validation Macro F1 by dataset\nSeed 42; label spaces and supervision differ',fontsize=11)
    fig.colorbar(image,ax=ax);fig.savefig(args.output/'four-dataset-macro-f1.png',dpi=170,bbox_inches='tight');plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(11,8),layout='constrained')
    for ax,dataset in zip(axes.flat,config['datasets']):
        name=dataset['id'];x=np.arange(len(config['models']));width=.24
        for i,label in enumerate(['negative','neutral','positive']):
            if label not in dataset['labels']:continue
            values=[next((r['per_class'][label]['f1-score'] for r,_ in records if r['dataset']==name and r['model']==m['id']),np.nan)
                if label in dataset['labels'] else np.nan for m in config['models']]
            ax.bar(x+(i-1)*width,values,width,label=label,color={'negative':'#4477AA','neutral':'#EE9944','positive':'#228833'}[label])
        ax.set_xticks(x,[m['id'] for m in config['models']],rotation=30);ax.set_ylim(0,1);ax.set_title(name+(' (binary, no neutral)' if len(dataset['labels'])==2 else ''))
    handles,labels=axes.flat[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='outside upper center',ncol=3,fontsize=9)
    fig.savefig(args.output/'per-class-f1.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(11,8),layout='constrained')
    for ax,dataset in zip(axes.flat,config['datasets']):
        for model in config['models']:
            history=args.output/'runs'/dataset['id']/model['id']/'42/training_history.json'
            if history.exists():
                points=[r for r in json.loads(history.read_text(encoding='utf-8')) if 'eval_macro_f1' in r]
                ax.plot([r['epoch'] for r in points],[r['eval_macro_f1'] for r in points],marker='o',label=model['id'])
        ax.set_title(dataset['id']);ax.set_xlabel('Epoch');ax.set_ylabel('Validation Macro F1');ax.set_ylim(0,1)
        if ax.lines:ax.legend(fontsize=8)
    fig.savefig(args.output/'validation-curves.png',dpi=160);plt.close(fig)
    for dataset in config['datasets']:
        fig,axes=plt.subplots(2,3,figsize=(11,6.5),layout='constrained')
        for ax,model in zip(axes.flat,config['models']):
            record=next((r for r,_ in records if r['dataset']==dataset['id'] and r['model']==model['id']),None)
            if record is None:ax.set_title(model['id']+' NOT RUN');ax.axis('off');continue
            matrix=np.array(record['confusion_matrix']);ax.imshow(matrix,cmap='Blues',vmin=0)
            for i in range(len(dataset['labels'])):
                for j in range(len(dataset['labels'])):
                    ax.text(j,i,str(matrix[i,j]),ha='center',va='center',color='white' if matrix[i,j]>matrix.max()/2 else 'black')
            ax.set_xticks(range(len(dataset['labels'])),[x[:3] for x in dataset['labels']]);ax.set_yticks(range(len(dataset['labels'])),[x[:3] for x in dataset['labels']])
            ax.set_title(model['id']);ax.set_xlabel('Predicted');ax.set_ylabel('Reference')
        fig.suptitle(dataset['id']+' | validation confusion matrices')
        fig.savefig(args.output/'datasets'/dataset['id']/'confusion-matrices.png',dpi=160);plt.close(fig)
    with (args.output/'validation-errors-to-review.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['dataset','model','row_id','reference','prediction','human_error_category','notes'])
        for record,folder in records:
            validation=json.loads((folder/'validation.json').read_text(encoding='utf-8'))
            for error in validation['errors']:writer.writerow([record['dataset'],record['model'],error['id'],error['expected'],error['predicted'],'',''])
    checks=ROOT/'.local/datasets/four-vi-v1/tests.log'
    if checks.exists():atomic_json(args.output/'checks.json',dict(result=checks.read_text(encoding='utf-8').splitlines()[-1],log_sha256=sha(checks),scope='pipelines/tests'))
    complete_checks=ROOT/'.local/datasets/four-vi-v1/full-python-tests.log'
    if complete_checks.exists():
        lines=complete_checks.read_text(encoding='utf-8').splitlines()
        result=next((line for line in reversed(lines) if ' passed' in line and ' in ' in line),None)
        if result:atomic_json(args.output/'full-checks.json',dict(result=result,log_sha256=sha(complete_checks),scope='scripts/ai/check.ps1 -WithBroker'))
    linux_checks=ROOT/'.local/datasets/four-vi-v1/linux-pipeline-tests.log'
    if linux_checks.exists():atomic_json(args.output/'linux-checks.json',dict(result=linux_checks.read_text(encoding='utf-8').splitlines()[-1],log_sha256=sha(linux_checks),scope='Linux Docker CPU pipelines/tests'))
    linux_reproduction=ROOT/'.local/datasets/four-vi-v1/linux-film-reproduction.log'
    if linux_reproduction.exists():
        result=json.loads(linux_reproduction.read_text(encoding='utf-8').splitlines()[-1])
        if not result['semantic_inputs_verified']:raise ValueError('Linux label reproduction failed')
        atomic_json(args.output/'linux-film-reproduction.json',dict(result=result,log_sha256=sha(linux_reproduction),
            method='Fresh ephemeral Linux CPU container, repository read-only, raw source fetched by pinned URL/SHA, no private annotation files or host model cache used.'))
    four_reproduction=ROOT/'.local/datasets/four-vi-v1/linux-four-reproduction.log'
    if four_reproduction.exists():
        result=json.loads(four_reproduction.read_text(encoding='utf-8').splitlines()[-1])
        if not result['all_four_reproduced']:raise ValueError('Four-corpus reproduction failed')
        atomic_json(args.output/'linux-four-reproduction.json',dict(result=result,log_sha256=sha(four_reproduction),
            method='Fresh ephemeral Linux CPU container downloaded all four pinned corpora, used label-only film snapshot, and verified model-input semantic SHA for all 12 splits. No private host data/cache/database used.'))
    files=sorted(p for p in args.output.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
    (args.output/'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.relative_to(args.output).as_posix()}\n' for p in files),encoding='utf-8')
    print(json.dumps(dict(completed=len(records),missing=len(missing),output=str(args.output))))


if __name__=='__main__':main()
