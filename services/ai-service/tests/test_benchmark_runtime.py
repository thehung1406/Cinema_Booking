import json
from pathlib import Path

import httpx
import pytest

from scripts.ai import benchmark_rag_answers as benchmark


@pytest.mark.parametrize('provider', ['openai', 'ollama', 'disabled'])
def test_benchmark_uses_configured_provider_without_requiring_ollama(tmp_path, monkeypatch, provider):
    monkeypatch.chdir(Path(__file__).resolve().parents[3])
    monkeypatch.setenv('AI_LLM_PROVIDER', provider)
    monkeypatch.setenv('AI_OPENAI_API_KEY', 'fixture-only')
    monkeypatch.setenv('AI_OPENAI_MODEL', 'fixture-openai')
    monkeypatch.setenv('AI_LLM_MODEL', 'fixture-ollama')
    corpus, cases, output = [tmp_path / name for name in ('corpus.json', 'cases.jsonl', 'results')]
    corpus.write_text('[]')
    cases.write_text(json.dumps(dict(id='missing', question='Missing fact?', scope='policy', expected=[],
        expected_answerable=False, synthetic=True, annotation_origin='ai-authored-development'))+'\n')
    calls = []
    def respond(request):
        calls.append(request.url.path)
        assert provider == 'ollama', 'OpenAI must not call Ollama health or warmup endpoints'
        if request.url.path == '/api/tags':
            return httpx.Response(200, json={'models': [{'name': 'fixture-ollama', 'digest': 'fixture-digest'}]})
        assert request.url.path == '/api/chat'
        assert json.loads(request.content)['model'] == 'fixture-ollama'
        return httpx.Response(200, json={})
    original = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs))
    if provider == 'disabled':
        with pytest.raises(ValueError, match='provider'):
            benchmark.run([corpus], cases, output, 'lexical', '', '')
        assert not output.exists()
    else:
        result = benchmark.run([corpus], cases, output, 'lexical', '', '')
        assert result['runtime']['provider'] == provider
        assert result['runtime']['model']['name'] == f'fixture-{provider}'
        assert result['summary']['completed'] == 1
        assert calls == ([] if provider == 'openai' else ['/api/tags', '/api/chat'])
