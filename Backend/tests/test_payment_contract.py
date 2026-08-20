import ast
import hashlib
import hmac
import os
import sys
import urllib.parse
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
FRONTEND_ROOT = REPO_ROOT / "Frontend" / "src"

sys.path.insert(0, str(BACKEND_ROOT))

# Set test environment variables
os.environ.setdefault("PROJECT_NAME", "Cinema Booking Test")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "15")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_DAYS", "30")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_DB", "test")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("REDIS_DB", "0")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("TMN_CODE", "SANDBOX_TMN")
os.environ.setdefault("HASH_SECRET", "SANDBOX_HASH_SECRET_KEY")
os.environ.setdefault("VNPAY_URL", "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

from app.schemas.payment import (
    VNPayURLRequest,
    VNPayURLResponse,
    VNPayReturnRequest,
    PaymentConfirmResponse,
    VNPayIPNResponse,
)


def verify_vnpay_signature_standalone(params: dict, secret_key: str) -> bool:
    """Xác thực chữ ký HMAC-SHA512 của VNPay."""
    secure_hash = params.get("vnp_SecureHash")
    if not secure_hash:
        return False

    signed_params = {
        key: value
        for key, value in params.items()
        if key.startswith("vnp_")
        and key not in {"vnp_SecureHash", "vnp_SecureHashType"}
        and value is not None
        and str(value) != ""
    }
    sorted_params = sorted(signed_params.items())
    hash_data = "&".join(
        f"{key}={urllib.parse.quote_plus(str(value))}"
        for key, value in sorted_params
    )
    expected_hash = hmac.new(
        secret_key.encode("utf-8"),
        hash_data.encode("utf-8"),
        hashlib.sha512
    ).hexdigest()
    return hmac.compare_digest(expected_hash.lower(), str(secure_hash).lower())


def test_verify_vnpay_signature_valid():
    """Kiểm tra xác thực chữ ký VNPay HMAC-SHA512 hợp lệ."""
    secret = "TEST_SECRET_KEY_12345"
    params = {
        "vnp_Amount": "10000000",
        "vnp_BankCode": "NCB",
        "vnp_Command": "pay",
        "vnp_CreateDate": "20260820090000",
        "vnp_CurrCode": "VND",
        "vnp_OrderInfo": "Thanh toan ve phim booking 1",
        "vnp_ResponseCode": "00",
        "vnp_TmnCode": "TESTTMN",
        "vnp_TxnRef": "1",
        "vnp_Version": "2.1.0",
    }
    # Sinh hash
    signed_params = {k: v for k, v in params.items() if k.startswith("vnp_")}
    sorted_params = sorted(signed_params.items())
    hash_data = "&".join(f"{k}={urllib.parse.quote_plus(str(v))}" for k, v in sorted_params)
    secure_hash = hmac.new(secret.encode("utf-8"), hash_data.encode("utf-8"), hashlib.sha512).hexdigest()
    params["vnp_SecureHash"] = secure_hash

    assert verify_vnpay_signature_standalone(params, secret) is True


def test_verify_vnpay_signature_tampered():
    """Kiểm tra phát hiện chữ ký bị giả mạo / sửa đổi số tiền."""
    secret = "TEST_SECRET_KEY_12345"
    params = {
        "vnp_Amount": "10000000",
        "vnp_BankCode": "NCB",
        "vnp_ResponseCode": "00",
        "vnp_TxnRef": "1",
    }
    signed_params = sorted(params.items())
    hash_data = "&".join(f"{k}={urllib.parse.quote_plus(str(v))}" for k, v in signed_params)
    secure_hash = hmac.new(secret.encode("utf-8"), hash_data.encode("utf-8"), hashlib.sha512).hexdigest()
    params["vnp_SecureHash"] = secure_hash

    # Giả mạo số tiền sang 50,000 VND
    params["vnp_Amount"] = "5000000"

    assert verify_vnpay_signature_standalone(params, secret) is False


def test_verify_vnpay_signature_missing_or_empty():
    """Kiểm tra xử lý chữ ký bị thiếu hoặc rỗng."""
    secret = "TEST_SECRET_KEY_12345"
    assert verify_vnpay_signature_standalone({}, secret) is False
    assert verify_vnpay_signature_standalone({"vnp_SecureHash": ""}, secret) is False
    assert verify_vnpay_signature_standalone({"vnp_TxnRef": "1"}, secret) is False


def test_payment_schemas_fields():
    """Kiểm tra định nghĩa các schema thanh toán."""
    url_req_fields = set(VNPayURLRequest.model_fields.keys())
    assert {"bookingId", "amount", "orderInfo", "returnUrl"}.issubset(url_req_fields)

    url_res_fields = set(VNPayURLResponse.model_fields.keys())
    assert "paymentUrl" in url_res_fields

    return_req_fields = set(VNPayReturnRequest.model_fields.keys())
    assert {"vnp_ResponseCode", "vnp_SecureHash"}.issubset(return_req_fields)

    ipn_res_fields = set(VNPayIPNResponse.model_fields.keys())
    assert {"RspCode", "Message"}.issubset(ipn_res_fields)


def test_payment_router_endpoints_exist():
    """Kiểm tra Router Payment định nghĩa đầy đủ các endpoint theo yêu cầu."""
    router_source = (BACKEND_ROOT / "app" / "router" / "payment.py").read_text(encoding="utf-8")
    parsed = ast.parse(router_source)

    function_names = {node.name for node in parsed.body if isinstance(node, ast.FunctionDef)}
    assert "verify_vnpay_signature" in function_names
    assert "create_vnpay_url" in function_names
    assert "vnpay_return_post" in function_names
    assert "vnpay_return_get" in function_names
    assert "vnpay_ipn_get" in function_names
    assert "vnpay_ipn_post" in function_names
    assert "get_payment_status" in function_names

    assert '"/vnpay-url"' in router_source
    assert '"/vnpay-return"' in router_source
    assert '"/vnpay-ipn"' in router_source
    assert '"/status/{booking_id}"' in router_source


def test_payment_service_methods_and_status_transitions():
    """Kiểm tra PaymentService có đầy đủ logic cập nhật trạng thái PAID, BOOKED, FAILED và IPN."""
    service_source = (BACKEND_ROOT / "app" / "services" / "payment_service.py").read_text(encoding="utf-8")

    assert "def confirm_vnpay_payment" in service_source
    assert "def process_vnpay_ipn" in service_source
    assert "def get_payment_status" in service_source

    # Kiểm tra chuyển trạng thái sang PAID và gọi book_seat_optimistic
    assert 'payment_status="PAID"' in service_source
    assert "SeatRepository.book_seat_optimistic" in service_source
    assert "SeatLockManager.unlock_seat" in service_source

    # Kiểm tra xử lý khi thanh toán thất bại (FAILED)
    assert 'payment_status="FAILED"' in service_source
    assert "SeatRepository.release_seat_optimistic" in service_source

    # Kiểm tra IPN return codes chuẩn VNPay
    assert '"RspCode": "00"' in service_source
    assert '"RspCode": "97"' in service_source
    assert '"RspCode": "01"' in service_source
    assert '"RspCode": "02"' in service_source
    assert '"RspCode": "04"' in service_source


def test_vnpay_url_generation_uses_sha512_and_amount_multiplier():
    """Kiểm tra logic sinh URL thanh toán VNPay dùng HMAC-SHA512 và nhân 100 số tiền."""
    router_source = (BACKEND_ROOT / "app" / "router" / "payment.py").read_text(encoding="utf-8")

    assert "hashlib.sha512" in router_source
    assert "request.amount * 100" in router_source
    assert "vnp_SecureHash" in router_source
    assert "vnp_Version" in router_source
    assert "vnp_Command" in router_source
    assert "vnp_TmnCode" in router_source


def test_frontend_payment_components_contract():
    """Kiểm tra các component Frontend PaymentPage và VNPayReturn."""
    payment_page_src = (FRONTEND_ROOT / "components" / "PaymentPage.jsx").read_text(encoding="utf-8")
    vnpay_return_src = (FRONTEND_ROOT / "components" / "VNPayReturn.jsx").read_text(encoding="utf-8")
    app_src = (FRONTEND_ROOT / "App.jsx").read_text(encoding="utf-8")

    # PaymentPage checks
    assert "/payment/vnpay-url" in payment_page_src
    assert "bookingId" in payment_page_src
    assert "/payment-result" in payment_page_src
    assert "Thanh toán qua VNPay" in payment_page_src
    assert "secondsLeft" in payment_page_src

    # VNPayReturn checks
    assert "/payment/vnpay-return" in vnpay_return_src
    assert "vnp_ResponseCode" in vnpay_return_src
    assert "vnp_TxnRef" in vnpay_return_src
    assert "QRCode" in vnpay_return_src
    assert "VNPAY_RESPONSE_MESSAGES" in vnpay_return_src
    assert "Thanh toán thành công" in vnpay_return_src

    # App.jsx routing checks
    assert 'path="payment/:bookingId"' in app_src
    assert 'path="payment-result"' in app_src
