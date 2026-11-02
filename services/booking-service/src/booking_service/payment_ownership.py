from sqlalchemy import select
from fastapi import HTTPException
from .models.payment_saga import PaymentOwnership
from .config import settings

def owner(db,lock=False):
    query=select(PaymentOwnership).where(PaymentOwnership.id==1)
    if lock: query=query.with_for_update(read=True)
    row=db.scalar(query)
    if row is None: raise HTTPException(503,'Payment ownership migration missing')
    rank={'legacy':0,'maintenance':1,'service':2}
    return max((row.owner,settings.payment_storage_owner),key=rank.__getitem__)

def legacy(db):
    state=owner(db,True)
    if state!='legacy': raise HTTPException(410 if state=='service' else 503,'Payment writer đã chuyển hoặc đang freeze')

def main():
    import argparse
    from sqlalchemy import create_engine
    from sqlmodel import Session
    parser=argparse.ArgumentParser(); parser.add_argument('owner',choices=['legacy','maintenance','service']); parser.add_argument('--reason',required=True)
    args=parser.parse_args()
    if not args.reason.strip(): raise ValueError('Audit reason required')
    from cinema_platform.events import ReplayAudit
    from uuid import uuid4
    with Session(create_engine(settings.database_url)) as db,db.begin():
        row=db.scalar(select(PaymentOwnership).where(PaymentOwnership.id==1).with_for_update())
        if (row.owner=='service' and args.owner!='service') or (row.owner=='legacy' and args.owner=='service'): raise ValueError('Freeze/verify first; transferred owner is terminal')
        db.add(ReplayAudit(record_id=str(uuid4()),actor='local-operator',reason=f'Payment ownership {row.owner} -> {args.owner}: {args.reason}'))
        row.owner=args.owner
    print('Booking-side Payment ownership:',args.owner)
if __name__=='__main__': main()
