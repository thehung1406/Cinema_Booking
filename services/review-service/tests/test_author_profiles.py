from types import SimpleNamespace
import httpx
from review_service.config import Settings
from review_service.read_client import ReadClient


def test_author_uses_public_name_and_avatar_without_exposing_profile_fields():
    def respond(request):
        if request.url.path.endswith('/profiles'):
            return httpx.Response(200, json=[{'id': 7, 'username': 'login-name', 'full_name': 'Nguyễn An',
                'avatar': 'https://example.org/avatar.png', 'email': 'private@example.org'}])
        return httpx.Response(200, json=[{'user_id': 7, 'film_id': 1, 'verified_purchase': True}])
    settings = Settings(database_url='sqlite://', service_key='isolated-test-service-key-at-least-32', direct_reads_enabled=True)
    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        author = ReadClient(http, settings).authors([SimpleNamespace(user_id=7, film_id=1)])[(7, 1)]
    assert author.author == 'Nguyễn An'
    assert author.author_avatar == 'https://example.org/avatar.png'
    assert author.verified_purchase and 'email' not in author.model_dump()
