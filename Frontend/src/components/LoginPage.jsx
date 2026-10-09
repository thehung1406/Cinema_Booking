import { Button, FormField } from "./ui/Primitives";
import React, { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import api from "../config/api";
import { setSession } from "../services/authStorage";
import logger from "../utils/logger";

const LoginPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [formData, setFormData] = useState({
    username: "",
    email: "",
    password: "",
    confirmPassword: "",
    phone: "",
    fullName: "",
  });

  const [isSignUp, setIsSignUp] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const handleChange = (e) => {
    const { id, value } = e.target;
    setFormData((prevState) => ({
      ...prevState,
      [id]: value,
    }));
  };
  // Toggle between login and signup modes
  const toggleMode = () => {
    setIsSignUp(!isSignUp);
    setError("");
  };
  // Form validation
  const validateForm = () => {
    if (isSignUp) {
      // Signup validation
      if (!formData.username.trim()) {
        setError("Vui lòng nhập tên đăng nhập");
        return false;
      }
      if (!formData.fullName.trim()) {
        setError("Vui lòng nhập họ tên đầy đủ");
        return false;
      }
      if (!formData.email.trim()) {
        setError("Vui lòng nhập email");
        return false;
      }
      const emailRegex = /^[a-zA-Z0-9._%+-]+@gmail\.com$/;
      if (!emailRegex.test(formData.email)) {
        setError("Email phải có đuôi @gmail.com");
        return false;
      }
      if (formData.password !== formData.confirmPassword) {
        setError("Mật khẩu xác nhận không khớp");
        return false;
      }
      if (formData.password.length < 6) {
        setError("Mật khẩu phải có ít nhất 6 ký tự");
        return false;
      }
    } else {
      // Login validation
      if (!formData.username.trim()) {
        setError("Vui lòng nhập tên đăng nhập");
        return false;
      }
      if (!formData.password) {
        setError("Vui lòng nhập mật khẩu");
        return false;
      }
    }
    return true;
  };
  // Handle form submission
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    // Validate form
    if (!validateForm()) {
      return;
    }
    setLoading(true);

    try {
      let response;

      if (isSignUp) {
        // Registration request
        response = await api.post("/auth/register", {
          username: formData.username,
          email: formData.email,
          password: formData.password,
          phone: formData.phone,
          full_name: formData.fullName,
        });

        // If registration successful, automatically log in
        if (response.data) {
          const loginFormData = new URLSearchParams();
          loginFormData.append("username", formData.username);
          loginFormData.append("password", formData.password);

          const loginResponse = await api.post("/auth/login", loginFormData, {
            headers: {
              "Content-Type": "application/x-www-form-urlencoded",
            },
          });

          await handleLoginSuccess(loginResponse.data, response.data);
        }
      } else {
        // Login request - Gửi dữ liệu dạng form-data (OAuth2PasswordRequestForm)
        const loginFormData = new URLSearchParams();
        loginFormData.append("username", formData.username);
        loginFormData.append("password", formData.password);

        response = await api.post("/auth/login", loginFormData, {
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
          },
        });

        await handleLoginSuccess(response.data);
      }
    } catch (err) {
      logger.error(isSignUp ? "Lỗi đăng ký:" : "Lỗi đăng nhập:", err);
      const errorMessage =
        err.response?.data?.detail ||
        err.response?.data?.message ||
        (isSignUp
          ? "Đã có lỗi xảy ra khi đăng ký. Vui lòng thử lại."
          : "Đã có lỗi xảy ra khi đăng nhập. Vui lòng thử lại.");
      setError(
        typeof errorMessage === "string"
          ? errorMessage
          : JSON.stringify(errorMessage),
      );
    } finally {
      setLoading(false);
    }
  };

  // Handle successful login
  const handleLoginSuccess = async (loginData, userData = null) => {
    const { access_token } = loginData;

    // Save user info if available (from registration)
    if (userData) {
      // Lưu cả token và user info
      setSession(loginData, userData);
    } else {
      // Lấy thông tin user từ API /auth/me
      try {
        const userResponse = await api.get("/auth/me", {
          headers: {
            Authorization: `Bearer ${access_token}`,
          },
        });
        setSession(loginData, userResponse.data);
      } catch (error) {
        logger.error("Lỗi khi lấy thông tin user:", error);
        throw error;
      }
    }

    // Resume the booking route supplied by the login guard.
    navigate(location.state?.redirectTo || "/", { replace: true });
  };
  return (
    <div className="auth-page">
      <div className="auth-card">
        <Link
          to="/"
          className="brand inline-block mb-7"
          aria-label="CGV — Trang chủ"
        >
          CGV
        </Link>
        <p className="eyebrow">Tài khoản Cinema</p>
        <h1 className="page-title !text-3xl">
          {isSignUp ? "Tạo tài khoản" : "Chào mừng trở lại"}
        </h1>
        <p className="text-gray-500 text-sm leading-6 mb-6">
          {isSignUp
            ? "Đăng ký để đặt vé và quản lý các buổi xem phim."
            : "Đăng nhập để chọn ghế và tiếp tục đặt vé."}
        </p>
        {location.state?.message && (
          <p
            role="status"
            className="bg-amber-50 text-amber-800 text-sm p-3 rounded-lg mb-4"
          >
            {location.state.message}
          </p>
        )}
        <form onSubmit={handleSubmit} className="space-y-4" aria-busy={loading}>
          {error && (
            <div
              id="auth-error"
              role="alert"
              className="bg-red-50 text-red-800 border border-red-200 p-3 rounded-lg text-sm"
            >
              {error}
            </div>
          )}
          <FormField
            label="Tên đăng nhập"
            id="username"
            name="username"
            autoComplete="username"
            value={formData.username}
            onChange={handleChange}
            placeholder="Nhập tên đăng nhập"
            required
            disabled={loading}
            aria-describedby={error ? "auth-error" : undefined}
          />
          {isSignUp && (
            <>
              <FormField
                label="Họ và tên"
                id="fullName"
                name="fullName"
                autoComplete="name"
                value={formData.fullName}
                onChange={handleChange}
                required
                disabled={loading}
              />
              <FormField
                label="Email"
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                pattern="[a-zA-Z0-9._%+-]+@gmail\\.com"
                hint="Sử dụng địa chỉ Gmail theo yêu cầu đăng ký hiện tại."
                value={formData.email}
                onChange={handleChange}
                required
                disabled={loading}
              />
              <FormField
                label="Số điện thoại"
                id="phone"
                name="phone"
                type="tel"
                autoComplete="tel"
                value={formData.phone}
                onChange={handleChange}
                disabled={loading}
              />
            </>
          )}
          <FormField
            label="Mật khẩu"
            id="password"
            name="password"
            type="password"
            autoComplete={isSignUp ? "new-password" : "current-password"}
            hint={isSignUp ? "Ít nhất 6 ký tự." : undefined}
            minLength={isSignUp ? 6 : undefined}
            value={formData.password}
            onChange={handleChange}
            required
            disabled={loading}
          />
          {isSignUp && (
            <FormField
              label="Xác nhận mật khẩu"
              id="confirmPassword"
              name="confirmPassword"
              type="password"
              autoComplete="new-password"
              value={formData.confirmPassword}
              onChange={handleChange}
              required
              disabled={loading}
            />
          )}
          <Button type="submit" className="w-full mt-2" busy={loading}>
            {loading ? "Đang xử lý…" : isSignUp ? "Tạo tài khoản" : "Đăng nhập"}
          </Button>
        </form>
        <div className="border-t border-gray-200 pt-5 mt-6 text-center">
          <p className="text-gray-500 text-sm">
            {isSignUp ? "Đã có tài khoản?" : "Chưa có tài khoản?"}
          </p>
          <Button variant="ghost" onClick={toggleMode} disabled={loading}>
            {isSignUp ? "Đăng nhập" : "Đăng ký tài khoản"}
          </Button>
        </div>
        <Link to="/" className="block text-center text-sm text-gray-500 py-3">
          ← Về trang chủ
        </Link>
      </div>
    </div>
  );
};

export default LoginPage;
