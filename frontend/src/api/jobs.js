import client from './client';

export const jobsApi = {
  getAll: () => client.get('/jobs'),
  getById: (id) => client.get(`/jobs/${id}`),
  create: (data) => client.post('/jobs', data),
  update: (id, data) => client.put(`/jobs/${id}`, data),
  delete: (id) => client.delete(`/jobs/${id}`),
};

