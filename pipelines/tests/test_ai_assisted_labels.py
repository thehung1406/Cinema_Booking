import json

import pytest

from ml.assist_dataset import prepare
from ml.auto_annotate import batches, validate
from ml.data import read_jsonl, reviewed, write_jsonl


def test_needs_context_cannot_be_promoted_to_neutral():
    item=dict(id='r0',category='needs_context',label='neutral',confidence='low',reason='Fixture')
    with pytest.raises(ValueError,match='Unexpected'):
        validate({'items':[item]},1)
    del item['label']
    assert validate({'items':[item]},1)['r0']['label'] is None
    with pytest.raises(ValueError,match='Missing or duplicate'):
        validate({'items':[item,item]},2)


def test_ai_labels_remain_ineligible_for_primary_human_benchmark():
    with pytest.raises(ValueError,match='reviewer'):
        reviewed([dict(id='fixture',label='positive',review_status='ai_labeled_unreviewed',reviewer=None,
            source='https://example.org',license='test',group_id='g')])


def test_frozen_pilot_excludes_human_work_and_near_duplicate_families(tmp_path):
    import hashlib
    source=tmp_path/'source.jsonl'
    rows=[dict(id=str(i),text=hashlib.sha256(str(i).encode()).hexdigest(),group_id=str(i),
        source='https://example.org/test-only',license='test-only',synthetic=False) for i in range(75)]
    rows[1]['text']=rows[0]['text']+'!'
    human=rows[0] | dict(label='negative',reviewer='Test person',review_status='approved')
    write_jsonl(source,rows)
    human_path=tmp_path/'human.jsonl'
    write_jsonl(human_path,[human])
    output=tmp_path/'batch'
    manifest=prepare(source,output,human_path,target=10)
    train=read_jsonl(output/'train-ai-pending.jsonl')
    gold=read_jsonl(output/'gold-pilot-pending.jsonl')
    assert manifest['existing_human_decisions']==1
    assert not {'0','1'} & {r['id'] for r in train+gold}
    assert not {r['group_id'] for r in train} & {r['group_id'] for r in gold}
    assert all(r['label'] is None and r['reviewer'] is None and 'suggested_label' not in r for r in gold)
    assert json.loads((output/'partition-manifest.json').read_text())['stage'].startswith('supplementary')
    assert read_jsonl(output/'existing-human-decisions.jsonl')[0]['label']=='negative'


def test_long_reviews_are_not_silently_truncated():
    rows=[dict(id='a',text='x'*4300),dict(id='b',text='short')]
    result=list(batches(rows,4))
    assert len(result)==2 and result[0][0]['text']==rows[0]['text']


def test_ai_assisted_human_confirmation_is_not_counted_as_blind_agreement(tmp_path):
    from ml.blind_annotation import reconcile
    source=dict(id='fixture',text='Test fixture only',group_id='test',source='https://example.org',license='test',
        synthetic=True,label='positive',reviewer='A',review_status='approved',annotation_mode='ai-assisted',annotation_origin='manual-ai-assisted-confirmation')
    first,second=tmp_path/'first.jsonl',tmp_path/'second.jsonl'
    write_jsonl(first,[source]);write_jsonl(second,[source | {'reviewer':'B'}])
    with pytest.raises(ValueError,match='blind independent'):
        reconcile(first,second)


def test_human_ai_assisted_correction_keeps_original_machine_label(tmp_path):
    import re
    import threading
    import httpx
    from ml.annotation_app import create_server
    source,output=tmp_path/'source.jsonl',tmp_path/'confirmed.jsonl'
    write_jsonl(source,[dict(id='synthetic-test-fixture',text='Synthetic test text only',synthetic=True,
        label='positive',ai_label='positive',suggested_label='positive',annotation_mode='ai-assisted',review_status='ai_labeled_unreviewed')])
    server=create_server(source,output,port=0)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{server.server_port}',trust_env=False) as client:
            token=re.search(r"const token='([a-f0-9]+)'",client.get('/').text).group(1)
            headers={'X-Annotation-Token':token}
            state=client.get('/api/items',headers=headers).json()
            response=client.post('/api/decision',headers=headers,json=dict(id='synthetic-test-fixture',
                reviewer='Test fixture reviewer',label='negative',note='Test fixture correction',revision=state['revision']))
            assert response.status_code==200
        saved=read_jsonl(output)[0]
        assert saved['annotation_origin']=='manual-ai-assisted-confirmation'
        assert saved['ai_label']=='positive' and saved['label']=='negative' and saved['confirmed_at']
    finally:
        server.shutdown();thread.join(timeout=3);server.server_close()
