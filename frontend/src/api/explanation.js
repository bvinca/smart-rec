import client from './client';

export const explanationApi = {
  explainScoring: (applicantId, jobId = null) => {
    return client.post('/explanation/scoring', {
      applicant_id: applicantId,
      job_id: jobId
    });
  }
};

