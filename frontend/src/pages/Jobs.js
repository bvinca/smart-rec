import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { jobsApi } from '../api/jobs';
import { Plus, Edit, Trash2, Users, MapPin, DollarSign, Briefcase } from 'lucide-react';
import toast from 'react-hot-toast';
import JobModal from '../components/JobModal';
import './Jobs.css';

const Jobs = () => {
  const navigate = useNavigate();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingJob, setEditingJob] = useState(null);
  const queryClient = useQueryClient();

  const { data: jobs = [], isLoading } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => jobsApi.getAll().then(res => res.data || res),
    onError: (error) => {
      console.error('Error fetching jobs:', error);
      toast.error(error?.message || 'Failed to load jobs');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id) => jobsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries(['jobs']);
      toast.success('Job deleted successfully');
    },
    onError: (error) => {
      toast.error(error.message || 'Failed to delete job');
    },
  });

  const handleCreate = () => {
    setEditingJob(null);
    setIsModalOpen(true);
  };

  const handleEdit = (job) => {
    setEditingJob(job);
    setIsModalOpen(true);
  };

  const handleDelete = (id) => {
    if (window.confirm('Are you sure you want to delete this job?')) {
      deleteMutation.mutate(id);
    }
  };

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
          <h1>Job Postings</h1>
          <p>Manage and track your job openings</p>
        </div>
        <button className="btn btn-primary" onClick={handleCreate}>
          <Plus size={20} />
          Create Job
        </button>
      </div>

      <div className="jobs-grid">
        {jobs.map((job) => (
          <div key={job.id} className="job-card">
            <div className="job-header">
              <h2>{job.title}</h2>
              <div className="job-actions">
                <button
                  className="btn-icon"
                  onClick={() => handleEdit(job)}
                  title="Edit"
                >
                  <Edit size={18} />
                </button>
                <button
                  className="btn-icon"
                  onClick={() => handleDelete(job.id)}
                  title="Delete"
                >
                  <Trash2 size={18} />
                </button>
              </div>
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
              <button
                className="btn btn-link view-applicants"
                onClick={() => navigate(`/recruiter/jobs/${job.id}/applicants`)}
              >
                <Users size={16} />
                View Applicants
              </button>
            </div>
          </div>
        ))}
      </div>

      {jobs.length === 0 && (
        <div className="empty-state">
          <Briefcase size={64} />
          <h3>No jobs yet</h3>
          <p>Create your first job posting to get started</p>
          <button className="btn btn-primary" onClick={handleCreate}>
            Create Job
          </button>
        </div>
      )}

      {isModalOpen && (
        <JobModal
          job={editingJob}
          onClose={() => {
            setIsModalOpen(false);
            setEditingJob(null);
          }}
        />
      )}
    </div>
  );
};

export default Jobs;

