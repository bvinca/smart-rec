import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { MapPin, DollarSign, Briefcase } from 'lucide-react';
import { jobsApi } from '../api/jobs';
import './Jobs.css';

const ApplicantJobs = () => {
  const navigate = useNavigate();

  const { data: jobs = [], isLoading, error } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => jobsApi.getAll().then(res => res.data || res),
    onError: (error) => {
      console.error('Error fetching jobs:', error);
    },
  });

  if (isLoading) {
    return (
      <div className="loading-container">
        <div className="loading"></div>
        <p>Loading jobs...</p>
      </div>
    );
  }

  return (
    <div className="jobs-page">
      <div className="page-header">
        <div>
          <h1>Available Jobs</h1>
          <p>Browse and apply to job opportunities</p>
        </div>
      </div>

      <div className="jobs-grid">
        {jobs.map((job) => (
          <div key={job.id} className="job-card" onClick={() => navigate(`/applicant/jobs/${job.id}`)}>
            <div className="job-header">
              <h2>{job.title}</h2>
            </div>

            <div className="job-meta">
              {job.location && (
                <div className="meta-item">
                  <MapPin size={16} />
                  <span>{job.location}</span>
                </div>
              )}
              {job.salary_range && (
                <div className="meta-item">
                  <DollarSign size={16} />
                  <span>{job.salary_range}</span>
                </div>
              )}
            </div>

            <p className="job-description">
              {job.description.substring(0, 150)}...
            </p>

            <div className="job-footer">
              <span className={`status-badge status-${job.status}`}>
                {job.status}
              </span>
              <button className="btn btn-primary btn-sm">
                View Details
              </button>
            </div>
          </div>
        ))}
      </div>

      {jobs.length === 0 && (
        <div className="empty-state">
          <Briefcase size={64} />
          <h3>No jobs available</h3>
          <p>Check back later for new opportunities</p>
        </div>
      )}
    </div>
  );
};

export default ApplicantJobs;

