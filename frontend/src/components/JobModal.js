import React, { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { jobsApi } from '../api/jobs';
import { enhancementApi } from '../api/enhancement';
import { useAuth } from '../context/AuthContext';
import { X, Sparkles } from 'lucide-react';
import toast from 'react-hot-toast';
import './Modal.css';

const JobModal = ({ job, onClose }) => {
  const { user, isRecruiter } = useAuth();
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    requirements: '',
    location: '',
    salary_range: '',
    status: 'active',
    required_education_level: '',
    required_skills: '', // comma-separated; backend splits into a list
  });

  const queryClient = useQueryClient();
  const [enhancedDescription, setEnhancedDescription] = useState(null);

  useEffect(() => {
    if (job) {
      setFormData({
        title: job.title || '',
        description: job.description || '',
        requirements: job.requirements || '',
        location: job.location || '',
        salary_range: job.salary_range || '',
        status: job.status || 'active',
        required_education_level: job.required_education_level || '',
        required_skills: Array.isArray(job.required_skills)
          ? job.required_skills.join(', ')
          : (job.required_skills || ''),
      });
    }
  }, [job]);

  const mutation = useMutation({
    mutationFn: (data) => {
      if (job) {
        return jobsApi.update(job.id, data);
      }
      return jobsApi.create(data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['jobs']);
      queryClient.invalidateQueries(['analytics']); // dashboard counts depend on jobs
      toast.success(job ? 'Job updated successfully' : 'Job created successfully');
      onClose();
    },
    onError: (error) => {
      console.error('Job creation error:', error);
      console.error('Error response:', error?.response);
      console.error('Error status:', error?.response?.status);
      console.error('Error data:', error?.response?.data);
      
      let errorMessage = 'Failed to save job';
      
      if (error?.response?.status === 403) {
        errorMessage = 'Access denied. You must be logged in as a recruiter to create jobs.';
      } else if (error?.response?.status === 401) {
        errorMessage = 'Authentication failed. Please log in again.';
      } else if (error?.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      } else if (error?.message) {
        errorMessage = error.message;
      }
      
      toast.error(errorMessage);
    },
  });

  const enhanceMutation = useMutation({
    mutationFn: () => enhancementApi.enhanceJobDescription(formData.description, formData.title),
    onSuccess: (response) => {
      setEnhancedDescription(response.data);
      toast.success('Job description enhanced successfully!');
    },
    onError: (error) => {
      const errorMsg = error.response?.data?.detail || error.message || 'Failed to enhance job description';
      toast.error(errorMsg);
    },
  });

  const handleSubmit = (e) => {
    e.preventDefault();

    // temp debug while role bugs linger
    console.log('Submitting job:', formData);
    console.log('Current user:', user);
    console.log('Is recruiter:', isRecruiter);
    console.log('Token:', localStorage.getItem('token') ? 'Present' : 'Missing');

    // client-side guard; backend checks too
    if (!isRecruiter) {
      toast.error('Only recruiters can create jobs. Please log in as a recruiter.');
      return;
    }
    
    mutation.mutate(formData);
  };

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{job ? 'Edit Job' : 'Create New Job'}</h2>
          <button className="btn-icon" onClick={onClose}>
            <X size={24} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          <div className="form-group">
            <label>Job Title *</label>
            <input
              type="text"
              name="title"
              value={formData.title}
              onChange={handleChange}
              className="input"
              required
            />
          </div>

          <div className="form-group">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <label>Description *</label>
              {isRecruiter && formData.description && (
                <button 
                  type="button"
                  className="btn btn-sm btn-secondary" 
                  onClick={() => enhanceMutation.mutate()}
                  disabled={enhanceMutation.isLoading}
                  style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', padding: '6px 12px' }}
                >
                  <Sparkles size={14} />
                  {enhanceMutation.isLoading ? 'Enhancing...' : 'Enhance with AI'}
                </button>
              )}
            </div>
            {enhancedDescription ? (
              <div>
                <div className="enhanced-description" style={{ 
                  padding: '12px', 
                  backgroundColor: '#f0f9ff', 
                  borderRadius: '6px',
                  marginBottom: '10px',
                  border: '1px solid #bae6fd',
                  fontSize: '13px'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <h4 style={{ margin: 0, color: '#0369a1', fontSize: '14px' }}>✨ AI-Enhanced Description</h4>
                    <button 
                      type="button"
                      className="btn btn-sm btn-primary" 
                      onClick={() => {
                        setFormData({ ...formData, description: enhancedDescription.improved_description });
                        setEnhancedDescription(null);
                        toast.success('Enhanced description applied to form!');
                      }}
                      style={{ fontSize: '11px', padding: '4px 8px' }}
                    >
                      Apply
                    </button>
                  </div>
                  <p style={{ whiteSpace: 'pre-wrap', marginBottom: '10px', fontSize: '13px' }}>
                    {enhancedDescription.improved_description}
                  </p>
                  {enhancedDescription.identified_issues && enhancedDescription.identified_issues.length > 0 && (
                    <div className="issues" style={{ marginTop: '10px', paddingTop: '10px', borderTop: '1px solid #bae6fd' }}>
                      <h5 style={{ fontSize: '12px', fontWeight: '600', marginBottom: '6px' }}>Issues Identified:</h5>
                      <ul style={{ margin: '4px 0', paddingLeft: '18px', fontSize: '12px' }}>
                        {enhancedDescription.identified_issues.map((issue, idx) => (
                          <li key={idx} style={{ marginBottom: '3px' }}>{issue}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {enhancedDescription.improvements && enhancedDescription.improvements.length > 0 && (
                    <div className="improvements" style={{ marginTop: '10px', paddingTop: '10px', borderTop: '1px solid #bae6fd' }}>
                      <h5 style={{ fontSize: '12px', fontWeight: '600', marginBottom: '6px' }}>Improvements Made:</h5>
                      <ul style={{ margin: '4px 0', paddingLeft: '18px', fontSize: '12px' }}>
                        {enhancedDescription.improvements.map((improvement, idx) => (
                          <li key={idx} style={{ marginBottom: '3px' }}>{improvement}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  <button 
                    type="button"
                    className="btn btn-outline btn-sm" 
                    onClick={() => setEnhancedDescription(null)}
                    style={{ marginTop: '8px', fontSize: '11px', padding: '4px 8px' }}
                  >
                    Show Original
                  </button>
                </div>
              </div>
            ) : null}
            <textarea
              name="description"
              value={formData.description}
              onChange={handleChange}
              className="textarea"
              required
              rows="5"
            />
          </div>

          <div className="form-group">
            <label>Requirements</label>
            <textarea
              name="requirements"
              value={formData.requirements}
              onChange={handleChange}
              className="textarea"
              rows="4"
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Location</label>
              <input
                type="text"
                name="location"
                value={formData.location}
                onChange={handleChange}
                className="input"
                placeholder="e.g., Remote, New York, NY"
              />
            </div>

            <div className="form-group">
              <label>Salary Range</label>
              <input
                type="text"
                name="salary_range"
                value={formData.salary_range}
                onChange={handleChange}
                className="input"
                placeholder="e.g., $80k - $120k"
              />
            </div>
          </div>

          <div className="form-group">
            <label>Required Skills (optional)</label>
            <input
              type="text"
              name="required_skills"
              value={formData.required_skills}
              onChange={handleChange}
              className="input"
              placeholder="e.g. Python, FastAPI, PostgreSQL, Kubernetes"
            />
            <p style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>
              Comma-separated. When set, the scorer uses this list directly instead of text-mining the description. Skills only declared in a candidate's "Skills" section (not in work history) are weighted lower.
            </p>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Status</label>
              <select
                name="status"
                value={formData.status}
                onChange={handleChange}
                className="input"
              >
                <option value="active">Active</option>
                <option value="draft">Draft</option>
                <option value="closed">Closed</option>
              </select>
            </div>

            <div className="form-group">
              <label>Required Education Level</label>
              <select
                name="required_education_level"
                value={formData.required_education_level || ''}
                onChange={handleChange}
                className="input"
              >
                <option value="">No preference</option>
                <option value="associate">Associate / Diploma</option>
                <option value="bachelor">Bachelor's degree</option>
                <option value="master">Master's degree</option>
                <option value="phd">PhD / Doctorate</option>
              </select>
              <p style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>
                If set, applicants are scored against this minimum; lower levels lose points.
              </p>
            </div>
          </div>

          <div className="modal-actions">
            <button type="button" className="btn btn-outline" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={mutation.isLoading}>
              {mutation.isLoading ? 'Saving...' : job ? 'Update' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default JobModal;

