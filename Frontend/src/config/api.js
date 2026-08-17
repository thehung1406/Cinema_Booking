import axios from 'axios';

// Base URL cho API - sử dụng proxy trong development
export const API_BASE_URL = import.meta.env.MODE === 'development' 
  ? '/api' 
  : 'http://localhost:8000';

// Tạo axios instance với cấu hình mặc định
export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor để thêm token vào mọi request
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Interceptor để xử lý response errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token hết hạn hoặc không hợp lệ
      localStorage.removeItem('token');
      localStorage.removeItem('isLoggedIn');
      window.location.href = '/LoginPage';
    }
    return Promise.reject(error);
  }
);

export default api;
