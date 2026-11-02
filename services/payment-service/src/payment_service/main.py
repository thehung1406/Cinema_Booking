from contextlib import asynccontextmanager
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from uuid import uuid4
import hashlib,hmac,urllib.parse
import httpx
from fastapi import FastAPI,Depends,HTTPException,Request,Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel,Field
from sqlalchemy import create_engine,select,text
from sqlalchemy.exc import SQLAlchemyError,IntegrityError
from cinema_platform.auth import AuthClient
from cinema_platform.events import ReplayAudit
from .config import Settings,settings as scoped,request_settings
from .dependencies import get_session,get_current_user,private,writes,require_permission
from .models import Payment,Case,Checkout,Fulfillment,now
from . import clients,service
from .signatures import verify_vnpay_signature

def create_app(settings=None,*,engine=None,auth_transport=None):
    settings=settings or Settings(); owned=engine is None
    engine=engine or create_engine(settings.database_url,pool_pre_ping=True)
    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(trust_env=False,transport=auth_transport) as http:
            app.state.auth=AuthClient(http,settings.identity_origin,settings.service_key); yield
        if owned: engine.dispose()
    app=FastAPI(title='Payment Service',lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
    app.state.engine=engine; app.state.settings=settings
    @app.middleware('http')
    async def context(request,call_next):
        token=request_settings.set(settings)
        try:
            response=await call_next(request); response.headers['X-Service-Name']='payment'; return response
        finally: request_settings.reset(token)
    @app.exception_handler(SQLAlchemyError)
    async def db_error(request,exc): return JSONResponse({'detail':'Payment chưa sẵn sàng; thử lại cùng giao dịch'},status_code=409 if isinstance(exc,IntegrityError) else 503)
    @app.get('/health/live')
    def live(): return dict(status='ok',service='payment')
    @app.get('/health/ready')
    def ready():
        try:
            with engine.connect() as conn: conn.execute(text('SELECT 1 FROM payment_reconciliation LIMIT 0'))
        except SQLAlchemyError: return JSONResponse(dict(status='not_ready',service='payment'),status_code=503)
        return dict(status='ready',service='payment')
    @app.get('/internal/v1/migration/state',dependencies=[Depends(private)])
    def migration(): return dict(writes_enabled=settings.writes_enabled)

    class URLRequest(BaseModel): bookingId:int=Field(gt=0)
    @app.post('/payment/vnpay-url',dependencies=[Depends(writes)])
    def url(body:URLRequest,request:Request,user=Depends(get_current_user),db=Depends(get_session)):
        if not settings.tmn_code or len(settings.hash_secret)<16: raise HTTPException(503,'VNPay chưa được cấu hình')
        fact=clients.checkout(body.bookingId)
        payment=service.attempt(db,fact,user.id)
        stamp=payment.created_at.astimezone(ZoneInfo('Asia/Ho_Chi_Minh'))
        params={'vnp_Version':'2.1.0','vnp_Command':'pay','vnp_TmnCode':settings.tmn_code,'vnp_Amount':str(int(payment.amount*100)),
            'vnp_CurrCode':'VND','vnp_TxnRef':payment.merchant_ref,'vnp_OrderInfo':f'Thanh toan ve phim booking {payment.booking_id}',
            'vnp_OrderType':'other','vnp_Locale':'vn','vnp_ReturnUrl':settings.frontend_url.rstrip('/')+'/payment-result',
            'vnp_CreateDate':stamp.strftime('%Y%m%d%H%M%S'),'vnp_ExpireDate':min(fact.deadline.astimezone(stamp.tzinfo),stamp+timedelta(minutes=10)).strftime('%Y%m%d%H%M%S'),
            'vnp_IpAddr':request.client.host if request.client else '127.0.0.1'}
        encoded='&'.join(f'{k}={urllib.parse.quote_plus(str(v))}' for k,v in sorted(params.items()))
        signature=hmac.new(settings.hash_secret.encode(),encoded.encode(),hashlib.sha512).hexdigest()
        return dict(paymentUrl=settings.vnpay_url+'?'+encoded+'&vnp_SecureHash='+signature)

    def reply(db,payment):
        data=service.view(db,payment.booking_id)
        stage=data['fulfillment_status']
        messages={'ISSUED':'Đơn đã được xác nhận và cấp vé','PROCESSING':'Đã thu tiền; đang xác nhận vé','REQUIRES_REVIEW':'Đã ghi nhận tiền; giao dịch cần hỗ trợ/đối soát','FAILED':'Cổng thanh toán thông báo giao dịch thất bại','AWAITING_PAYMENT':'Đang chờ kết quả giao dịch'}
        return dict(status='success' if stage=='ISSUED' else 'failed' if stage=='FAILED' else 'pending',booking=None,booking_id=payment.booking_id,
            provider_status=data['provider_status'],fulfillment_status=stage,requires_review=data['requires_review'],message=messages[stage])

    def callback(params,db,ipn=False):
        if len(settings.hash_secret)<16: raise HTTPException(503,'VNPay chưa được cấu hình')
        if not verify_vnpay_signature(params,settings.hash_secret):
            if ipn: return dict(RspCode='97',Message='Invalid Checksum')
            raise HTTPException(400,'Chữ ký VNPay không hợp lệ')
        try:
            payment,repeated,mismatch=service.record(db,params); db.commit()
        except HTTPException as exc:
            db.rollback()
            if not ipn: raise
            return dict(RspCode='01' if exc.status_code==404 else '99',Message=str(exc.detail))
        if ipn: return dict(RspCode='04' if mismatch else '02' if repeated else '00',Message='Invalid Amount' if mismatch else 'Order already confirmed' if repeated else 'Confirm Success')
        return reply(db,payment)

    @app.get('/payment/vnpay-return',dependencies=[Depends(writes)])
    def return_get(request:Request,db=Depends(get_session)):
        if len(request.query_params.multi_items())!=len(set(request.query_params.keys())): raise HTTPException(400,'Duplicate callback parameter')
        return callback(dict(request.query_params),db)
    @app.post('/payment/vnpay-return',dependencies=[Depends(writes)])
    def return_post(body:dict,db=Depends(get_session)): return callback(body,db)
    @app.get('/payment/vnpay-ipn',dependencies=[Depends(writes)])
    def ipn_get(request:Request,db=Depends(get_session)):
        if len(request.query_params.multi_items())!=len(set(request.query_params.keys())): return dict(RspCode='99',Message='Duplicate parameter')
        return callback(dict(request.query_params),db,True)
    @app.post('/payment/vnpay-ipn',dependencies=[Depends(writes)])
    async def ipn_post(request:Request,db=Depends(get_session)):
        if len(request.query_params.multi_items())!=len(set(request.query_params.keys())): return dict(RspCode='99',Message='Duplicate parameter')
        params=dict(request.query_params)
        try:
            body=await request.json() if 'application/json' in request.headers.get('content-type','') else dict(await request.form())
            if not isinstance(body,dict) or any(k in params and params[k]!=v for k,v in body.items()): raise ValueError()
            params.update(body)
        except (ValueError,TypeError): return dict(RspCode='99',Message='Invalid callback body')
        return callback(params,db,True)
    @app.get('/payment/status/{booking_id}')
    def status(booking_id:int,user=Depends(get_current_user),db=Depends(get_session)):
        data=service.view(db,booking_id,user.id)
        if data is None:
            fact=clients.checkout(booking_id)
            if fact.user_id!=user.id: raise HTTPException(403,'Bạn không có quyền xem giao dịch')
            service.register(db,fact); db.commit(); data=service.view(db,booking_id,user.id)
        return data

    @app.get('/admin/payment-reconciliation')
    def cases(user=Depends(require_permission('reports.view')),db=Depends(get_session),offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200)):
        from sqlalchemy import func
        from sqlalchemy import and_
        query=select(Case,Payment,Checkout,Fulfillment).join(Payment,Payment.id==Case.payment_id).join(Checkout,and_(Checkout.booking_id==Payment.booking_id,Checkout.booking_version==Payment.checkout_version)).outerjoin(Fulfillment,Fulfillment.payment_id==Payment.id).where(Case.status=='OPEN').order_by(Case.created_at,Case.id)
        items=[]
        for row,payment,checkout,fulfillment in db.execute(query.offset(offset).limit(limit)):
            items.append({**{c.name:getattr(row,c.name) for c in Case.__table__.columns},'booking_id':payment.booking_id,'expected_amount':str(payment.amount),'currency':payment.currency,'merchant_ref':payment.merchant_ref,'transaction_ref':payment.transaction_ref,'provider_status':payment.status,'confirmation':fulfillment.outcome if fulfillment else 'PENDING'})
        return dict(items=items,total=db.scalar(select(func.count()).select_from(Case).where(Case.status=='OPEN')))
    class Retry(BaseModel): reason:str=Field(min_length=1,max_length=500)
    @app.post('/admin/payment-reconciliation/{case_id}/retry',dependencies=[Depends(writes)])
    def retry(case_id:str,body:Retry,user=Depends(require_permission('reports.view')),db=Depends(get_session)):
        from .reconcile import retry_capture
        if not body.reason.strip(): raise HTTPException(422,'Lý do kiểm tra không được để trống')
        case=db.get(Case,case_id)
        if case is None: raise HTTPException(404,'Không có hồ sơ')
        service.lock(db,db.get(Payment,case.payment_id).booking_id)
        queued=retry_capture(db,case.payment_id)
        db.add(ReplayAudit(record_id=case_id,actor=f'user:{user.id}',reason=body.reason)); db.commit()
        return dict(queued=queued,message='Đã ghi nhận yêu cầu đối soát; kiểm tra kết quả xác nhận trước khi xử lý tiền')
    return app

def application(): return create_app()
