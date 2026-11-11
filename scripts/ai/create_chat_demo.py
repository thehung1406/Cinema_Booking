"""Explicit local demo provisioning through authenticated application APIs.

Creates only DEMO catalog/cinema records. Never changes historical films,
showtimes, accounts, orders or payments. The user must authorize demo data first.
"""
import argparse
from getpass import getpass
from datetime import datetime, timedelta
import json
from pathlib import Path
import time
import unicodedata
from zoneinfo import ZoneInfo

import httpx


def fold(value):
    return ''.join(c for c in unicodedata.normalize('NFD', value.lower().replace('đ','d')) if unicodedata.category(c) != 'Mn')


def provision(client):
    def request(method, path, **kwargs):
        response = client.request(method, path, **kwargs)
        if response.status_code >= 400:
            raise RuntimeError(f'{method} {path}: HTTP {response.status_code}: {str(response.json().get("detail", "Owner error"))[:300]}')
        result = response.json()
        if response.status_code == 202:
            stop = time.monotonic()+90
            while time.monotonic() < stop:
                operation = client.get('/admin/cinema-operations/'+result['operation_id'])
                operation.raise_for_status()
                row = operation.json()
                if row['status'] == 'DONE':
                    return row['result']
                if row['status'] == 'FAILED':
                    raise RuntimeError('Demo operation failed: '+row['message'])
                time.sleep(.5)
            raise RuntimeError('Demo operation not acknowledged before deadline')
        return result

    refs = request('GET','/admin/catalog')
    formats = refs['formats']
    if not formats:
        raise RuntimeError('Run the explicit Catalog demo reference bootstrap first; see docs/AI_PORTABLE_SETUP.md')
    format_id = next((row['id'] for row in formats if row.get('code') == '2D' or row['name'] == '2D'), formats[0]['id'])
    genres = {fold(row['name']):row['id'] for row in refs['genres']}
    if 'hai' not in genres:
        raise RuntimeError('Existing catalog needs a Comedy genre before creating this demo')
    theater_name = 'DEMO - Rạp thử trợ lý Cinema'
    theater = next((row for row in refs['theaters'] if row['name'] == theater_name), None)
    if theater is None:
        theater = request('POST','/admin/theaters',json={'name':theater_name,'address':'Dữ liệu demo cục bộ, không phải địa điểm kinh doanh','city':'TP. Hồ Chí Minh'})
    room_name = 'DEMO - Phòng 12 ghế'
    rooms = request('GET','/admin/rooms',params={'theater_id':theater['id'],'limit':200})['items']
    room = next((row for row in rooms if row['name'] == room_name), None)
    if room is None:
        room = request('POST','/admin/rooms',json={'theater_id':theater['id'],'name':room_name,'capacity':12,'room_type':'2D','status':'ACTIVE'})
    prices = request('GET','/admin/prices',params={'room_id':room['id'],'limit':200})['items']
    standard = next((row for row in prices if row['name'] == 'Standard'), None)
    if standard is None:
        standard = request('POST','/admin/prices',json={'room_id':room['id'],'name':'Standard','base_price':'80000'})
    seats = request('GET',f"/admin/rooms/{room['id']}/seats")
    existing = {row['seat_name'] for row in seats['seats']}
    for letter in ('A','B'):
        for number in range(1,7):
            name = f'{letter}{number}'
            if name not in existing:
                request('POST',f"/admin/rooms/{room['id']}/seats",json={'seat_name':name,'seat_type_id':standard['id'],'status':'ACTIVE'})
    today = datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date()
    specifications = [('DEMO - Chuyến đi vui vẻ',genres['hai'],'19:00:00','20:30:00'),
                      ('DEMO - Nhiệm vụ cuối tuần',genres.get('hanh dong',genres['hai']),'21:00:00','22:30:00')]
    films, showtimes = [], []
    for title, genre, start, end in specifications:
        matches = request('GET','/admin/films',params={'q':title,'limit':200})['items']
        film = next((row for row in matches if row['title'] == title), None)
        if film is None:
            film = request('POST','/admin/films',json={'title':title,'duration_minutes':90,'release_date':today.isoformat(),
                'end_date':(today+timedelta(days=30)).isoformat(),'genre_ids':[genre],'format_ids':[format_id],
                'image':'/poster-placeholder.svg','rating':'P','language':'Tiếng Việt','subtitle':'Tiếng Việt',
                'description':'Phim DEMO giả lập để kiểm thử trợ lý và chọn ghế; không phải lịch phát hành hay suất bán vé thực tế.'})
        films.append(film)
        for offset in (1,2,3):
            date = (today+timedelta(days=offset)).isoformat()
            matches = request('GET','/admin/showtimes',params={'film_id':film['id'],'room_id':room['id'],'show_date':date,'limit':200})['items']
            show = next((row for row in matches if row['start_time'] == start), None)
            if show is None:
                result = request('POST','/admin/showtimes',json={'film_id':film['id'],'room_id':room['id'],
                    'format_id':format_id,'show_date':date,'start_time':start,'end_time':end})
                show = request('GET',f"/showtimes/{result['id']}")
            showtimes.append(show)
    return {'created_for':'user-authorized local chatbot demo; no financial transactions',
            'theater':theater,'room':room,'films':films,'showtimes':showtimes,'ticket_price_vnd':80000,'seats':12}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--origin',default='http://127.0.0.1:8080/api')
    parser.add_argument('--credentials',default='.local/runtime/demo-access.json')
    parser.add_argument('--output',default='.local/evidence/chat-demo-data.json')
    parser.add_argument('--create-demo',action='store_true')
    parser.add_argument('--allow-service-network',action='store_true',help='Allow only the Docker Compose gateway hostname')
    args = parser.parse_args()
    if not args.create_demo:
        parser.error('Explicit --create-demo is required')
    allowed_hosts = {'127.0.0.1','localhost'} | ({'gateway'} if args.allow_service_network else set())
    if httpx.URL(args.origin).host not in allowed_hosts:
        parser.error('Demo provisioning is restricted to the local application')
    access = json.loads(Path(args.credentials).read_text(encoding='utf-8')) if Path(args.credentials).exists() else {
        'username': input('Your local admin username: '), 'password': getpass('Your local admin password: ')}
    with httpx.Client(base_url=args.origin.rstrip('/')+'/',timeout=30,trust_env=False) as client:
        login = client.post('/auth/login',data={'username':access['username'],'password':access['password']})
        login.raise_for_status()
        client.headers['Authorization']='Bearer '+login.json()['access_token']
        report = provision(client)
    output = Path(args.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'demo_films':len(report['films']),'demo_showtimes':len(report['showtimes']),'seats':report['seats'],'price_vnd':report['ticket_price_vnd']}))


if __name__ == '__main__': main()
