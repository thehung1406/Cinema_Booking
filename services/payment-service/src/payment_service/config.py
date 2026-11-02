from contextvars import ContextVar
import httpx
from pydantic import field_validator
from pydantic_settings import BaseSettings,SettingsConfigDict

class Settings(BaseSettings):
    database_url:str
    service_key:str=''
    identity_origin:str='http://identity-service:8084'
    booking_origin:str='http://booking-service:8087'
    writes_enabled:bool=False
    frontend_url:str='http://localhost:5173'
    tmn_code:str=''
    hash_secret:str=''
    vnpay_url:str='https://sandbox.vnpayment.vn/paymentv2/vpcpay.html'
    amqp_public_url:str=''
    amqp_consumer_url:str=''
    reconcile_seconds:int=30
    model_config=SettingsConfigDict(env_prefix='PAYMENT_',extra='ignore',hide_input_in_errors=True)
    @field_validator('identity_origin','booking_origin')
    @classmethod
    def origin(cls,value):
        url=httpx.URL(value)
        if url.scheme not in {'http','https'} or not url.host or url.userinfo or url.path!='/' or url.query or url.fragment: raise ValueError('Fixed HTTP origin required')
        return str(url).rstrip('/')

request_settings=ContextVar('payment_settings',default=None)
_default=Settings()
class ScopedSettings:
    def __getattr__(self,name): return getattr(request_settings.get() or _default,name)
    def __setattr__(self,name,value): setattr(_default,name,value)
settings=ScopedSettings()
