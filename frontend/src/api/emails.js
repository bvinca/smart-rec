import client from './client';

export const emailsApi = {
  // LLM draft for applicant (ack, feedback, reject, invite, hired)
  generateForApplicant: async (applicantId, messageType, tone = null, additionalContext = null) => {
    const response = await client.post(`/emails/applicants/${applicantId}/generate`, {
      message_type: messageType,
      tone: tone,
      additional_context: additionalContext
    });
    return response.data;
  },

  // same draft flow, scoped to one application
  generateForApplication: async (applicationId, messageType, tone = null, additionalContext = null) => {
    const response = await client.post(`/emails/applications/${applicationId}/generate`, {
      message_type: messageType,
      tone: tone,
      additional_context: additionalContext
    });
    return response.data;
  },

  getApplicantHistory: async (applicantId) => {
    const response = await client.get(`/emails/applicants/${applicantId}/history`);
    return response.data;
  },

  getJobHistory: async (jobId) => {
    const response = await client.get(`/emails/jobs/${jobId}/history`);
    return response.data;
  },

  // send draft via SMTP; emailId is the log row
  sendEmail: async (emailId, subject = null) => {
    const response = await client.post(`/emails/${emailId}/send`, {
      subject: subject
    });
    return response.data;
  }
};

