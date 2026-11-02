"""Explicit operator upload through the AI owner API; no legacy DB access."""
import argparse,json,os
from pathlib import Path
import httpx

def main():
    parser=argparse.ArgumentParser();parser.add_argument('input');parser.add_argument('--origin',default='http://127.0.0.1:8080/api');args=parser.parse_args()
    token=os.environ.get('AI_IMPORT_TOKEN','')
    if not token:raise RuntimeError('AI_IMPORT_TOKEN for knowledge.manage is required')
    rows=json.loads(Path(args.input).read_text(encoding='utf-8'))
    if not isinstance(rows,list) or any(row.get('approved') and not row.get('reviewer') for row in rows):raise ValueError('Reviewed JSON list and responsible human reviewer required')
    with httpx.Client(timeout=30,trust_env=False,headers={'Authorization':'Bearer '+token}) as http:
        for row in rows:
            response=http.post(args.origin.rstrip('/')+'/admin/documents',json=row)
            if response.status_code!=200:raise RuntimeError('AI owner rejected an import; inspect the input and retry deliberately')
    print(f'Imported {len(rows)} documents through the AI owner')
if __name__=='__main__':main()
