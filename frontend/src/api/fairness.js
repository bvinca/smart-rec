import client from './client';

export const fairnessApi = {
  auditFairness: (jobId = null, groupKey = 'experience_tier', scoreKey = 'overall_score', threshold = 10.0) => {
    return client.post('/fairness/audit', {
      job_id: jobId,
      group_key: groupKey,
      score_key: scoreKey,
      threshold: threshold
    });
  },

  generateVisualization: (jobId = null, groupKey = 'experience_tier', scoreKey = 'overall_score', threshold = 10.0) => {
    return client.post('/fairness/visualize', {
      job_id: jobId,
      group_key: groupKey,
      score_key: scoreKey,
      threshold: threshold
    });
  },

  getTrends: (jobId) => {
    return client.get(`/fairness/trends/${jobId}`);
  }
};

