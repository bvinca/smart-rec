import client from './client';

export const applicationsApi = {
  apply: async (jobId, file) => {
    const formData = new FormData();
    if (file) {
      formData.append('file', file);
    }
    // send FormData even when empty; FastAPI Optional[UploadFile] expects it
    return client.post(`/applications/apply/${jobId}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },

  getAll: () => client.get('/applications'),

  getOne: (id) => client.get(`/applications/${id}`),

  update: (id, data) => client.put(`/applications/${id}`, data),

  // interview prep from LLM; cached on server
  getInterviewPrep: (applicationId) =>
    client.post(`/applications/${applicationId}/interview-prep`),
};

