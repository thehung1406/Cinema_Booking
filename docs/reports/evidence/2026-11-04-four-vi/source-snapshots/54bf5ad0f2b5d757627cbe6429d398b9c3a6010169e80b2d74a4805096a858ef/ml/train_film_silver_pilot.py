"""Explicit weak-supervision experiment; never admits silver as primary gold.

The separate primary training CLI retains its human/publisher admission gates.
Only the old human development labels select C/checkpoints here. The new human
pilot is read for leakage checks and evaluated only after the artifact is saved.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import time
from types import SimpleNamespace

from ml.data import read_jsonl, text_of, near_duplicate, reviewed
from ml.text import normalize_text
from ml.evaluate_human_pilot import ROOT, LABELS, checked, load, sha, save_metrics
from ml.auto_annotate import atomic_json
from ml.train_sentiment import metrics, architecture_metadata, transformer_training_arguments


def validate_inputs(train, validation, pilot):
    reviewed(validation)
    reviewed(pilot)
    for rows in (train, validation, pilot):
        if not rows or {r['label'] for r in rows} != set(LABELS):
            raise ValueError('Each partition requires all three classes')
        if len({r['id'] for r in rows}) != len(rows):
            raise ValueError('Duplicate row IDs')
    if any(r.get('review_status') != 'ai_labeled_unreviewed' or r.get('reviewer')
           or r.get('synthetic') is not False or not r.get('license') or not r.get('source')
           or r.get('ai_label') != r['label'] for r in train):
        raise ValueError('Expected real licensed text with explicitly unreviewed AI labels')
    for left, right in ((train, validation), (train, pilot), (validation, pilot)):
        if {r['id'] for r in left} & {r['id'] for r in right} or {r['group_id'] for r in left} & {r['group_id'] for r in right}:
            raise ValueError('Overlapping IDs/text families')
        right_text = [text_of(r) for r in right]
        if any(near_duplicate(text_of(a), b) for a in left for b in right_text):
            raise ValueError('Near-duplicate leakage across partitions')


def run(base, output, model_id):
    evaluation = base / 'evaluation-v1'
    protocol, pilot = checked(evaluation)
    preregistration = load(evaluation / 'silver-pilot-preregistration.json')
    config_path = ROOT / 'pipelines/configs/film_silver_pilot.v1.json'
    config = load(config_path)
    if preregistration['config_sha256'] != sha(config_path) or preregistration['config'] != config:
        raise ValueError('Frozen experiment configuration changed')
    sources = {'train': base/'ai-run-v2/silver-candidates.jsonl', 'validation': base/'existing-human-decisions.jsonl',
               'pilot': evaluation/'human-snapshot.jsonl'}
    train, validation = read_jsonl(sources['train']), read_jsonl(sources['validation'])
    validate_inputs(train, validation, pilot)
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    name = f'{model_id}-film-silver'
    selected = next(m for m in config['models'] if m['id'] == name)
    metadata = dict(schema_version=2, stage=config['stage'], model_version=name+':s42:'+sha(sources['train'])[:12],
        backend=selected['backend'], labels=list(LABELS), text_preprocessing='normalize', max_length=256,
        created_at=datetime.now(timezone.utc).isoformat(), seed=config['seed'],
        train_count=len(train), validation_count=len(validation), pilot_count=len(pilot),
        label_counts={k:dict(Counter(r['label'] for r in rows)) for k,rows in [('train',train),('validation',validation),('pilot',pilot)]},
        input_sha256={k:sha(p) for k,p in sources.items()}, config_sha256=sha(config_path),
        preregistration_sha256=sha(evaluation/'silver-pilot-preregistration.json'),
        training_label_origin='AI silver, unreviewed; not human gold', selection_split='36 old human development labels',
        primary_matrix_credit=False, primary_final_test_opened=False, production_promoted=False,
        python=platform.python_version(), code_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        code_sha256={p.name:sha(p) for p in [Path(__file__),ROOT/'pipelines/ml/train_sentiment.py',ROOT/'pipelines/ml/text.py']})
    x, vx = [[normalize_text(r['text']) for r in rows] for rows in (train, validation)]
    y, vy = [[r['label'] for r in rows] for rows in (train, validation)]
    if model_id == 'lr':
        import joblib
        from sklearn.pipeline import Pipeline
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        candidates=[]
        for c in selected['C_candidates']:
            model=Pipeline([('tfidf',TfidfVectorizer(analyzer='char',ngram_range=(2,5),min_df=1)),
                ('classifier',LogisticRegression(C=c,max_iter=1000,class_weight='balanced',random_state=config['seed']))])
            model.fit(x,y)
            predicted=model.predict(vx)
            candidates.append((metrics(vy,predicted)['macro_f1'],c,model))
        score,c,model=max(candidates,key=lambda item:item[0])
        joblib.dump(model,output/'model.joblib')
        classifier=model.named_steps['classifier']
        metadata.update(architecture=dict(model_type='char-tfidf-logistic-regression',encoder_layers=None,
            total_parameters=int(classifier.coef_.size+classifier.intercept_.size),input_features=len(model.named_steps['tfidf'].vocabulary_)),
            training=dict(selected_C=c,C_candidates=selected['C_candidates'],validation_candidates=[dict(C=c,macro_f1=s) for s,c,_ in candidates],
            optimizer=classifier.solver,iterations_completed=classifier.n_iter_.tolist(),max_iter=1000,class_weight='balanced',
            learning_rate=None,epochs_requested=None,epochs_completed=None,batch_size=None))
        validation_predictions=model.predict(vx).tolist()
    else:
        import numpy as np
        import torch
        from datasets import Dataset
        from transformers import AutoTokenizer,AutoModelForSequenceClassification,Trainer,TrainingArguments,DataCollatorWithPadding,set_seed
        set_seed(config['seed'])
        tokenizer=AutoTokenizer.from_pretrained(selected['checkpoint'],revision=selected['revision'])
        model=AutoModelForSequenceClassification.from_pretrained(selected['checkpoint'],revision=selected['revision'],num_labels=3,
            id2label=dict(enumerate(LABELS)),label2id={label:i for i,label in enumerate(LABELS)},ignore_mismatched_sizes=True)
        def dataset(texts,labels):
            return Dataset.from_dict(dict(tokenizer(texts,truncation=True,max_length=config['training']['max_length']),labels=[LABELS.index(y) for y in labels]))
        settings=SimpleNamespace(seed=config['seed'],**config['training'])
        arguments=TrainingArguments(**transformer_training_arguments(settings,output,torch.cuda.is_available()))
        validation_ds=dataset(vx,vy)
        trainer=Trainer(model=model,args=arguments,train_dataset=dataset(x,y),eval_dataset=validation_ds,
            processing_class=tokenizer,data_collator=DataCollatorWithPadding(tokenizer),
            compute_metrics=lambda result:dict(macro_f1=metrics([LABELS[i] for i in result.label_ids],
                [LABELS[i] for i in np.argmax(result.predictions,axis=1)])['macro_f1']))
        trainer.train()
        trainer.save_model(str(output));tokenizer.save_pretrained(output)
        validation_predictions=[LABELS[i] for i in np.argmax(trainer.predict(validation_ds).predictions,axis=1)]
        metadata.update(model=selected['checkpoint'],revision=selected['revision'],architecture=architecture_metadata(model),
            training=dict(config['training'],epochs_completed=trainer.state.epoch,global_step=trainer.state.global_step,
                best_checkpoint=trainer.state.best_model_checkpoint,best_validation_macro_f1=trainer.state.best_metric,
                effective_batch_size=arguments.per_device_train_batch_size*arguments.gradient_accumulation_steps*arguments.world_size,
                optimizer=arguments.optim.value,scheduler=arguments.lr_scheduler_type.value,warmup_steps=arguments.warmup_steps,
                fp16=arguments.fp16,device=str(arguments.device),world_size=arguments.world_size),
            peak_vram_bytes=torch.cuda.max_memory_allocated() if torch.cuda.is_available() else None)
        atomic_json(output/'training_history.json',trainer.state.log_history)
        (output/'training_arguments.json').write_text(arguments.to_json_string(),encoding='utf-8')
    metadata['elapsed_training_validation_seconds']=time.perf_counter()-started
    atomic_json(output/'metadata.json',metadata)
    atomic_json(output/'validation.json',metrics(vy,validation_predictions))
    (output/'environment.txt').write_text(subprocess.check_output([__import__('sys').executable,'-m','pip','freeze'],text=True),encoding='utf-8')
    # Artifact is fully saved before any predictions on the new development pilot.
    if model_id=='lr':
        predictions=model.predict([normalize_text(r['text']) for r in pilot]).tolist()
    else:
        dummy_labels=[LABELS[0]]*len(pilot)  # Human labels do not enter inference inputs.
        predictions=[LABELS[i] for i in np.argmax(trainer.predict(dataset([normalize_text(r['text']) for r in pilot],dummy_labels)).predictions,axis=1)]
    save_metrics(evaluation,name,pilot,[dict(id=r['id'],label=p) for r,p in zip(pilot,predictions)],
        dict(training_label_origin=metadata['training_label_origin'],primary_matrix_credit=False,training_metadata_sha256=sha(output/'metadata.json')))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',type=Path,default=ROOT/'.local/annotations/cinema-ai-assisted-v1')
    p.add_argument('--model',choices=['lr','visobert'],required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    run(args.base,args.output,args.model)
