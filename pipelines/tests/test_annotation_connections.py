import concurrent.futures
import re
import socket
import threading
import time

import httpx

from ml.annotation_app import create_server
from ml.data import read_jsonl, write_jsonl


def test_browser_preconnection_cannot_block_page_or_data_requests(tmp_path):
    original=tmp_path/'original.jsonl'
    write_jsonl(original,[dict(id='synthetic-connection-fixture',text='Synthetic test only',synthetic=True,review_status='pending')])
    server=create_server(original,tmp_path/'output.jsonl',port=0)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    idle=socket.create_connection(('127.0.0.1',server.server_port),timeout=2)
    try:
        # Let the server accept the idle socket before real browser requests.
        time.sleep(.05)
        origin=f'http://127.0.0.1:{server.server_port}'
        with httpx.Client(timeout=2,trust_env=False) as client:
            response=client.get(origin+'/')
            assert response.status_code==200
            assert int(response.headers['Content-Length'])==len(response.content)
            token=re.search(r"const token='([a-f0-9]+)'",response.text).group(1)
            def load(_):
                return client.get(origin+'/api/items',headers={'X-Annotation-Token':token}).json()
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
                results=list(pool.map(load,range(3)))
            assert all(r['items'][0]['id']=='synthetic-connection-fixture' for r in results)
            assert len({r['revision'] for r in results})==1
    finally:
        idle.close();server.shutdown();thread.join(timeout=3);server.server_close()


def test_parallel_decisions_cannot_overwrite_a_stale_revision(tmp_path):
    original,output=tmp_path/'original.jsonl',tmp_path/'output.jsonl'
    write_jsonl(original,[dict(id=f'synthetic-fixture-{i}',text=f'Synthetic test {i}',synthetic=True,review_status='pending') for i in range(2)])
    server=create_server(original,output,port=0)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{server.server_port}',timeout=2,trust_env=False) as client:
            token=re.search(r"const token='([a-f0-9]+)'",client.get('/').text).group(1)
            headers={'X-Annotation-Token':token}
            state=client.get('/api/items',headers=headers).json()
            def save(i):
                return client.post('/api/decision',headers=headers,json=dict(id=f'synthetic-fixture-{i}',
                    reviewer='Synthetic fixture reviewer',label='positive',revision=state['revision'])).status_code
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                codes=list(pool.map(save,range(2)))
        assert sorted(codes)==[200,409]
        assert sum(r['review_status']=='approved' for r in read_jsonl(output))==1
    finally:
        server.shutdown();thread.join(timeout=3);server.server_close()
