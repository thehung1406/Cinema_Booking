"""Real local LLM + complete chat API, using isolated DB/cache/owner fixtures."""
import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path
import time
from zoneinfo import ZoneInfo

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from ai_service.config import Settings
from ai_service.main import create_app
from ai_service.models import Base


class LocalCache:
    def eval(self, *args): return 1
    def setex(self, *args): pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='.local/evidence/full-chat-pilot.json')
    args = parser.parse_args()
    tomorrow = (datetime.now(ZoneInfo('Asia/Ho_Chi_Minh'))+timedelta(days=1)).date().isoformat()
    calls = []
    def owner(request):
        calls.append({'method': request.method, 'path': request.url.path, 'body': json.loads(request.content) if request.content else None})
        if request.url.path.endswith('/matches'): body = []
        elif request.url.path.endswith('/options'):
            body = {'items': [{'showtime_id': 11, 'sales_version': 1, 'film_id': 1, 'film_title': 'Development fixture comedy',
                'theater_id': 1, 'theater_name': 'Development fixture theater', 'room_name': '1', 'show_date': tomorrow,
                'start_time': '19:30:00', 'format': '2D', 'available_seats': 12, 'min_ticket_price': '90000',
                'minimum_total': '180000', 'party_size': 2, 'currency': 'VND', 'url': '/seat-selection/11'}], 'has_more': False}
        else: raise AssertionError('Unexpected owner call: '+request.url.path)
        return httpx.Response(200, json=body)
    settings = Settings(database_url='sqlite://', redis_url='redis://localhost/0', writes_enabled=True,
        direct_reads_enabled=True, service_key='isolated-pilot-credential-32-characters', llm_provider='ollama', llm_timeout_seconds=20)
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    app = create_app(settings, engine=engine, cache=LocalCache(), read_transport=httpx.MockTransport(owner),
        auth_transport=httpx.MockTransport(lambda request: httpx.Response(200, json={'user_id': 1, 'role': 'USER', 'permissions': [], 'is_active': True})))
    started = time.perf_counter()
    try:
        with TestClient(app) as client:
            response = client.post('/ai/chat', headers={'Authorization': 'Bearer isolated-pilot'},
                json={'message': 'Tối mai tôi muốn xem phim hài, hai người, tổng tiền vé dưới 250k, sau 19h.'})
            response.raise_for_status()
            body = response.json()
            assert body['status'] == 'ok' and body['cards'][0]['minimum_total'] == '180000'
            assert body['mode'] == 'model_planned', 'Live planner failed; fallback alone is not a successful model smoke'
            query = next(call['body'] for call in calls if call['path'].endswith('/options'))
            assert query['party_size'] == 2 and query['budget_total'] == '250000' and query['genre'] == 'Hài'
            assert query['show_date'] == tomorrow and query['start_after'] == '19:00:00'
        report = {'stage': 'development-smoke-not-held-out', 'model_runtime': 'real Ollama',
                  'owners_db_cache': 'isolated fixtures only; no real showtimes or booking writes',
                  'elapsed_seconds': time.perf_counter()-started, 'owner_calls': calls, 'response': body}
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'status': body['status'], 'mode': body['mode'], 'seconds': report['elapsed_seconds'], 'cards': len(body['cards'])}))
    finally:
        engine.dispose()


if __name__ == '__main__': main()
