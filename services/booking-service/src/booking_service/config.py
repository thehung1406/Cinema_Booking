import httpx
from pydantic import field_validator,Field
from pydantic_settings import BaseSettings,SettingsConfigDict

class Settings(BaseSettings):
    database_url:str
    service_key:str=""
    identity_origin:str="http://identity-service:8084"
    catalog_origin:str="http://catalog-service:8085"
    payment_storage_owner:str="legacy"
    amqp_payment_consumer_url:str=""
    writes_enabled:bool=False
    hold_seconds:int=Field(default=600,ge=1,le=600)
    frontend_url:str="http://localhost:5173"
    tmn_code:str=""
    hash_secret:str=""
    vnpay_url:str="https://sandbox.vnpayment.vn/paymentv2/vpcpay.html"
    amqp_public_url:str=""
    amqp_notification_url:str=""
    model_config=SettingsConfigDict(env_prefix="BOOKING_",extra="ignore",hide_input_in_errors=True)
    @field_validator('identity_origin','catalog_origin')
    @classmethod
    def origin(cls,value):
        url=httpx.URL(value)
        if url.scheme not in {'http','https'} or not url.host or url.userinfo or url.path!='/' or url.query or url.fragment: raise ValueError('Fixed HTTP origin required')
        return str(url).rstrip('/')

from contextvars import ContextVar
request_settings=ContextVar("booking_request_settings",default=None)
_default_settings=Settings()

class ScopedSettings:
    def __getattr__(self,name): return getattr(request_settings.get() or _default_settings,name)
    def __setattr__(self,name,value): setattr(_default_settings,name,value)

settings=ScopedSettings()
