import os
import sys
import unittest
import ast
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))


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
os.environ.setdefault("TMN_CODE", "test")
os.environ.setdefault("HASH_SECRET", "test")
os.environ.setdefault("VNPAY_URL", "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

from app.schemas.auth import UserRead


class AuthContractTest(unittest.TestCase):
    def test_user_read_exposes_username_without_password(self):
        fields = set(UserRead.model_fields)

        self.assertIn("username", fields)
        self.assertNotIn("password", fields)

    def test_me_route_uses_safe_user_response_model(self):
        auth_router = ast.parse((BACKEND_ROOT / "app" / "router" / "auth.py").read_text())
        get_me = next(node for node in auth_router.body if isinstance(node, ast.FunctionDef) and node.name == "get_me")
        route_decorator = next(
            decorator
            for decorator in get_me.decorator_list
            if isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr == "get"
        )
        response_model = next(
            (keyword.value for keyword in route_decorator.keywords if keyword.arg == "response_model"),
            None,
        )

        self.assertIsNotNone(response_model)
        self.assertIsInstance(response_model, ast.Name)
        self.assertEqual(response_model.id, "UserRead")


if __name__ == "__main__":
    unittest.main()
