import client from './client';

export const enhancementApi = {
  enhanceJobDescription: (description, title = '') => {
    return client.post('/enhancement/job-description', {
      description,
      title
    });
  },
  
  analyzeResume: (resumeText, jobDescription = null, jobRequirements = null) => {
    return client.post('/enhancement/resume-analysis', {
      resume_text: resumeText,
      job_description: jobDescription,
      job_requirements: jobRequirements
    });
  }
};

