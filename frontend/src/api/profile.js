import client from './client';

export const profileApi = {
  get: () => client.get('/profile'),
  
  update: (data) => client.put('/profile', data),
  
  getResume: () => client.get('/profile/resume'),
  
  uploadResume: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return client.post('/profile/resume', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },
  
  generateSummary: () => client.post('/profile/resume/generate-summary'),
  
  delete: () => client.delete('/profile'),
};

