import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Briefcase, Users, TrendingUp, FileText, Shield } from 'lucide-react';
import { jobsApi } from '../api/jobs';
import { analyticsApi } from '../api/analytics';
import { fairnessApi } from '../api/fairness';
import JobModal from '../components/JobModal';
import FairnessChart from '../components/FairnessChart';
import FairnessTrendsWidget from '../components/FairnessTrendsWidget';
import './RecruiterDashboard.css';

const RecruiterDashboard = () => {
  const navigate = useNavigate();
  const [isJobModalOpen, setIsJobModalOpen] = useState(false);

  const { data: analytics, isLoading: analyticsLoading } = useQuery({
    queryKey: ['analytics'],
    queryFn: () => analyticsApi.get().then(res => res.data),
  });

  const { data: jobs = [], isLoading: jobsLoading } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => jobsApi.getAll().then(res => res.data),
  });

  const isLoading = analyticsLoading || jobsLoading;

  if (isLoading) {
    return (
      <div className="loading-container">
        <div className="loading"></div>
        <p>Loading dashboard...</p>
      </div>
    );
  }

  return (
    <div className="recruiter-dashboard">
      <div className="dashboard-header">
        <h1>Recruiter Dashboard</h1>
        <p>Overview of your hiring activities</p>
      </div>

      <div className="dashboard-stats">
        <div className="stat-card">
          <div className="stat-icon jobs">
            <Briefcase size={24} />
          </div>
          <div className="stat-info">
            <h3>{analytics?.total_jobs || 0}</h3>
            <p>Total Jobs</p>
            <span className="stat-sub">{analytics?.active_jobs || 0} active</span>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon applicants">
            <Users size={24} />
          </div>
          <div className="stat-info">
            <h3>{analytics?.total_applications || 0}</h3>
            <p>Total Applications</p>
            <span className="stat-sub">{analytics?.pending_applications || 0} pending</span>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon score">
            <TrendingUp size={24} />
          </div>
          <div className="stat-info">
            <h3>{analytics?.average_score?.toFixed(1) || '0.0'}</h3>
            <p>Average Score</p>
            <span className="stat-sub">Candidate quality</span>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon shortlisted">
            <FileText size={24} />
          </div>
          <div className="stat-info">
            <h3>{analytics?.shortlisted_applications || 0}</h3>
            <p>Shortlisted</p>
            <span className="stat-sub">Ready for interview</span>
          </div>
        </div>
      </div>

      <div className="dashboard-sections">
        <div className="section">
          <div className="section-header">
            <h2>Recent Job Postings</h2>
            <button
              className="btn btn-link"
              onClick={() => navigate('/recruiter/jobs')}
            >
              View All
            </button>
          </div>
          <div className="jobs-list">
            {jobs.slice(0, 5).map((job) => (
              <div key={job.id} className="job-item">
                <div className="job-info">
                  <h3>{job.title}</h3>
                  <p className="job-meta">{job.location || 'Remote'}</p>
                </div>
                <button
                  className="btn btn-sm btn-secondary"
                  onClick={() => navigate(`/recruiter/jobs/${job.id}/applicants`)}
                >
                  View Applicants
                </button>
              </div>
            ))}
            {jobs.length === 0 && (
              <div className="empty-state">
                <Briefcase size={48} />
                <p>No jobs yet</p>
                <button
                  className="btn btn-primary"
                  onClick={() => setIsJobModalOpen(true)}
                >
                  Create Job
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="section">
          <div className="section-header">
            <h2>Quick Actions</h2>
          </div>
          <div className="quick-actions">
            <button
              className="action-card"
              onClick={() => setIsJobModalOpen(true)}
            >
              <Briefcase size={24} />
              <span>Create New Job</span>
            </button>
            <button
              className="action-card"
              onClick={() => navigate('/recruiter/applicants')}
            >
              <Users size={24} />
              <span>View All Applicants</span>
            </button>
            <button
              className="action-card"
              onClick={() => navigate('/recruiter/analytics')}
            >
              <TrendingUp size={24} />
              <span>View Analytics</span>
            </button>
          </div>
        </div>
      </div>

      {isJobModalOpen && (
        <JobModal
          job={null}
          onClose={() => setIsJobModalOpen(false)}
        />
      )}
    </div>
  );
};

export default RecruiterDashboard;

