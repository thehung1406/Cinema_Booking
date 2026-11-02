from uuid import uuid4
from catalog_support import binding_body


def test_release_before_delayed_bind_permanently_fences_the_id(catalog_client,catalog_settings):
    headers={'X-Service-Key':catalog_settings.service_key}
    body=binding_body(); ref={'reference':'cinema-operation:'+str(uuid4())}
    path='/internal/v1/schedule-bindings/'+body['id']
    assert catalog_client.post(path+'/release',headers=headers,json=ref).status_code==200
    assert catalog_client.post('/internal/v1/schedule-bindings',headers=headers,json=body).status_code==409
    assert catalog_client.post(path+'/confirm',headers=headers,json=ref).status_code==409
    assert catalog_client.post(path+'/release',headers=headers,json=ref).status_code==200


def test_confirmed_reference_releases_once_and_cannot_resurrect(catalog_client,catalog_settings):
    headers={'X-Service-Key':catalog_settings.service_key}; body=binding_body()
    assert catalog_client.post('/internal/v1/schedule-bindings',headers=headers,json=body).status_code==200
    path='/internal/v1/schedule-bindings/'+body['id']; ref={'reference':'cinema-showtime:123'}
    assert catalog_client.post(path+'/confirm',headers=headers,json=ref).status_code==200
    assert catalog_client.post(path+'/release',headers=headers,json={'reference':'cinema-showtime:999'}).status_code==409
    assert catalog_client.post(path+'/release',headers=headers,json=ref).status_code==200
    assert catalog_client.post('/internal/v1/schedule-bindings',headers=headers,json=body).status_code==409
