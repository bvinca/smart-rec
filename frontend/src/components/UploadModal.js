import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { applicantsApi } from '../api/applicants';
import { X, Upload as UploadIcon } from 'lucide-react';
import toast from 'react-hot-toast';
import './Modal.css';

const UploadModal = ({ jobs, onClose }) => {
  const [selectedJob, setSelectedJob] = useState('');
  const [file, setFile] = useState(null);
  const [applicantData, setApplicantData] = useState({
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
  });
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => {
      if (!selectedJob || !file) {
        throw new Error('Please select a job and upload a file');
      }
      return applicantsApi.uploadCV(parseInt(selectedJob), file, applicantData);
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['applicants']);
      toast.success('CV uploaded and parsed successfully');
      onClose();
      setFile(null);
      setSelectedJob('');
      setApplicantData({ first_name: '', last_name: '', email: '', phone: '' });
    },
    onError: (error) => {
      toast.error(error.message || 'Failed to upload CV');
    },
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    mutation.mutate();
  };

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      const validTypes = ['application/pdf', 'application/msword', 
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain'];
      if (validTypes.includes(selectedFile.type)) {
        setFile(selectedFile);
      } else {
        toast.error('Please upload a PDF, DOC, DOCX, or TXT file');
      }
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Upload CV</h2>
          <button className="btn-icon" onClick={onClose}>
            <X size={24} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          <div className="form-group">
            <label>Select Job *</label>
            <select
              value={selectedJob}
              onChange={(e) => setSelectedJob(e.target.value)}
              className="input"
              required
            >
              <option value="">Choose a job...</option>
              {jobs.map((job) => (
                <option key={job.id} value={job.id}>
                  {job.title}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>CV File *</label>
            <div className="file-upload">
              <input
                type="file"
                id="file-upload"
                onChange={handleFileChange}
                accept=".pdf,.doc,.docx,.txt"
                style={{ display: 'none' }}
              />
              <label htmlFor="file-upload" className="file-upload-label">
                <UploadIcon size={20} />
                {file ? file.name : 'Choose file (PDF, DOC, DOCX, TXT)'}
              </label>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>First Name</label>
              <input
                type="text"
                value={applicantData.first_name}
                onChange={(e) => setApplicantData({ ...applicantData, first_name: e.target.value })}
                className="input"
                placeholder="Optional - will be extracted from CV"
              />
            </div>
            <div className="form-group">
              <label>Last Name</label>
              <input
                type="text"
                value={applicantData.last_name}
                onChange={(e) => setApplicantData({ ...applicantData, last_name: e.target.value })}
                className="input"
                placeholder="Optional - will be extracted from CV"
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Email</label>
              <input
                type="email"
                value={applicantData.email}
                onChange={(e) => setApplicantData({ ...applicantData, email: e.target.value })}
                className="input"
                placeholder="Optional - will be extracted from CV"
              />
            </div>
            <div className="form-group">
              <label>Phone</label>
              <input
                type="tel"
                value={applicantData.phone}
                onChange={(e) => setApplicantData({ ...applicantData, phone: e.target.value })}
                className="input"
                placeholder="Optional - will be extracted from CV"
              />
            </div>
          </div>

          <div className="modal-actions">
            <button type="button" className="btn btn-outline" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={mutation.isLoading || !file || !selectedJob}>
              {mutation.isLoading ? 'Uploading...' : 'Upload CV'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default UploadModal;

