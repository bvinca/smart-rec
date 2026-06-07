import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useNavigate } from 'react-router-dom';
import { MapPin, DollarSign, Briefcase, Upload, ArrowLeft, CheckCircle, Sparkles } from 'lucide-react';
import { jobsApi } from '../api/jobs';
import { applicationsApi } from '../api/applications';
import { enhancementApi } from '../api/enhancement';
import { useAuth } from '../context/AuthContext';
import ApplicationSuccess from '../components/ApplicationSuccess';
import toast from 'react-hot-toast';
import './JobDetail.css';

const JobDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [selectedFile, setSelectedFile] = useState(null);
  const [enhancedDescription, setEnhancedDescription] = useState(null);

  const { data: job, isLoading, error: jobError } = useQuery({
    queryKey: ['job', id],
    queryFn: () => jobsApi.getById(id).then(res => res.data || res),
    retry: 1,
  });

  const { data: applications = [] } = useQuery({
    queryKey: ['applications'],
    queryFn: () => applicationsApi.getAll().then(res => res.data || res),
    enabled: user?.role === 'applicant',
  });

  const [applicationResult, setApplicationResult] = useState(null);

  const applyMutation = useMutation({
    mutationFn: (file) => applicationsApi.apply(id, file),
    onSuccess: (response) => {
      queryClient.invalidateQueries(['applications']);
      queryClient.invalidateQueries(['resume']); // profile should show new parse
      setApplicationResult(response.data);
      toast.success('Application submitted successfully!');
      setSelectedFile(null);
    },
    onError: (error) => {
      console.error('Application error:', error);
      console.error('Error response:', error.response);
      const errorMessage = error.response?.data?.detail || error.message || 'Failed to submit application';
      toast.error(errorMessage);
    },
  });

  const enhanceMutation = useMutation({
    mutationFn: () => enhancementApi.enhanceJobDescription(job.description, job.title),
    onSuccess: (response) => {
      setEnhancedDescription(response.data);
      toast.success('Job description enhanced successfully!');
    },
    onError: (error) => {
      const errorMsg = error.response?.data?.detail || error.message || 'Failed to enhance job description';
      toast.error(errorMsg);
    },
  });

  const hasApplied = applications.some(app => app.job_id === parseInt(id));

  const handleFileChange = (e) => {
    setSelectedFile(e.target.files[0]);
  };

  const handleApply = () => {
    if (user?.role !== 'applicant') {
      toast.error('Please log in as an applicant to apply');
      navigate('/login');
      return;
    }

    if (hasApplied) {
      toast.error('You have already applied to this job');
      return;
    }

    applyMutation.mutate(selectedFile);
  };

  if (isLoading) {
    return (
      <div className="loading-container">
        <div className="loading"></div>
        <p>Loading job details...</p>
      </div>
    );
  }

  if (jobError || (!job && !isLoading)) {
    return (
      <div className="error-state">
        <h2>Job not found</h2>
        <p>{jobError?.message || 'The job you are looking for does not exist or has been removed.'}</p>
        <button className="btn btn-primary" onClick={() => navigate('/applicant/jobs')}>
          Back to Jobs
        </button>
      </div>
    );
  }

  return (
    <div className="job-detail">
      <button className="back-button" onClick={() => navigate(-1)}>
        <ArrowLeft size={20} />
        Back
      </button>

      <div className="job-header">
        <h1>{job.title}</h1>
        <div className="job-meta">
          {job.location && (
            <div className="meta-item">
              <MapPin size={18} />
              <span>{job.location}</span>
            </div>
          )}
          {job.salary_range && (
            <div className="meta-item">
              <DollarSign size={18} />
              <span>{job.salary_range}</span>
            </div>
          )}
          <div className="meta-item">
            <Briefcase size={18} />
            <span className={`status-badge status-${job.status}`}>{job.status}</span>
          </div>
        </div>
      </div>

      <div className="job-content">
        <div className="job-description">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <h2>Job Description</h2>
            {user?.role === 'recruiter' && (
              <button 
                className="btn btn-secondary btn-sm" 
                onClick={() => enhanceMutation.mutate()}
                disabled={enhanceMutation.isLoading}
                style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
              >
                <Sparkles size={16} />
                {enhanceMutation.isLoading ? 'Enhancing...' : 'Enhance with AI'}
              </button>
            )}
          </div>
          {enhancedDescription ? (
            <div>
              <div className="enhanced-description" style={{ 
                padding: '15px', 
                backgroundColor: '#f0f9ff', 
                borderRadius: '8px',
                marginBottom: '15px',
                border: '1px solid #bae6fd'
              }}>
                <h3 style={{ marginTop: 0, color: '#0369a1' }}>✨ AI-Enhanced Description</h3>
                <p style={{ whiteSpace: 'pre-wrap' }}>{enhancedDescription.improved_description}</p>
                {enhancedDescription.identified_issues && enhancedDescription.identified_issues.length > 0 && (
                  <div className="issues" style={{ marginTop: '15px' }}>
                    <h4 style={{ fontSize: '14px', fontWeight: '600' }}>Issues Identified:</h4>
                    <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
                      {enhancedDescription.identified_issues.map((issue, idx) => (
                        <li key={idx} style={{ marginBottom: '4px' }}>{issue}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {enhancedDescription.improvements && enhancedDescription.improvements.length > 0 && (
                  <div className="improvements" style={{ marginTop: '15px' }}>
                    <h4 style={{ fontSize: '14px', fontWeight: '600' }}>Improvements Made:</h4>
                    <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
                      {enhancedDescription.improvements.map((improvement, idx) => (
                        <li key={idx} style={{ marginBottom: '4px' }}>{improvement}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <button 
                  className="btn btn-outline btn-sm" 
                  onClick={() => setEnhancedDescription(null)}
                  style={{ marginTop: '10px' }}
                >
                  Show Original
                </button>
              </div>
            </div>
          ) : (
            <p>{job.description}</p>
          )}
        </div>

        {job.requirements && (
          <div className="job-requirements">
            <h2>Requirements</h2>
            <p>{job.requirements}</p>
          </div>
        )}
      </div>

      {applicationResult ? (
        <ApplicationSuccess
          applicationData={applicationResult}
          onClose={() => {
            setApplicationResult(null);
            navigate('/applicant/applications');
          }}
        />
      ) : (
        user?.role === 'applicant' && job.status === 'active' && (
          <div className="apply-section">
            {hasApplied ? (
              <div className="already-applied">
                <CheckCircle size={24} />
                <p>You have already applied to this job</p>
                <button
                  className="btn btn-secondary"
                  onClick={() => navigate('/applicant/applications')}
                >
                  View Application
                </button>
              </div>
            ) : (
              <div className="apply-form">
                <h2>Apply for this Position</h2>
                <div className="file-upload">
                  <label htmlFor="resume-upload" className="upload-label">
                    <Upload size={20} />
                    {selectedFile ? selectedFile.name : 'Upload Resume (Optional)'}
                  </label>
                  <input
                    type="file"
                    id="resume-upload"
                    accept=".pdf,.doc,.docx"
                    onChange={handleFileChange}
                    style={{ display: 'none' }}
                  />
                </div>
                <button
                  className="btn btn-primary btn-large"
                  onClick={handleApply}
                  disabled={applyMutation.isLoading}
                >
                  {applyMutation.isLoading ? 'Submitting...' : 'Submit Application'}
                </button>
              </div>
            )}
          </div>
        )
      )}
    </div>
  );
};

export default JobDetail;

