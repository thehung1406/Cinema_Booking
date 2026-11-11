"""Research scope checks: binary scoring and silver admission stay explicit."""
import json
from difflib import SequenceMatcher
import random

import pytest

from ml.data import near_duplicate,write_jsonl
from ml.dataset_audit import audit
from ml.task_spec import label_order
from ml.train_sentiment import metrics,training_class_weights
from ml.train_four_dataset import validate


def test_binary_metrics_do_not_add_an_unobserved_neutral_class(tmp_path):
    (tmp_path/'task.json').write_text(json.dumps(dict(labels=['negative','positive'])))
    labels=label_order(tmp_path)
    report=metrics(['negative','positive'],['negative','positive'],labels)
    assert report['macro_f1']==1
    assert report['confusion_matrix']==[[1,0],[0,1]]
    assert report['label_order']==['negative','positive']
    assert training_class_weights(['negative','positive'],'none',labels)==[1,1]
    with pytest.raises(ValueError,match='declared label'):
        metrics(['negative'],['neutral'],labels)


def test_research_accelerator_preserves_original_near_duplicate_definition():
    rng=random.Random(439)
    pairs=[('a'*44+'b'*6,'a'*44+'c'*6),('tieng viet unicode','tieng viet unicodE')]
    for _ in range(120):
        left=''.join(rng.choice('abcdefgh ') for _ in range(rng.randint(5,100)))
        right=list(left)
        for _ in range(rng.randint(0,25)):
            right[rng.randrange(len(right))]=rng.choice('abcdefgh ')
        pairs.append((left,''.join(right)))
    for left,right in pairs:
        assert near_duplicate(left,right)==(SequenceMatcher(None,left,right).ratio()>=.88)


def test_primary_admission_still_rejects_silver_even_in_four_corpus_work(tmp_path):
    (tmp_path/'task.json').write_text(json.dumps(dict(labels=['negative','positive'])))
    for split,texts in [('train',['sad rainy day','bright sunny dawn']),('validation',['broken chair','amazing beautiful story']),('test',['terrible loud noise','wonderful fine evening'])]:
        write_jsonl(tmp_path/f'{split}.jsonl',[dict(id=f'{split}:{i}',group_id=f'{split}:{i}',text=text,label=label,
            reviewer=None if split=='train' else 'fixture-human',review_status='ai_labeled_unreviewed' if split=='train' else 'approved',
            source='fixture',license='fixture',synthetic=False) for i,(label,text) in enumerate(zip(['negative','positive'],texts))])
    assert not audit(tmp_path)['admissible']
    with pytest.raises(ValueError,match='requires reviewer'):
        validate(tmp_path,'publisher-or-human-reviewed')


def test_label_pack_round_trip_preserves_model_inputs_without_names_or_text(tmp_path,monkeypatch):
    import hashlib
    from scripts.ai import reproduce_cinema_labels as tool
    directory=tmp_path/'private';directory.mkdir()
    raw=b'text\nfixture training review\nfixture validation review\nfixture pilot review\n'
    source=tmp_path/'source.csv';source.write_bytes(raw)
    monkeypatch.setattr(tool,'SOURCE_SHA',hashlib.sha256(raw).hexdigest())
    parts={}
    for i,name in enumerate(['train','validation','test']):
        row=dict(id=f'vimovie:fixture:row:{i}',text=['fixture training review','fixture validation review','fixture pilot review'][i],
            label='positive',group_id=f'family:{i}',source='fixture-source',license='fixture-license',synthetic=False,
            annotation_origin='fixture-AI' if name=='train' else 'fixture-confirmed-human',
            reviewer=None if name=='train' else 'PRIVATE TEST FIXTURE IDENTITY',
            review_status='ai_labeled_unreviewed' if name=='train' else 'approved')
        if name=='train':row.update(ai_label='positive',suggestion_model='fixture-model',suggestion_model_digest='fixture-digest')
        parts[name]=[row];write_jsonl(directory/f'{name}.jsonl',[row])
    (directory/'task.json').write_text(json.dumps(dict(labels=['negative','neutral','positive'])))
    (directory/'source_manifest.json').write_text('{}')
    pack=tmp_path/'public-labels.json';tool.export(directory,pack)
    public=pack.read_text(encoding='utf-8')
    assert 'PRIVATE TEST FIXTURE IDENTITY' not in public and 'fixture training review' not in public
    restored=tmp_path/'restored';tool.restore(pack,restored,source)
    from ml.data import read_jsonl
    for name,rows in parts.items():
        reconstructed=read_jsonl(restored/f'{name}.jsonl')
        assert tool.semantic_sha(rows)==tool.semantic_sha(reconstructed)
        assert reconstructed[0]['review_status']==rows[0]['review_status']
        if name=='train':assert reconstructed[0]['reviewer'] is None
