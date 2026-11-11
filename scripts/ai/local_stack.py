"""Cross-platform AI development commands; Python standard library + Docker Compose."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
SERVICES=['identity-service','catalog-service','cinema-service','booking-service','review-service','ai-service','cinema-worker','gateway','web']


def prepare():
    env=ROOT/'.env.microservices'
    if env.exists():
        print('Existing private configuration preserved. Review docs/AI_PORTABLE_SETUP.md before changing its project or volumes.')
        return
    subprocess.run([sys.executable,str(ROOT/'scripts/dev/prepare_messaging.py')],cwd=ROOT,check=True)
    flags={name+'_WRITES_ENABLED':'true' for name in ('IDENTITY','CATALOG','CINEMA','BOOKING','REVIEW','AI')}
    flags.update(PAYMENT_WRITES_ENABLED='false',REPORTING_WRITES_ENABLED='false',REVIEW_SENTIMENT_BACKEND='disabled')
    with env.open('a',encoding='utf-8') as stream:
        stream.write('\n# Portable AI development; configure full runtime separately.\n')
        stream.writelines(f'{key}={value}\n' for key,value in flags.items())
    print('Created private credentials for this machine. No account, business data or model weights were copied.')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=['prepare','up','status','admin','references','demo','stop'])
    p.add_argument('--project',default='cinema-ai-demo',help='Keep the same project name to reuse its own data volumes')
    p.add_argument('--gpu',action='store_true',help='Optional NVIDIA Docker runtime; CPU is the default')
    args=p.parse_args()
    if args.action=='prepare':
        prepare()
        return
    if not (ROOT/'.env.microservices').exists():
        p.error('Run prepare first; never copy somebody else\'s private environment file')
    command=['docker','compose','--project-name',args.project,'--env-file',str(ROOT/'.env.microservices'),
        '-f',str(ROOT/'compose.yml'),'-f',str(ROOT/'compose.ai-local.yml')]
    if args.gpu:
        command+=['-f',str(ROOT/'compose.ai-gpu.yml')]
    if args.action=='up':
        command+=['up','-d','--build',*SERVICES]
    elif args.action=='status':
        command+=['ps','-a']
    elif args.action=='admin':
        command+=['exec','identity-service','python','-m','identity_service.bootstrap']
    elif args.action=='references':
        command+=['exec','-T','catalog-service','python','-m','catalog_service.bootstrap_references','--demo']
    elif args.action=='demo':
        command+=['exec','ai-service','python','/app/tools/create_chat_demo.py','--origin','http://gateway:8080/api',
            '--allow-service-network','--create-demo','--output','/tmp/chat-demo-created.json']
    else:
        command+=['stop']
    subprocess.run(command,cwd=ROOT,check=True)


if __name__=='__main__':
    main()
