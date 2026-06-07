import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Briefcase, FileText, CheckCircle, Clock, XCircle, Sparkles } from 'lucide-react';
import { applicationsApi } from '../api/applications';
import { jobsApi } from '../api/jobs';
import { useAuth } from '../context/AuthContext';
import './ApplicantDashboard.css';

const ApplicantDashboard = () => {
  const navigate = useNavigate();
  const { user } = useAuth();

  const { data: applications = [], isLoading: appsLoading } = useQuery({
    queryKey: ['applications'],
    queryFn: () => applicationsApi.getAll().then(res => res.data),
  });

  const { data: jobs = [], isLoading: jobsLoading } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => jobsApi.getAll().then(res => res.data),
  });

  const isLoading = appsLoading || jobsLoading;

  const statusCounts = {
    pending: applications.filter(app => app.status === 'pending').length,
    reviewing: applications.filter(app => app.status === 'reviewing').length,
    shortlisted: applications.filter(app => app.status === 'shortlisted').length,
    rejected: applications.filter(app => app.status === 'rejected').length,
    hired: applications.filter(app => app.status === 'hired').length,
  };

  if (isLoading) {
    return (
      <div className="loading-container">
        <div className="loading"></div>
        <p>Loading...</p>
      </div>
    );
  }

  return (
    <div className="applicant-dashboard">
      <div className="dashboard-header">
        <h1>Dashboard</h1>
        <p>Track your job applications and discover opportunities</p>
      </div>

      <div className="dashboard-stats">
        <div className="stat-card">
          <div className="stat-icon pending">
            <Clock size={24} />
          </div>
          <div className="stat-info">
            <h3>{statusCounts.pending + statusCounts.reviewing}</h3>
            <p>In Progress</p>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon shortlisted">
            <CheckCircle size={24} />
          </div>
          <div className="stat-info">
            <h3>{statusCounts.shortlisted}</h3>
            <p>Shortlisted</p>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon rejected">
            <XCircle size={24} />
          </div>
          <div className="stat-info">
            <h3>{statusCounts.rejected}</h3>
            <p>Rejected</p>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon total">
            <Briefcase size={24} />
          </div>
          <div className="stat-info">
            <h3>{applications.length}</h3>
            <p>Total Applications</p>
          </div>
        </div>
      </div>

      <div className="dashboard-sections">
        <div className="section">
          <div className="section-header">
            <h2>Recent Applications</h2>
            <button
              className="btn btn-link"
              onClick={() => navigate('/applicant/applications')}
            >
              View All
            </button>
          </div>
          <div className="applications-list">
            {applications.slice(0, 5).map((app) => (
              <div key={app.id} className="application-item">
                <div className="application-info">
                  <h3>{app.job?.title || 'Unknown Job'}</h3>
                  <p className="application-date">
                    Applied {new Date(app.created_at).toLocaleDateString()}
                  </p>
                </div>
                <span className={`status-badge status-${app.status}`}>
                  {app.status}
                </span>
              </div>
            ))}
            {applications.length === 0 && (
              <div className="empty-state">
                <FileText size={48} />
                <p>No applications yet</p>
                <button
                  className="btn btn-primary"
                  onClick={() => navigate('/applicant/jobs')}
                >
                  Browse Jobs
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="section">
          <div className="section-header">
            <h2>Available Jobs</h2>
            <button
              className="btn btn-link"
              onClick={() => navigate('/applicant/jobs')}
            >
              View All
            </button>
          </div>
          <div className="jobs-preview">
            {jobs.slice(0, 3).map((job) => (
              <div key={job.id} className="job-preview-card">
                <h3>{job.title}</h3>
                <p className="job-location">{job.location || 'Remote'}</p>
                <button
                  className="btn btn-sm btn-primary"
                  onClick={() => navigate(`/applicant/jobs/${job.id}`)}
                >
                  View Details
                </button>
              </div>
            ))}
            {jobs.length === 0 && (
              <div className="empty-state">
                <Briefcase size={48} />
                <p>No jobs available</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ApplicantDashboard;

