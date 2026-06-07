import client from './client';

export const rankingApi = {
  getRankedCandidates: (jobId) => client.get(`/ranking/job/${jobId}`),
};

