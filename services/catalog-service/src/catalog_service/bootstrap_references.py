"""Explicit, idempotent reference setup for the local AI demo. Own Catalog DB only."""
import argparse

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from .config import Settings
from .models import Genre, Format


def initialize(engine):
    with Session(engine) as db,db.begin():
        for name in ('Hài','Hành động'):
            if db.scalar(select(Genre).where(Genre.name==name)) is None:
                db.add(Genre(name=name))
        if db.scalar(select(Format).where(Format.code=='2D')) is None:
            db.add(Format(code='2D',name='2D'))


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--demo',action='store_true')
    args=p.parse_args()
    if not args.demo:
        p.error('Explicit --demo required; not part of normal API startup')
    engine=create_engine(Settings().database_url)
    try:
        initialize(engine)
        print('Demo reference genres and 2D format ready; existing records preserved.')
    finally:
        engine.dispose()


if __name__=='__main__':
    main()
