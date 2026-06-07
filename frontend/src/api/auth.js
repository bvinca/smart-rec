import client from './client';

export const authApi = {
  register: (data) => client.post('/auth/register', data),
  login: (email, password) => {
    const formData = new FormData();
    formData.append('username', email); // OAuth2 form field is username
    formData.append('password', password);
    return client.post('/auth/login', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },
  getCurrentUser: () => client.get('/auth/me'),
  logout: () => client.post('/auth/logout'),
  requestPasswordReset: (email) =>
    client.post('/auth/request-password-reset', { email }),
  confirmPasswordReset: (token, newPassword) =>
    client.post('/auth/confirm-password-reset', {
      token,
      new_password: newPassword,
    }),
  changePassword: (currentPassword, newPassword) =>
    client.post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    }),
};

