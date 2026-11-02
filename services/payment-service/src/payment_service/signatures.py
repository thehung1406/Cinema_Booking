import hashlib,hmac,urllib.parse

def verify_vnpay_signature(params: dict,secret: str) -> bool:
    """
    Xác thực chữ ký HMAC-SHA512 của VNPay.
    Lọc bỏ vnp_SecureHash, vnp_SecureHashType và các giá trị rỗng/None.
    Sắp xếp các tham số theo thứ tự alphabet và băm dữ liệu với HASH_SECRET.
    """
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
        secret.encode("utf-8"),
        hash_data.encode("utf-8"),
        hashlib.sha512
    ).hexdigest()
    return hmac.compare_digest(expected_hash.lower(), str(secure_hash).lower())
