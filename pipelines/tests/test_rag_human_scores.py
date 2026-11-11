import csv
import hashlib
import json

import pytest

from scripts.ai.score_rag_human_review import score


def test_empty_scores_stay_pending_and_trace_tampering_is_rejected(tmp_path):
    trace=tmp_path/'trace.json'
    trace.write_text(json.dumps(dict(question='Test question',answer='Test answer')))
    checksum=hashlib.sha256(trace.read_bytes()).hexdigest()
    run=tmp_path/'run.json'
    run.write_text(json.dumps({'cases':[dict(id='fixture',state='completed',trace_file=str(trace),trace_sha256=checksum)]}))
    worksheet=tmp_path/'review.csv'
    with worksheet.open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=['id','trace_sha256','question','answer','reviewer','correctness','groundedness','citation','refusal'])
        writer.writeheader()
        writer.writerow(dict(id='fixture',trace_sha256=checksum,question='Test question',answer='Test answer'))
    result=score(run,worksheet)
    assert result['human_reviewed']==0 and result['pending']==1
    assert result['summary']['correctness']['mean_0_to_2'] is None
    trace.write_text(json.dumps(dict(question='Test question',answer='Edited answer')))
    with pytest.raises(ValueError,match='checksum'):
        score(run,worksheet)
