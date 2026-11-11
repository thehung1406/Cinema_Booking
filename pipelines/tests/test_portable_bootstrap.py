import pytest

from scripts.ai.bootstrap_chat_model import provision
from scripts.ai import local_stack


def test_cached_wrong_model_is_not_warmed_or_silently_replaced():
    calls=[]
    def call(origin,path,body=None,**kwargs):
        calls.append(path)
        return {'models':[{'name':'test-model','digest':'unexpected'}]}
    with pytest.raises(ValueError,match='digest'):
        provision('http://test',{'model':'test-model','digest':'locked','context_length':4096},call)
    assert calls==['/api/tags']


def test_fresh_model_is_verified_before_warmup():
    calls=[]
    def call(origin,path,body=None,**kwargs):
        calls.append(path)
        if path=='/api/tags':
            return {'models':[] if len(calls)==1 else [{'name':'test-model','digest':'locked'}]}
        return {}
    result=provision('http://test',{'model':'test-model','digest':'locked','context_length':4096},call)
    assert calls==['/api/tags','/api/pull','/api/tags','/api/chat']
    assert result['status']=='verified-and-warmed'


def test_prepare_never_replaces_existing_machine_credentials(tmp_path,monkeypatch):
    monkeypatch.setattr(local_stack,'ROOT',tmp_path)
    private=tmp_path/'.env.microservices'
    private.write_text('TEST_ONLY_SECRET=keep-this-local\n')
    monkeypatch.setattr(local_stack.subprocess,'run',lambda *a,**k:pytest.fail('Must not regenerate credentials'))
    local_stack.prepare()
    assert private.read_text()=='TEST_ONLY_SECRET=keep-this-local\n'
