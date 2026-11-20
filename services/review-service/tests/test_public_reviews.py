from datetime import datetime, timedelta

from sqlalchemy import event, func
from sqlmodel import Session, select

from cinema_platform.events import OutboxRecord
from review_service import service
from review_service.models import Review, ReviewSentiment, utcnow
from test_review_api import HEADERS, client_for


def test_reviews_publish_without_approval_and_staff_can_delete(review_store, review_settings):
    client, identity = client_for(review_store, review_settings)
    with client:
        response = client.post('/films/1/reviews', headers=HEADERS, json={'content': 'Phim hay lắm'})
        assert response.status_code == 201
        review = response.json()
        assert review['moderation_status'] == 'approved'
        assert client.get('/films/1/reviews').json()[0]['id'] == review['id']
        edited = client.patch(f"/reviews/{review['id']}", headers=HEADERS,
                              json={'content': 'Cảm nhận đã sửa', 'content_version': 1})
        assert edited.json()['moderation_status'] == 'approved'
        assert client.patch(f"/reviews/{review['id']}", headers=HEADERS,
                            json={'content': 'Nội dung cũ', 'content_version': 1}).status_code == 409
        identity['user_id'] = 2
        assert client.get('/reviews', headers=HEADERS).status_code == 403
        assert client.delete(f"/reviews/{review['id']}", headers=HEADERS).status_code == 403
        identity['permissions'] = ['reviews.moderate']
        assert client.delete(f"/reviews/{review['id']}", headers=HEADERS).status_code == 204
        assert client.get('/films/1/reviews').json() == []
        assert client.get('/reviews', headers=HEADERS).json() == {'items': [], 'total': 0}
    with Session(review_store) as db:
        saved = db.get(Review, review['id'])
        assert saved.is_deleted and saved.content == ''


def test_staff_list_filters_and_current_analysis_only(review_store, review_settings):
    stamp = utcnow() - timedelta(days=1)
    with Session(review_store) as db:
        for i, visibility, status, label in [(1, 'approved', 'succeeded', 'positive'),
                                             (2, 'rejected', 'failed', None),
                                             (3, 'approved', 'succeeded', 'negative')]:
            db.add(Review(id=i, user_id=i, film_id=i, content=f'Nhận xét phim {i}',
                          moderation_status=visibility, content_version=2, updated_at=stamp))
            db.add(ReviewSentiment(review_id=i, content_version=1 if i == 3 else 2,
                                   status=status, label=label,
                                   scores={'positive': .8, 'neutral': .1, 'negative': .1},
                                   model_version='test-model'))
        db.commit()
    client, identity = client_for(review_store, review_settings)
    with client:
        assert client.get('/reviews').status_code == 401
        assert client.get('/reviews', headers=HEADERS).status_code == 403
        identity['permissions'] = ['reviews.moderate']
        def listing(**params):
            response = client.get('/reviews', headers=HEADERS, params=params)
            assert response.status_code == 200, response.text
            return response.json()
        result = listing(limit=1, offset=1)
        assert result['total'] == 3 and result['items'][0]['id'] == 2
        row = listing(q='phim 1', film_id=1, sentiment='positive', analysis_status='succeeded',
                      moderation_status='approved')['items'][0]
        assert row['film_id'] == 1 and row['model_version'] == 'test-model'
        assert row['scores']['positive'] == .8 and row['author'] == 'User 1'
        assert listing(moderation_status='rejected')['total'] == 1
        assert listing(analysis_status='failed')['total'] == 1
        assert listing(analysis_status='pending')['items'][0]['id'] == 3
        assert listing(sentiment='negative')['total'] == 0
        stale = listing(film_id=3)['items'][0]
        assert stale['sentiment'] is None and stale['scores'] == {} and stale['model_version'] is None
        assert client.get('/reviews?limit=101', headers=HEADERS).status_code == 422
        assert client.get('/reviews?analysis_status=invalid', headers=HEADERS).status_code == 422
        assert client.patch('/reviews/1/moderation', headers=HEADERS,
                            json={'content_version': 2, 'status': 'rejected'}).status_code == 404
        assert client.post('/reviews/1/sentiment-decision', headers=HEADERS, json={}).status_code == 404
        statements = []
        def count_selects(connection, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith('SELECT'):
                statements.append(statement)
        event.listen(review_store, 'before_cursor_execute', count_selects)
        try:
            assert listing(limit=100)['total'] == 3
            assert len(statements) == 2, 'List and count must not issue a sentiment SELECT for each review'
        finally:
            event.remove(review_store, 'before_cursor_execute', count_selects)


def test_publication_backfill_is_idempotent_preserves_hidden_and_emits_events(review_store):
    from review_service.backfill_public_reviews import backfill
    stamp = utcnow() - timedelta(days=50)
    with Session(review_store) as db:
        for i, visibility, deleted in [(1, 'pending', False), (2, 'approved', False),
                                        (3, 'rejected', False), (4, 'pending', True)]:
            db.add(Review(id=i, user_id=i, film_id=i, content='Nhận xét cũ',
                          moderation_status=visibility, is_deleted=deleted, content_version=2,
                          updated_at=stamp, created_at=stamp))
            db.add(ReviewSentiment(review_id=i, content_version=2, status='needs_review',
                                   label='negative', predicted_label='negative', attempts=5))
        db.commit()
    assert backfill(review_store) == 2
    assert backfill(review_store) == 0
    with Session(review_store) as db:
        for i in (1, 2):
            review, result = db.get(Review, i), db.get(ReviewSentiment, i)
            assert review.moderation_status == 'approved' and review.updated_at == stamp
            assert review.created_at == stamp and review.content_version == 2
            assert result.status == 'pending' and result.attempts == 0 and result.label is None
        assert db.get(Review, 3).moderation_status == 'rejected'
        assert db.get(Review, 4).is_deleted
        events = db.exec(select(OutboxRecord)).all()
        assert len(events) == 2
        assert all(datetime.fromisoformat(event.payload['data']['updated_at'].replace('Z', '+00:00')) == stamp for event in events)
        assert db.scalar(select(func.count()).select_from(Review)) == 4


def test_overlapping_backfills_emit_one_event(review_store, review_settings):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, get_ident
    from review_service.backfill_public_reviews import backfill
    with Session(review_store) as db:
        review = service.create_review(db, 1, 1, 'Nhận xét cần phân tích', review_settings)
        result = db.get(ReviewSentiment, review.id)
        result.status = 'needs_review'
        db.commit()
        initial_events = db.scalar(select(func.count()).select_from(OutboxRecord))
    selected, competing = Event(), Event()
    first_thread = []
    waited = []
    def before(connection, cursor, statement, parameters, context, executemany):
        if 'FOR UPDATE OF reviews' in statement:
            if not first_thread:
                first_thread.append(get_ident())
            elif get_ident() != first_thread[0]:
                competing.set()
    def after(connection, cursor, statement, parameters, context, executemany):
        if 'FOR UPDATE OF reviews' in statement and get_ident() == first_thread[0] and not waited:
            waited.append(True)
            selected.set()
            assert competing.wait(5)
    event.listen(review_store, 'before_cursor_execute', before)
    event.listen(review_store, 'after_cursor_execute', after)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(backfill, review_store)
            assert selected.wait(5)
            second = pool.submit(backfill, review_store)
            assert first.result(timeout=10) + second.result(timeout=10) == 1
        with Session(review_store) as db:
            assert db.scalar(select(func.count()).select_from(OutboxRecord)) == initial_events + 1
    finally:
        event.remove(review_store, 'before_cursor_execute', before)
        event.remove(review_store, 'after_cursor_execute', after)
