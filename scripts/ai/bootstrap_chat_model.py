"""Download/verify/warm a pinned Ollama model. Standard library only; no host paths."""
import argparse
import json
from pathlib import Path
import time
from urllib.error import URLError
from urllib.request import Request, build_opener, ProxyHandler


def request(origin, path, body=None, timeout=30):
    data=json.dumps(body).encode() if body is not None else None
    req=Request(origin.rstrip('/')+path,data=data,headers={'Content-Type':'application/json'})
    with build_opener(ProxyHandler({})).open(req,timeout=timeout) as response:
        return json.load(response)


def provision(origin, lock, call=request):
    models=call(origin,'/api/tags').get('models',[])
    found=next((m for m in models if m['name']==lock['model']),None)
    if found is None:
        print('Downloading the pinned chat model; first setup needs internet.',flush=True)
        call(origin,'/api/pull',{'model':lock['model'],'stream':False},timeout=1800)
        found=next((m for m in call(origin,'/api/tags')['models'] if m['name']==lock['model']),None)
    if found is None or found.get('digest')!=lock['digest']:
        raise ValueError('Model digest differs from the repository lock. Keep AI disabled and review the model version; do not silently change the lock.')
    print('Model digest verified. Warming CPU/GPU inference...',flush=True)
    call(origin,'/api/chat',{'model':lock['model'],'stream':False,'think':False,'keep_alive':'5m',
        'messages':[{'role':'user','content':'Ready'}],'options':{'num_predict':1,'num_ctx':lock['context_length']}},timeout=600)
    return {'model':lock['model'],'digest':found['digest'],'status':'verified-and-warmed'}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--origin',default='http://127.0.0.1:11434')
    p.add_argument('--lock',default='pipelines/configs/chat_runtime.lock.json')
    args=p.parse_args()
    lock=json.loads(Path(args.lock).read_text(encoding='utf-8'))
    for attempt in range(30):
        try:
            request(args.origin,'/api/tags',timeout=3)
            break
        except (URLError,TimeoutError):
            if attempt==29:
                raise
            time.sleep(1)
    print(json.dumps(provision(args.origin,lock)),flush=True)


if __name__=='__main__':
    main()
