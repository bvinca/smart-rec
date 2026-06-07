import client from './client';

export const analyticsApi = {
  get: () => client.get('/analytics'),
};

