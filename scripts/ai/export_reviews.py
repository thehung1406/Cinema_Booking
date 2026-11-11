"""Read approved project reviews into an unlabeled local annotation queue."""
import argparse
import hashlib
import json
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--origin', default='http://127.0.0.1:8083')
    parser.add_argument('--film-id', type=int, nargs='+', required=True)
    parser.add_argument('--license', required=True, help='Actual basis permitting research use; do not invent permission')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    origin = httpx.URL(args.origin)
    if origin.scheme not in {'http', 'https'} or origin.userinfo or origin.path != '/' or origin.query or origin.fragment:
        raise SystemExit('Use a fixed Review service origin')
    if min(args.film_id) < 1 or not args.license.strip():
        raise SystemExit('Positive film IDs and a real usage-rights statement are required')
    output = Path(args.output)
    if output.exists():
        raise SystemExit('Choose a new snapshot path')
    rows, seen = [], set()
    with httpx.Client(base_url=str(origin), timeout=20, trust_env=False, follow_redirects=False) as client:
        for film_id in dict.fromkeys(args.film_id):
            skip = 0
            while True:
                response = client.get(f'/films/{film_id}/reviews', params={'skip': skip, 'limit': 50})
                response.raise_for_status()
                items = response.json()
                if not isinstance(items, list) or len(items) > 50:
                    raise ValueError('Unexpected owner response')
                for item in items:
                    identifier = f"review:{item['id']}:v{item['content_version']}"
                    if identifier in seen:
                        raise ValueError('Review list changed during export; retry after concurrent edits stop')
                    seen.add(identifier)
                    rows.append({'id': identifier, 'text': item['content'], 'film_id': film_id,
                        'group_id': f'film:{film_id}', 'source': str(origin)+f'films/{film_id}/reviews',
                        'source_version': item['updated_at'], 'license': args.license.strip(), 'synthetic': False,
                        'label': '', 'reviewer': '', 'review_status': 'pending',
                        'annotation_origin': 'owner-export-unlabeled'})
                skip += len(items)
                if len(items) < 50:
                    break
    if not rows:
        raise SystemExit('No approved reviews found; no empty dataset was created')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(''.join(json.dumps(row, ensure_ascii=False)+'\n' for row in rows), encoding='utf-8')
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    print(json.dumps({'reviews': len(rows), 'film_groups': len({r['group_id'] for r in rows}), 'sha256': digest,
                      'labels': 'pending; no star/model labels promoted; no author identities exported'}))


if __name__ == '__main__': main()
