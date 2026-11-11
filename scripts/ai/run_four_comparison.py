"""Sequential GPU runs, resumable completed cells; never opens research test."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'pipelines'))
from ml.auto_annotate import atomic_json
from ml.data import fingerprint


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,default=ROOT/'pipelines/configs/ai_research.four-vi.v1.json')
    p.add_argument('--output',type=Path,default=ROOT/'.local/research/four-vi-v1')
    p.add_argument('--segmenter-path',type=Path)
    p.add_argument('--dataset');p.add_argument('--model')
    args=p.parse_args();args.output=args.output.resolve();args.config=args.config.resolve()
    config=json.loads(args.config.read_text(encoding='utf-8'))
    if args.dataset and args.dataset not in {d['id'] for d in config['datasets']}:p.error('Unknown dataset')
    if args.model and args.model not in {m['id'] for m in config['models']}:p.error('Unknown model')
    if (args.model is None or args.model=='phobert') and args.segmenter_path is None:
        p.error('PhoBERT requires --segmenter-path; other models and LR do not')
    args.output.mkdir(parents=True,exist_ok=True)
    protocol_path=args.output/'protocol.json'
    identity=dict(config_sha256=sha(args.config),data_sha256={d['id']:fingerprint(ROOT/d['path']) for d in config['datasets']})
    if protocol_path.exists():
        if json.loads(protocol_path.read_text(encoding='utf-8'))['identity']!=identity:raise ValueError('Frozen config/data changed')
    else:atomic_json(protocol_path,dict(created_at=datetime.now(timezone.utc).isoformat(),identity=identity,config=config))
    # Execute immutable copies of ML modules. The CLI keeps its original
    # __file__ only for locating the repository; all bytes come from this copy.
    source_bytes={path.name:path.read_bytes() for path in sorted((ROOT/'pipelines/ml').glob('*.py'))}
    source_hashes={name:hashlib.sha256(data).hexdigest() for name,data in source_bytes.items()}
    source_id=hashlib.sha256(json.dumps(source_hashes,sort_keys=True).encode()).hexdigest()
    source_root=args.output/'source-snapshots'/source_id
    for name,data in source_bytes.items():
        target=source_root/'ml'/name;target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists() and target.read_bytes()!=data:raise ValueError('Immutable source copy changed')
        if not target.exists():target.write_bytes(data)
    frozen_config=args.output/'config-snapshots'/(identity['config_sha256']+'.json')
    frozen_config.parent.mkdir(exist_ok=True)
    if not frozen_config.exists():frozen_config.write_bytes(args.config.read_bytes())
    if sha(frozen_config)!=identity['config_sha256']:raise ValueError('Frozen config copy differs')
    if json.loads(frozen_config.read_text(encoding='utf-8'))!=config:raise ValueError('Config changed while preparing the protocol')
    env=os.environ.copy();env['PYTHONPATH']=os.pathsep.join([str(ROOT),str(ROOT/'pipelines')]);env['PYTHONUTF8']='1'
    env['PYTHONPATH']=os.pathsep.join([str(source_root),env['PYTHONPATH']]);env['PYTHONDONTWRITEBYTECODE']='1'
    # Small film first: verifies all model heads and GPU batch memory before full
    # source corpora. Order is frozen by code, never chosen by resulting scores.
    order=['cinema-silver','shopee','uit-visfd-general','uts2017-bank']
    model_order=['xlmr','phobert','visobert','videberta','mbert','lr']
    for dataset_id in order:
        if args.dataset and args.dataset!=dataset_id:continue
        for model_id in model_order:
            if args.model and args.model!=model_id:continue
            for seed in config['seeds']:
                folder=args.output/'runs'/dataset_id/model_id/str(seed)
                if all((folder/name).is_file() for name in ['metadata.json','validation.json','comparison_protocol.json']):
                    meta=json.loads((folder/'metadata.json').read_text(encoding='utf-8'))
                    completed_protocol=json.loads((folder/'comparison_protocol.json').read_text(encoding='utf-8'))
                    if (meta['data_sha256']!=identity['data_sha256'][dataset_id]
                            or completed_protocol['config_sha256']!=identity['config_sha256']
                            or meta['seed']!=seed):raise ValueError('Completed run protocol/data differs')
                    print(json.dumps(dict(dataset=dataset_id,model=model_id,state='already-completed')),flush=True);continue
                sizes=[config['training']['batch_size'],*config['oom_fallback_batch_sizes']] if model_id!='lr' else [None]
                for batch in sizes:
                    if folder.exists():
                        # Preserve partial artifacts, especially genuine OOM output.
                        archived=folder.with_name(folder.name+'-interrupted-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f'))
                        if not folder.resolve().is_relative_to(args.output.resolve()) or not archived.resolve().is_relative_to(args.output.resolve()):
                            raise ValueError('Partial artifact move must stay inside the named experiment output')
                        folder.rename(archived)
                    log=args.output/f'{dataset_id}-{model_id}-s{seed}-batch{batch}.log'
                    loader="import pathlib,sys; frozen=pathlib.Path(sys.argv[1]); original=sys.argv[2]; sys.argv=[original,*sys.argv[3:]]; exec(compile(frozen.read_bytes(),original,'exec'),{'__name__':'__main__','__file__':original})"
                    command=[sys.executable,'-c',loader,str((source_root/'ml/train_four_dataset.py').resolve()),
                        str(ROOT/'pipelines/ml/train_four_dataset.py'),'--config',str(frozen_config.resolve()),
                        '--dataset',dataset_id,'--model',model_id,'--output',str(folder.resolve()),'--seed',str(seed)]
                    if model_id=='phobert':command+=['--segmenter-path',str(args.segmenter_path.resolve())]
                    if batch:command+=['--batch-size',str(batch)]
                    print(json.dumps(dict(dataset=dataset_id,model=model_id,seed=seed,batch=batch,state='training')),flush=True)
                    with log.open('w',encoding='utf-8') as stream:
                        process=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
                    if process.returncode==0:
                        metadata=json.loads((folder/'metadata.json').read_text(encoding='utf-8'))
                        if metadata['data_sha256']!=identity['data_sha256'][dataset_id]:raise ValueError('Data changed during fitting')
                        atomic_json(folder/'comparison_protocol.json',dict(protocol_sha256=sha(protocol_path),config_sha256=identity['config_sha256'],
                            command=command,log_sha256=sha(log),batch_size=batch,source_snapshot_id=source_id,
                            completed_at=datetime.now(timezone.utc).isoformat()))
                        result=json.loads((folder/'validation.json').read_text(encoding='utf-8'))
                        print(json.dumps(dict(dataset=dataset_id,model=model_id,state='completed',validation_macro_f1=result['macro_f1'])),flush=True)
                        break
                    error=log.read_text(encoding='utf-8')
                    if batch and ('CUDA out of memory' in error or 'torch.OutOfMemoryError' in error):
                        print(json.dumps(dict(dataset=dataset_id,model=model_id,batch=batch,state='OOM-preserved-retry-smaller')),flush=True)
                        continue
                    raise SystemExit(f'Training failed. Inspect {log}')
                else:raise SystemExit(f'No GPU batch fits: {dataset_id}/{model_id}')
