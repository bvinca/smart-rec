import client from './client';
import { jobsApi } from './jobs';

export const applicantsApi = {
  getAll: (jobId = null) => {
    const params = jobId ? { job_id: jobId } : {};
    return client.get('/applicants', { params });
  },
  getById: (id) => client.get(`/applicants/${id}`),
  uploadCV: (jobId, file, applicantData = {}) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('job_id', jobId);
    if (applicantData.first_name) formData.append('first_name', applicantData.first_name);
    if (applicantData.last_name) formData.append('last_name', applicantData.last_name);
    if (applicantData.email) formData.append('email', applicantData.email);
    if (applicantData.phone) formData.append('phone', applicantData.phone);
    
    return client.post('/applicants/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },
  score: (applicantId) => client.post(`/applicants/${applicantId}/score`),
  generateSummary: (applicantId) => client.post(`/applicants/${applicantId}/summary`),
  update: (id, data) => client.put(`/applicants/${id}`, data),
  downloadResume: (applicantId) => {
    return client.get(`/applicants/${applicantId}/download`, {
      responseType: 'blob',
    });
  },
  regenerateQuestions: (applicantId, feedback, numQuestions = 5) => {
    return client.post(`/applicants/${applicantId}/regenerate-questions`, {
      feedback,
      num_questions: numQuestions,
    });
  },
};

