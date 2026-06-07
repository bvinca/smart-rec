import client from './client';

// recruiter notes on an application; JWT handles scope
export const notesApi = {
  list: (applicationId) =>
    client.get(`/applications/${applicationId}/notes`),

  create: (applicationId, body) =>
    client.post(`/applications/${applicationId}/notes`, { body }),

  remove: (applicationId, noteId) =>
    client.delete(`/applications/${applicationId}/notes/${noteId}`),
};
