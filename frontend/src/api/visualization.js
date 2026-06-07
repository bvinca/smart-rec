import client from './client';

export const visualizationApi = {
  analyzeSkillGap: (jobId, applicantId) => {
    return client.post('/visualization/skill-gap', {
      job_id: jobId,
      applicant_id: applicantId
    });
  }
};

