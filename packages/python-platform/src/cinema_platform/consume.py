"""Caller-owned transaction: inbox insert and business effects commit before ACK."""
from sqlalchemy import select,text
from .events import InboxRecord,fingerprint

def once(db,consumer,event,apply):
    key=consumer+':'+str(event.event_id)
    db.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key,9))'),{'key':key})
    old=db.get(InboxRecord,(consumer,str(event.event_id)))
    checksum=fingerprint(event.model_dump(mode='json'))
    if old:
        if old.payload_sha256!=checksum: raise ValueError('Event ID reused with different payload')
        return False
    apply()
    db.add(InboxRecord(consumer=consumer,event_id=str(event.event_id),payload_sha256=checksum)); db.flush()
    return True

def consume_queue(engine,url,queue,receive):
    from sqlmodel import Session
    from .broker import connect
    from .events import EventEnvelope
    connection=connect(url); channel=connection.channel(); channel.basic_qos(prefetch_count=10)
    def callback(ch,method,properties,body):
        try:
            if len(body)>256000: raise ValueError('Oversized event')
            event=EventEnvelope.model_validate_json(body)
            with Session(engine) as db,db.begin(): receive(db,event)
        except ValueError: ch.basic_reject(method.delivery_tag,requeue=False)
        else: ch.basic_ack(method.delivery_tag)
        # Store/network failures escape: reconnect requeues the unacknowledged event.
    channel.basic_consume(queue=queue,on_message_callback=callback,auto_ack=False)
    try: channel.start_consuming()
    finally:
        if connection.is_open: connection.close()
