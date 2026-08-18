import axios from 'axios';
import { clearSession, getAccessToken } from '../services/authStorage';

// Base URL cho API - ưu tiên env, development mặc định dùng proxy của Vite.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL
  || (import.meta.env.MODE === 'development'
    ? import.meta.env.VITE_API_PROXY_PATH || '/api'
    : '/api');

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
    const token = getAccessToken();
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
      clearSession();
      window.location.href = '/LoginPage';
    }
    return Promise.reject(error);
  }
);

export default api;
