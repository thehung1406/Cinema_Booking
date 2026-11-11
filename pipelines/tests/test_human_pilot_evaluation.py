import pytest

from ml.evaluate_human_pilot import measure,masked_reviews


def test_abstentions_are_errors_in_primary_accuracy_and_class_recall():
    report=measure(['negative','neutral','positive'],['negative','abstain','positive'])
    assert report['accuracy_vs_single_reviewer']==pytest.approx(2/3)
    assert report['macro_f1']==pytest.approx(2/3)
    assert report['covered_accuracy']==1 and report['coverage']==pytest.approx(2/3)
    assert report['confusion_matrix'][1]==[0,0,0,1]
    assert report['per_class']['neutral']['support']==1 and report['per_class']['neutral']['recall']==0


def test_human_decisions_and_notes_never_enter_prediction_payload():
    rows=[dict(id='private-source-id',text='Test text',label='negative',reviewer='Private fixture identity',annotation_note='Private human reasoning')]
    assert masked_reviews(rows)==[dict(id='r0',text='Test text')]


def test_silver_experiment_rejects_faked_review_and_text_leakage():
    from ml.train_film_silver_pilot import validate_inputs
    def rows(prefix, texts, silver=False):
        return [dict(id=f'{prefix}{i}', group_id=f'{prefix}{i}', text=text, label=label,
            ai_label=label, synthetic=False, license='fixture', source='fixture',
            review_status='ai_labeled_unreviewed' if silver else 'approved',
            reviewer=None if silver else 'real-test-fixture')
            for i,(label,text) in enumerate(zip(('negative','neutral','positive'),texts))]
    train=rows('train', ['sad rainy midnight', 'ordinary quiet morning', 'bright happy sunshine'], True)
    validation=rows('validation', ['broken dirty chair', 'plain white ticket', 'excellent wonderful story'])
    pilot=rows('pilot', ['terrible loud speaker', 'scheduled standard admission', 'amazing beautiful cinematography'])
    validate_inputs(train,validation,pilot)
    train[0]['reviewer']='fake-human'
    with pytest.raises(ValueError,match='unreviewed'):
        validate_inputs(train,validation,pilot)
    train[0]['reviewer']=None
    pilot[0]['text']=train[0]['text']
    with pytest.raises(ValueError,match='Near-duplicate'):
        validate_inputs(train,validation,pilot)
