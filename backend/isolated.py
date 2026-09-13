import traceback
import sys
from app.db.session import SessionLocal
from app.ingestion.store import ChunkRecord, upsert_chunks

def test():
    db = SessionLocal()
    try:
        upsert_chunks(db, [ChunkRecord('t','g','y',None,0,'t',1,[0.1]*384)])
        print('SUCCESS')
    except Exception as e:
        with open('out.txt', 'w') as f:
            traceback.print_exc(file=f)

if __name__ == '__main__':
    test()
