import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const client = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// attach saved token to every request
client.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    // debug log for job POST 403s
    if (config.url?.includes('/jobs') && config.method === 'post') {
      console.log('Creating job - Request config:', {
        url: config.url,
        method: config.method,
        data: config.data,
        headers: {
          ...config.headers,
          Authorization: config.headers.Authorization ? 'Bearer ***' : 'Missing'
        }
      });
    }
    
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// plain Errors from axios; handle 401s
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const status = error.response.status;
      const data = error.response.data;

      // bad token: clear and go to login
      if (status === 401) {
        localStorage.removeItem('token');
        delete client.defaults.headers.common['Authorization'];
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
      }

      if (status === 403) {
        const message = data?.detail || data?.message || 'You do not have permission to perform this action';
        return Promise.reject(new Error(message));
      }

      const message = data?.detail || data?.message || `Error ${status}: An error occurred`;
      return Promise.reject(new Error(message));
    } else if (error.request) {
      // request sent, no response (network or server down)
      return Promise.reject(new Error('No response from server. Please check your connection.'));
    } else {
      return Promise.reject(error);
    }
  }
);

export default client;

