import client from './client';

export const feedbackApi = {
  submitFeedback: (feedbackData, learningRate = 0.1, recruiterId = null, jobId = null) => {
    return client.post('/feedback/submit', {
      feedback_data: feedbackData,
      learning_rate: learningRate,
      recruiter_id: recruiterId,
      job_id: jobId
    });
  },

  recordDecision: (applicationId, hired, notes = null) => {
    return client.post('/feedback/decision', {
      application_id: applicationId,
      hired: hired,
      notes: notes
    });
  },

  getWeights: (recruiterId = null, jobId = null) => {
    const params = new URLSearchParams();
    if (recruiterId) params.append('recruiter_id', recruiterId);
    if (jobId) params.append('job_id', jobId);
    return client.get(`/feedback/weights?${params.toString()}`);
  }
};

