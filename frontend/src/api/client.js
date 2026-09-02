import axios from 'axios';

const API_BASE_URL = 'https://studygenie-1-aunj.onrender.com/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: attach JWT token if available
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('studygenie_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: handle token expiry
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // If 401 unauthorized, clear token if not on login/register endpoints
      const isAuthUrl = error.config.url?.includes('/auth/login') || error.config.url?.includes('/auth/register');
      if (!isAuthUrl) {
        localStorage.removeItem('studygenie_token');
        localStorage.removeItem('studygenie_user');
        window.dispatchEvent(new Event('studygenie_logout'));
      }
    }
    return Promise.reject(error);
  }
);

export default api;
