import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';


const API_BASE_URL = 'http://localhost:8000';

const LoginPage = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
    phone: '',
    fullName: ''
  });
  const [rememberMe, setRememberMe] = useState(false);
  const [isSignUp, setIsSignUp] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const handleChange = (e) => {
    const { id, value } = e.target;
    setFormData(prevState => ({
      ...prevState,
      [id]: value
    }));
  };
  // Toggle between login and signup modes
  const toggleMode = () => {
    setIsSignUp(!isSignUp);
    setError('');
  };
  // Form validation
  const validateForm = () => {
    if (isSignUp) {
      // Signup validation
      if (!formData.username.trim()) {
        setError('Vui lòng nhập tên đăng nhập');
        return false;
      }
      if (!formData.fullName.trim()) {
        setError('Vui lòng nhập họ tên đầy đủ');
        return false;
      }
      if (!formData.email.trim()) {
        setError('Vui lòng nhập email');
        return false;
      }
      const emailRegex = /^[a-zA-Z0-9._%+-]+@gmail\.com$/;
      if (!emailRegex.test(formData.email)) {
        setError('Email phải có đuôi @gmail.com');
        return false;
      }
      if (formData.password !== formData.confirmPassword) {
        setError('Mật khẩu xác nhận không khớp');
        return false;
      }
      if (formData.password.length < 6) {
        setError('Mật khẩu phải có ít nhất 6 ký tự');
        return false;
      }
    } else {
      // Login validation
      if (!formData.username.trim()) {
        setError('Vui lòng nhập tên đăng nhập');
        return false;
      }
      if (!formData.password) {
        setError('Vui lòng nhập mật khẩu');
        return false;
      }
    }
    return true;
  };
  // Handle form submission
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    
    // Validate form
    if (!validateForm()) {
      return;
    }
    setLoading(true);
    
    try {
      let response;
      
      if (isSignUp) {
        // Registration request
        response = await axios.post(`${API_BASE_URL}/auth/register`, {
          username: formData.username,
          email: formData.email,
          password: formData.password,
          phone: formData.phone,
          full_name: formData.fullName
        });
        
        // If registration successful, automatically log in
        if (response.data) {
          const loginFormData = new URLSearchParams();
          loginFormData.append('username', formData.username);
          loginFormData.append('password', formData.password);
          
          const loginResponse = await axios.post(`${API_BASE_URL}/auth/login`, loginFormData, {
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded'
            }
          });
          
          handleLoginSuccess(loginResponse.data, response.data);
        }
      } else {
        // Login request - Gửi dữ liệu dạng form-data (OAuth2PasswordRequestForm)
        const loginFormData = new URLSearchParams();
        loginFormData.append('username', formData.username);
        loginFormData.append('password', formData.password);
        
        response = await axios.post(`${API_BASE_URL}/auth/login`, loginFormData, {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
          }
        });
        
        handleLoginSuccess(response.data);
      }
    } catch (err) {
      console.error(isSignUp ? 'Lỗi đăng ký:' : 'Lỗi đăng nhập:', err);
      const errorMessage = err.response?.data?.detail || 
        err.response?.data?.message ||
        (isSignUp ? 'Đã có lỗi xảy ra khi đăng ký. Vui lòng thử lại.' : 
                  'Đã có lỗi xảy ra khi đăng nhập. Vui lòng thử lại.');
      setError(typeof errorMessage === 'string' ? errorMessage : JSON.stringify(errorMessage));
    } finally {
      setLoading(false);
    }
  };

  // Handle successful login
  const handleLoginSuccess = async (loginData, userData = null) => {
    const { access_token, refresh_token, token_type } = loginData;
  
    // Save user info if available (from registration)
    if (userData) {
      // Lưu cả token và user info
      const userInfoWithToken = {
        ...userData,
        access_token: access_token,
        refresh_token: refresh_token,
        token_type: token_type || 'bearer'
      };
      localStorage.setItem('userInfo', JSON.stringify(userInfoWithToken));
    } else {
      // Lấy thông tin user từ API /auth/me
      try {
        const userResponse = await axios.get(`${API_BASE_URL}/auth/me`, {
          headers: {
            'Authorization': `${token_type} ${access_token}`
          }
        });
        // Lưu cả token và user info
        const userInfoWithToken = {
          ...userResponse.data,
          access_token: access_token,
          refresh_token: refresh_token,
          token_type: token_type || 'bearer'
        };
        localStorage.setItem('userInfo', JSON.stringify(userInfoWithToken));
      } catch (error) {
        console.error('Lỗi khi lấy thông tin user:', error);
      }
    }
    
    // Dispatch event để HomePage cập nhật trạng thái
    window.dispatchEvent(new Event('loginStatusChanged'));
    
    // Redirect to home page
    navigate(-1);
  };
  return (
    <div className="min-h-screen flex items-center justify-center bg-black relative overflow-hidden">
      <div className="absolute inset-0 z-0">
        <div className="absolute bottom-0 left-0 right-0 h-40 bg-red-900 transform skew-y-2"></div>
        <div className="absolute bottom-8 left-0 right-0 h-40 bg-red-800 transform skew-y-3"></div>
        <div className="absolute bottom-16 left-0 right-0 h-40 bg-red-700 transform skew-y-4"></div>
        <div className="absolute top-10 left-0 right-0 h-8 bg-gray-800 flex">
          {Array.from({ length: 20 }).map((_, i) => (
            <div key={i} className="h-full w-8 mx-1 bg-gray-900"></div>
          ))}
        </div>
        <div className="absolute bottom-96 left-0 right-0 h-8 bg-gray-800 flex">
          {Array.from({ length: 20 }).map((_, i) => (
            <div key={i} className="h-full w-8 mx-1 bg-gray-900"></div>
          ))}
        </div>
        <div className="absolute top-32 left-1/2 transform -translate-x-1/2 w-4/5 h-28 bg-gradient-to-b from-blue-300 to-transparent opacity-20 rounded-t-full"></div>

        <div className="absolute top-0 left-1/4 w-40 h-96 bg-yellow-100 opacity-10 transform rotate-12 rounded-b-full"></div>
        <div className="absolute top-0 right-1/4 w-40 h-96 bg-yellow-100 opacity-10 transform -rotate-12 rounded-b-full"></div>
      </div>
      
      {/* Login/Register form card */}
      <div className="relative z-10 bg-gray-900 p-8 rounded-lg shadow-2xl max-w-md w-full mx-4 border border-gray-700">
        <div className="text-center mb-6">
          <h1 className="text-red-600 text-3xl font-bold uppercase tracking-wider mb-1">
            CGV Cinema
          </h1>
          <div className="w-full flex justify-center mb-4">
            <div className="h-1 w-16 bg-red-600 rounded"></div>
          </div>
          <h2 className="text-white text-xl font-semibold">
            {isSignUp ? "Tạo Tài Khoản" : "Chào mừng trở lại"}
          </h2>
          <p className="text-gray-400 mt-2">
            {isSignUp 
              ? "Tham gia với chúng tôi để đặt vé và tận hưởng những lợi ích độc quyền" 
              : "Đăng nhập để truy cập tài khoản của bạn và đặt vé"}
          </p>
        </div>
        
        <form onSubmit={handleSubmit}>
          {error && (
            <div className="mb-4 p-3 bg-red-900/50 border border-red-500 rounded text-red-200 text-sm">
              {error}
            </div>
          )}
          
          <div className="mb-4">
            <label className="block text-gray-300 text-sm font-medium mb-2" htmlFor="username">
              Tên đăng nhập
            </label>
            <input
              id="username"
              type="text"
              className="w-full px-4 py-3 rounded-lg bg-gray-800 text-white border border-gray-700 focus:border-red-500 focus:outline-none focus:ring-1 focus:ring-red-500"
              placeholder="Nhập tên đăng nhập"
              value={formData.username}
              onChange={handleChange}
              required
            />
          </div>
          
          {isSignUp && (
            <>
              <div className="mb-4">
                <label className="block text-gray-300 text-sm font-medium mb-2" htmlFor="fullName">
                  Họ tên đầy đủ
                </label>
                <input
                  id="fullName"
                  type="text"
                  className="w-full px-4 py-3 rounded-lg bg-gray-800 text-white border border-gray-700 focus:border-red-500 focus:outline-none focus:ring-1 focus:ring-red-500"
                  placeholder="Nhập họ tên đầy đủ"
                  value={formData.fullName}
                  onChange={handleChange}
                  required
                />
              </div>
              
              <div className="mb-4">
                <label className="block text-gray-300 text-sm font-medium mb-2" htmlFor="email">
                  Địa chỉ email
                </label>
                <input
                  id="email"
                  type="email"
                  pattern="[a-zA-Z0-9._%+-]+@gmail\.com"
                  className="w-full px-4 py-3 rounded-lg bg-gray-800 text-white border border-gray-700 focus:border-red-500 focus:outline-none focus:ring-1 focus:ring-red-500 invalid:border-red-500"
                  placeholder="example@gmail.com"
                  value={formData.email}
                  onChange={handleChange}
                  required
                  title="Email phải có đuôi @gmail.com (ví dụ: user@gmail.com)"
                />
              </div>
              
              <div className="mb-4">
                <label className="block text-gray-300 text-sm font-medium mb-2" htmlFor="phone">
                  Số điện thoại
                </label>
                <input
                  id="phone"
                  type="tel"
                  className="w-full px-4 py-3 rounded-lg bg-gray-800 text-white border border-gray-700 focus:border-red-500 focus:outline-none focus:ring-1 focus:ring-red-500"
                  placeholder="Nhập số điện thoại"
                  value={formData.phone}
                  onChange={handleChange}
                />
              </div>
            </>
          )}
          
          <div className="mb-4">
            <div className="flex justify-between items-center mb-2">
              <label className="block text-gray-300 text-sm font-medium" htmlFor="password">
                Mật khẩu
              </label>
              {!isSignUp && (
                <a href="#" className="text-sm text-red-500 hover:text-red-400">
                  Quên mật khẩu?
                </a>
              )}
            </div>
            <input
              id="password"
              type="password"
              className="w-full px-4 py-3 rounded-lg bg-gray-800 text-white border border-gray-700 focus:border-red-500 focus:outline-none focus:ring-1 focus:ring-red-500"
              placeholder="Điền mật khẩu của bạn"
              value={formData.password}
              onChange={handleChange}
              required
            />
          </div>
          
          {isSignUp && (
            <div className="mb-4">
              <label className="block text-gray-300 text-sm font-medium mb-2" htmlFor="confirmPassword">
                Xác nhận mật khẩu
              </label>
              <input
                id="confirmPassword"
                type="password"
                className="w-full px-4 py-3 rounded-lg bg-gray-800 text-white border border-gray-700 focus:border-red-500 focus:outline-none focus:ring-1 focus:ring-red-500"
                placeholder="Xác nhận mật khẩu"
                value={formData.confirmPassword}
                onChange={handleChange}
                required
              />
            </div>
          )}
          
          <div className="flex items-center mb-6">
            <input
              id="remember-me"
              type="checkbox"
              className="h-4 w-4 text-red-600 focus:ring-red-500 border-gray-700 rounded"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
            />
            <label htmlFor="remember-me" className="ml-2 block text-sm text-gray-300">
              {isSignUp ? "Tôi đồng ý với các điều khoản và điều kiện." : "Ghi nhớ tôi"}
            </label>
          </div>
          
          <button
            type="submit"
            disabled={loading}
            className={`w-full bg-red-600 hover:bg-red-700 text-white font-bold py-3 px-4 rounded-lg focus:outline-none focus:shadow-outline transition duration-300 ${
              loading ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {loading ? 'Đang xử lý...' : (isSignUp ? 'Tạo tài khoản mới' : 'Đăng nhập')}
          </button>
        </form>
        
        <div className="mt-6 text-center">
          <p className="text-gray-400">
            {isSignUp 
              ? "Đã có tài khoản? " 
              : "Chưa có tài khoản? "}
            <button 
              className="ml-1 text-red-500 hover:text-red-400 font-medium"
              onClick={toggleMode}
            >
              {isSignUp ? "Đăng nhập" : "Đăng ký"}
            </button>
          </p>
        </div>
        
        <div className="mt-6 pt-6 border-t border-gray-700">
          <p className="text-center text-gray-500 text-sm">
            &copy; 2025 CGV All rights reserved.
          </p>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;