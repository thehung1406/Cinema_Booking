"""Fresh Git-visible source + fresh owner volumes + independently downloaded chat model.

Run only an explicitly named development project on alternate loopback ports.
Never reads the original private env or uses the original owner volumes.
"""
import argparse
from decimal import Decimal
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[2]


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--directory',default='.local/portable-v2')
    p.add_argument('--project',default='cinema-ai-portability-test')
    args=p.parse_args()
    work=(ROOT/args.directory).resolve()
    if not work.is_relative_to((ROOT/'.local').resolve()) or not re.fullmatch(r'cinema-ai-portability-[a-z0-9-]+',args.project):
        p.error('Dedicated portability project and workspace-local test copy required')
    source=work/'source'
    if not source.exists():
        subprocess.run([sys.executable,str(ROOT/'scripts/ai/export_portable_source.py'),'--output',str(source)],cwd=ROOT,check=True)
    subprocess.run([sys.executable,str(source/'scripts/ai/local_stack.py'),'prepare'],cwd=source,check=True)
    ports=work/'ports.yml'
    services={'gateway':(8180,8080),'ai-service':(8182,8082),'review-service':(8183,8083),
        'identity-service':(8184,8084),'catalog-service':(8185,8085),'cinema-service':(8186,8086),
        'booking-service':(8187,8087),'web':(5174,80)}
    ports.write_text('services:\n'+''.join(f'  {name}:\n    ports: !override ["127.0.0.1:{host}:{container}"]\n' for name,(host,container) in services.items()),encoding='utf-8')
    compose=['docker','compose','--project-name',args.project,'--env-file',str(source/'.env.microservices'),
        '-f',str(source/'compose.yml'),'-f',str(source/'compose.ai-local.yml'),'-f',str(ports)]
    def docker(*command,input=None,capture=False):
        return subprocess.run(compose+list(command),cwd=source,input=input,text=True,check=True,
            stdout=subprocess.PIPE if capture else None)
    # Inspect in memory only: Compose's rendered configuration includes secrets.
    config=json.loads(docker('config','--format','json',capture=True).stdout)
    if any(not value['name'].startswith(args.project+'_') for value in config['volumes'].values()):
        raise ValueError('Portability run would reuse a differently scoped volume')
    docker('up','-d','--build','identity-service','catalog-service','cinema-service','booking-service',
        'review-service','ai-service','cinema-worker','gateway','web')
    start=time.monotonic()
    print('Waiting for fresh owner APIs and verified CPU chat model...',flush=True)
    while True:
        try:
            with urlopen('http://127.0.0.1:8180/health/ready',timeout=5) as response:
                if response.status==200:
                    break
        except Exception:
            if time.monotonic()-start>1200:
                raise TimeoutError('Fresh stack did not become ready; inspect the dedicated project only')
            time.sleep(2)
    private=work/'demo-access.json'
    if not private.exists():
        access=dict(username='portable_demo_admin',email='portable-demo@example.org',full_name='PORTABILITY DEMO',password=secrets.token_urlsafe(24))
        command="import json,sys; from sqlalchemy import create_engine; from identity_service.config import Settings; from identity_service.bootstrap import initialize; initialize(create_engine(Settings().database_url),json.load(sys.stdin)); print('Created isolated demo admin')"
        docker('exec','-T','identity-service','python','-c',command,input=json.dumps(access))
        private.write_text(json.dumps(access),encoding='utf-8')
    access=json.loads(private.read_text(encoding='utf-8'))
    docker('exec','-T','catalog-service','python','-m','catalog_service.bootstrap_references','--demo')
    # Credentials travel through stdin, never command arguments or shared logs.
    command="import json,sys,importlib.util,httpx; s=importlib.util.spec_from_file_location('demo','/app/tools/create_chat_demo.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); a=json.load(sys.stdin); c=httpx.Client(base_url='http://gateway:8080/api/',timeout=30,trust_env=False); r=c.post('/auth/login',data={'username':a['username'],'password':a['password']}); r.raise_for_status(); c.headers['Authorization']='Bearer '+r.json()['access_token']; d=m.provision(c); print(json.dumps({'films':len(d['films']),'showtimes':len(d['showtimes']),'seats':d['seats']})); c.close()"
    demo=json.loads(docker('exec','-T','ai-service','python','-c',command,input=json.dumps(access),capture=True).stdout)
    # Use the real exposed gateway, real CPU model and owner databases, not fixtures.
    from urllib.parse import urlencode
    from urllib.request import Request
    with urlopen(Request('http://127.0.0.1:8180/api/auth/login',data=urlencode({'username':access['username'],'password':access['password']}).encode()),timeout=10) as response:
        token=json.load(response)['access_token']
    request=Request('http://127.0.0.1:8180/api/ai/chat',data=json.dumps({'message':'Tối mai tôi muốn xem phim hài, hai người, tổng dưới 200k.'}).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+token})
    with urlopen(request,timeout=90) as response:
        chat=json.load(response)
    (work/'chat-probe.json').write_text(json.dumps(chat,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if chat['status']!='ok' or not chat['cards']:
        raise AssertionError('Fresh stack did not return real demo showtime cards')
    assert all(Decimal(card['minimum_total'])==Decimal('160000') and card['party_size']==2 for card in chat['cards'])
    with urlopen('http://127.0.0.1:5174/health',timeout=5) as response:
        web_ready=response.status==200
    report=dict(created_at=datetime.now(timezone.utc).isoformat(),stage='fresh-source-and-volumes-portability-smoke',
        original_private_env_copied=False,original_model_cache_copied=False,original_database_volumes_used=False,
        host_ollama_used=False,host_cuda_required=False,model_runtime='CPU Docker Ollama',
        code_source_manifest='source-manifest.json',demo=demo,chat=chat,web_ready=web_ready,
        chat_model_planned=chat.get('mode')=='model_planned',financial_transactions_created=False,
        limitation='Tested fresh Linux containers on this Windows Docker host, not separate physical Windows/macOS/Linux machines; CPU fallback is recorded honestly.')
    (work/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(web_ready=web_ready,chat_mode=chat.get('mode'),cards=len(chat['cards']),private_env_copied=False,model_cache_copied=False)),flush=True)


if __name__=='__main__':
    main()
