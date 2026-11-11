"""Real trained artifact -> Review queue -> stats -> broker, in an isolated schema.

Bank validation text is used only for a technical smoke, never as film acceptance.
No human moderation/label confirmation is impersonated.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlmodel import Session

from cinema_platform.broker import Publisher, connect
from cinema_platform.events import EventEnvelope, MessagingBase
from cinema_platform.outbox import relay_one
from ml.data import read_jsonl
from review_service.config import Settings
from review_service.models import Base, ReviewSentiment
from review_service import service
from review_service.worker import process_one


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--model',default='pipelines/ml/runs/advisor-v3/uts2017-bank/lr/42')
    p.add_argument('--backend',choices=['sklearn','transformers'],default='sklearn')
    p.add_argument('--output',default='.local/evidence/advisor-v4/review-model-integration.json')
    args=p.parse_args()
    target=Path(args.output)
    if target.exists():
        raise ValueError('New evidence path required')
    db_url=os.environ['REVIEW_DATABASE_URL']
    parsed=make_url(db_url)
    if parsed.host not in {'localhost','127.0.0.1'} or not (parsed.database or '').endswith('_test'):
        raise ValueError('Dedicated loopback test database required')
    operator_url=os.environ['TEST_AMQP_OPERATOR_PUBLIC']
    publisher_url=os.environ['REVIEW_AMQP_PUBLIC_URL']
    from urllib.parse import urlsplit
    if any(urlsplit(url).hostname not in {'127.0.0.1','localhost'} or urlsplit(url).path != '/rabbitmq-test'
           for url in (operator_url,publisher_url)):
        raise ValueError('Dedicated loopback test broker required')
    model=Path(args.model).resolve()
    sample=read_jsonl('pipelines/ml/data/reviewed/uts2017-bank/validation.jsonl')[0]
    root=create_engine(db_url)
    schema='review_inference_pilot_'+uuid4().hex
    engine=None
    connection=None
    publisher=Publisher(publisher_url,'')
    try:
        with root.begin() as db:
            db.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine=create_engine(db_url,connect_args={'options':f'-csearch_path={schema}'})
        Base.metadata.create_all(engine)
        MessagingBase.metadata.create_all(engine)
        settings=Settings(database_url=db_url,writes_enabled=True,auto_approve=True,
            sentiment_backend=args.backend,sentiment_model_path=str(model),amqp_public_url=publisher_url)
        connection=connect(operator_url)
        channel=connection.channel()
        queue=channel.queue_declare(queue='',exclusive=True,auto_delete=True).method.queue
        for event_type in ('ReviewChanged.v1','ReviewSentimentUpdated.v1'):
            channel.queue_bind(queue,'cinema.events.v1',routing_key=event_type)
        with Session(engine) as db:
            review=service.create_review(db,film_id=900001,user_id=900001,content=sample['text'],settings=settings)
            identifier=review.id
        status=process_one(engine,settings)
        if status not in {'succeeded','needs_review'}:
            raise AssertionError('Real artifact inference did not complete')
        with Session(engine) as db:
            result=db.get(ReviewSentiment,identifier)
            from review_service.predictor import validate_scores
            validate_scores(result.scores)
            prediction=dict(status=result.status,label=result.label,scores=result.scores,model_version=result.model_version,
                decision_source=result.decision_source,confirmed_by_user_id=result.confirmed_by_user_id)
            stats=service.summaries(db,[900001],settings)[900001]
        published=0
        while relay_one(engine,publisher):
            published+=1
        events=[]
        for _ in range(published):
            method,_,body=channel.basic_get(queue,auto_ack=False)
            if method is None:
                raise AssertionError('Published event not received')
            event=EventEnvelope.model_validate_json(body)
            if 'content' in event.data or 'user_id' in event.data:
                raise AssertionError('Review event leaked private fields')
            events.append(dict(event_type=event.event_type,aggregate_version=event.aggregate_version,data=event.data))
            channel.basic_ack(method.delivery_tag)
        assert published==2 and {event['event_type'] for event in events}=={'ReviewChanged.v1','ReviewSentimentUpdated.v1'}
        report=dict(created_at=datetime.now(timezone.utc).isoformat(),stage='real-artifact-isolated-technical-smoke',
            production_changed=False,human_label_decision_performed=False,
            moderation='Test configuration auto_approve=True; not a human approval',
            model_metadata_sha256=hashlib.sha256((model/'metadata.json').read_bytes()).hexdigest(),
            input_sample_id=sample['id'],input_split='Bank validation, not final test',
            input_text_sha256=hashlib.sha256(sample['text'].encode()).hexdigest(),
            prediction=prediction,stats=stats,events=events,published=published,
            limitation='Bank-trained model and non-film text validate wiring only; no film sentiment quality or deployment claim.')
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
        print(json.dumps(dict(status=status,published=published,production_changed=False)))
    finally:
        publisher.close()
        if connection and connection.is_open:
            connection.close()
        if engine:
            engine.dispose()
        with root.begin() as db:
            db.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        root.dispose()


if __name__=='__main__':
    main()
