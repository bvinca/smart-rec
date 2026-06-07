import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams, useParams } from 'react-router-dom';
import { applicantsApi } from '../api/applicants';
import { applicationsApi } from '../api/applications';
import { jobsApi } from '../api/jobs';
import { rankingApi } from '../api/ranking';
import { Upload, TrendingUp, FileText, Sparkles, Download, Award, MessageSquare, CheckCircle, XCircle, UserCheck, Shield } from 'lucide-react';
import { fairnessApi } from '../api/fairness';
import { useAuth } from '../context/AuthContext';
import { useBlindMode } from '../context/BlindModeContext';
import toast from 'react-hot-toast';
import UploadModal from '../components/UploadModal';
import ApplicantDetail from '../components/ApplicantDetail';
import FairnessDashboard from '../components/FairnessDashboard';
import './Applicants.css';

const Applicants = () => {
  const { id } = useParams(); // from /recruiter/jobs/:id/applicants
  const [searchParams] = useSearchParams();
  const jobIdFromQuery = searchParams.get('job_id'); // ?job_id= backup
  const jobId = id || jobIdFromQuery;
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [selectedApplicant, setSelectedApplicant] = useState(null);
  const [showRanking, setShowRanking] = useState(false);
  const [fairnessAudit, setFairnessAudit] = useState(null);
  const [showFairnessDashboard, setShowFairnessDashboard] = useState(false);
  const { blindMode, maskName, maskEmail } = useBlindMode();
  const queryClient = useQueryClient();
  const { user } = useAuth();

  // applications are the main list (nested applicant + job)
  const { data: applications = [], isLoading: appsLoading } = useQuery({
    queryKey: ['applications', jobId],
    queryFn: () => applicationsApi.getAll().then(res => res.data || res),
  });

  // /applicants keeps manual CV upload path alive
  const { data: directApplicants = [], isLoading: applicantsLoading } = useQuery({
    queryKey: ['applicants', jobId],
    queryFn: () => applicantsApi.getAll(jobId).then(res => res.data || res),
  });

  const filteredApplications = jobId
    ? applications.filter(app => app.job_id === parseInt(jobId))
    : applications;

  // parsed resume rows get AI extras
  const applicantsFromApplications = filteredApplications
    .filter(app => app.applicant) // CV was parsed
    .map(app => ({
      ...app.applicant,
      application_id: app.id,
      application_status: app.status,
      job: app.job,
      has_resume: true
    }));

  // no-CV apps become stub rows
  const applicationsWithoutResume = filteredApplications
    .filter(app => !app.applicant && app.user)
    .map(app => ({
      id: `user_${app.user_id}`, // string id avoids clashing with numeric ids
      first_name: app.user.first_name || 'Unknown',
      last_name: app.user.last_name || '',
      email: app.user.email,
      phone: app.user.phone || null,
      skills: [],
      experience_years: 0,
      education: [],
      work_experience: [],
      overall_score: 0,
      match_score: 0,
      skill_score: 0,
      experience_score: 0,
      education_score: 0,
      ai_summary: null,
      ai_feedback: null,
      interview_questions: [],
      application_id: app.id,
      application_status: app.status,
      job: app.job,
      has_resume: false,
      user_id: app.user_id
    }));

  // merge lists without duplicates
  const applicantIds = new Set(applicantsFromApplications.map(a => a.id));
  const uniqueDirectApplicants = directApplicants.filter(a => !applicantIds.has(a.id));
  const applicants = [...applicantsFromApplications, ...applicationsWithoutResume, ...uniqueDirectApplicants];

  const isLoading = appsLoading || applicantsLoading;

  const { data: jobs = [] } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => jobsApi.getAll().then(res => res.data),
  });

  const { data: rankedCandidates = [] } = useQuery({
    queryKey: ['rankedCandidates', jobId],
    queryFn: () => rankingApi.getRankedCandidates(jobId).then(res => res.data),
    enabled: showRanking && !!jobId,
  });

  const scoreMutation = useMutation({
    mutationFn: (id) => applicantsApi.score(id),
    onSuccess: () => {
      queryClient.invalidateQueries(['applicants']);
      toast.success('Applicant scored successfully');
    },
    onError: (error) => {
      toast.error(error.message || 'Failed to score applicant');
    },
  });

  const summaryMutation = useMutation({
    mutationFn: (id) => applicantsApi.generateSummary(id),
    onSuccess: () => {
      queryClient.invalidateQueries(['applicants']);
      queryClient.invalidateQueries(['applications']);
      toast.success('AI summary generated successfully');
    },
    onError: (error) => {
      toast.error(error.message || 'Failed to generate summary');
    },
  });

  const updateStatusMutation = useMutation({
    mutationFn: ({ applicationId, status, notes }) => applicationsApi.update(applicationId, { status, notes }),
    onSuccess: () => {
      queryClient.invalidateQueries(['applications']);
      queryClient.invalidateQueries(['applicants']);
      toast.success('Application status updated successfully');
    },
    onError: (error) => {
      toast.error(error.message || 'Failed to update application status');
    },
  });

  const auditFairnessMutation = useMutation({
    mutationFn: () => fairnessApi.auditFairness(jobId),
    onSuccess: (response) => {
      setFairnessAudit(response.data);
      toast.success('Fairness audit complete!');
    },
    onError: (error) => {
      const errorMsg = error.response?.data?.detail || error.message || 'Failed to audit fairness';
      toast.error(errorMsg);
    },
  });

  const handleStatusUpdate = (applicationId, status) => {
    if (!applicationId) {
      toast.error('Application ID not found');
      return;
    }
    updateStatusMutation.mutate({ applicationId, status });
  };

  const handleScore = (applicantId) => {
    // fake string ids: nothing to score
    if (typeof applicantId !== 'number') {
      toast.error('Cannot score applicant without resume data');
      return;
    }
    scoreMutation.mutate(applicantId);
  };

  const handleGenerateSummary = (applicantId) => {
    // same gate: need parsed resume for summary
    if (typeof applicantId !== 'number') {
      toast.error('Cannot generate summary for applicant without resume data');
      return;
    }
    summaryMutation.mutate(applicantId);
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      pending: { label: 'Pending', class: 'badge-info' },
      reviewing: { label: 'Reviewing', class: 'badge-warning' },
      shortlisted: { label: 'Shortlisted', class: 'badge-success' },
      rejected: { label: 'Rejected', class: 'badge-danger' },
      hired: { label: 'Hired', class: 'badge-success' },
    };
    const config = statusConfig[status] || statusConfig.pending;
    return <span className={`badge ${config.class}`}>{config.label}</span>;
  };

  if (isLoading) {
    return (
      <div className="loading-container">
        <div className="loading"></div>
        <p>Loading applicants...</p>
      </div>
    );
  }

  return (
    <div className="applicants-page">
      <div className="page-header">
        <div>
          <h1>Applicants</h1>
          <p>Review and manage candidate applications</p>
        </div>
        <button className="btn btn-primary" onClick={() => setIsUploadModalOpen(true)}>
          <Upload size={20} />
          Upload CV
        </button>
      </div>

      {jobId && (
        <div className="filter-info">
          <span>Filtered by job: {jobs.find(j => j.id === parseInt(jobId))?.title || 'Unknown'}</span>
          <div>
            {user?.role === 'recruiter' && (
              <>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => setShowFairnessDashboard(!showFairnessDashboard)}
                  style={{ marginRight: '0.5rem', display: 'flex', alignItems: 'center', gap: '6px' }}
                >
                  <Shield size={16} />
                  {showFairnessDashboard ? 'Hide' : 'Show'} Fairness Dashboard
                </button>
                <button
                  className="btn btn-outline btn-sm"
                  onClick={() => auditFairnessMutation.mutate()}
                  disabled={auditFairnessMutation.isLoading}
                  style={{ marginRight: '0.5rem', display: 'flex', alignItems: 'center', gap: '6px' }}
                >
                  <Shield size={16} />
                  {auditFairnessMutation.isLoading ? 'Auditing...' : 'Quick Audit'}
                </button>
              </>
            )}
            <button
              className="btn btn-outline btn-sm"
              onClick={() => setShowRanking(!showRanking)}
            >
              <Award size={16} />
              {showRanking ? 'Hide' : 'Show'} Ranking
            </button>
            <a href="/applicants" style={{ marginLeft: '1rem' }}>Clear filter</a>
          </div>
        </div>
      )}

      {showFairnessDashboard && jobId && user?.role === 'recruiter' && (
        <div style={{ margin: '20px 0' }}>
          <FairnessDashboard jobId={parseInt(jobId)} />
        </div>
      )}

      {fairnessAudit && (
        <div className="fairness-audit" style={{
          margin: '20px 0',
          padding: '20px',
          backgroundColor: fairnessAudit.bias_detected ? '#fef2f2' : '#f0fdf4',
          borderRadius: '8px',
          border: `1px solid ${fairnessAudit.bias_detected ? '#fecaca' : '#bbf7d0'}`
        }}>
          <h3 style={{ marginTop: 0, color: fairnessAudit.bias_detected ? '#dc2626' : '#16a34a' }}>
            <Shield size={20} style={{ verticalAlign: 'middle', marginRight: '8px' }} />
            Fairness Audit Results
          </h3>
          <div className={`audit-status ${fairnessAudit.bias_detected ? 'bias-detected' : 'no-bias'}`} style={{ marginBottom: '15px' }}>
            {fairnessAudit.bias_detected ? (
              <p style={{ color: '#dc2626', fontWeight: '600', fontSize: '16px' }}>
                ⚠️ Potential bias detected
              </p>
            ) : (
              <p style={{ color: '#16a34a', fontWeight: '600', fontSize: '16px' }}>
                ✅ No significant bias detected
              </p>
            )}
          </div>
          
          <div className="audit-details" style={{ marginBottom: '15px' }}>
            <p style={{ margin: '4px 0', fontSize: '14px' }}>
              <strong>Bias Magnitude:</strong> {fairnessAudit.bias_magnitude}%
            </p>
            <p style={{ margin: '4px 0', fontSize: '14px' }}>
              <strong>Statistical Significance:</strong> {(fairnessAudit.statistical_significance * 100).toFixed(1)}%
            </p>
            {fairnessAudit.threshold_used && (
              <p style={{ margin: '4px 0', fontSize: '14px' }}>
                <strong>Threshold Used:</strong> {fairnessAudit.threshold_used}%
              </p>
            )}
          </div>
          
          {fairnessAudit.group_analysis && Object.keys(fairnessAudit.group_analysis).length > 0 && (
            <div className="group-analysis" style={{ marginBottom: '15px' }}>
              <h4 style={{ fontSize: '14px', fontWeight: '600', marginBottom: '8px' }}>Group Analysis:</h4>
              {Object.entries(fairnessAudit.group_analysis).map(([group, data]) => (
                <div key={group} style={{ 
                  marginBottom: '8px', 
                  padding: '8px', 
                  backgroundColor: 'white', 
                  borderRadius: '4px',
                  fontSize: '14px'
                }}>
                  <strong>{group}:</strong> Mean Score: {data.mean_score?.toFixed(1)}% 
                  {data.std_dev !== undefined && ` (Std Dev: ${data.std_dev.toFixed(1)})`}
                  {data.count !== undefined && ` - Count: ${data.count}`}
                </div>
              ))}
            </div>
          )}
          
          {fairnessAudit.recommendations && fairnessAudit.recommendations.length > 0 && (
            <div className="recommendations">
              <h4 style={{ fontSize: '14px', fontWeight: '600', marginBottom: '8px' }}>Recommendations:</h4>
              <ul style={{ margin: '4px 0', paddingLeft: '20px', fontSize: '14px' }}>
                {fairnessAudit.recommendations.map((rec, idx) => (
                  <li key={idx} style={{ marginBottom: '4px' }}>{rec}</li>
                ))}
              </ul>
            </div>
          )}
          
          {fairnessAudit.message && (
            <p style={{ marginTop: '12px', fontSize: '14px', fontStyle: 'italic' }}>
              {fairnessAudit.message}
            </p>
          )}
          
          <button 
            className="btn btn-outline btn-sm" 
            onClick={() => setFairnessAudit(null)}
            style={{ marginTop: '12px' }}
          >
            Close
          </button>
        </div>
      )}

      {showRanking && jobId && rankedCandidates.length > 0 && (
        <div className="ranking-section">
          <h2>
            <Award size={24} />
            Ranked Candidates
          </h2>
          <div className="ranked-list">
            {rankedCandidates.map((candidate, idx) => (
              <div key={candidate.applicant_id} className="ranked-item">
                <div className="rank-number">#{candidate.rank}</div>
                <div className="rank-info">
                  <h4>{maskName(candidate.name)}</h4>
                  <p>{maskEmail(candidate.email)}</p>
                  <div className="rank-scores">
                    <span>Match: {candidate.match_score.toFixed(1)}%</span>
                    <span>Overall: {candidate.overall_score.toFixed(1)}%</span>
                  </div>
                </div>
                <div className="rank-actions">
                  <button
                    className="btn btn-outline btn-sm"
                    onClick={() => {
                      const applicant = applicants.find(a => a.id === candidate.applicant_id);
                      if (applicant) setSelectedApplicant(applicant);
                    }}
                  >
                    View Details
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="applicants-list">
        {applicants.map((applicant) => (
          <div key={applicant.id} className="applicant-card">
            <div className="applicant-header">
              <div>
                <h3>{blindMode ? 'Candidate' : `${applicant.first_name} ${applicant.last_name}`}</h3>
                <p className="applicant-email">{maskEmail(applicant.email)}</p>
                {applicant.job && (
                  <p className="applicant-job">Applied for: {applicant.job.title}</p>
                )}
              </div>
              {getStatusBadge(applicant.application_status || applicant.status)}
            </div>

            {applicant.overall_score > 0 && applicant.has_resume !== false && (
              <div className="score-section">
                <div className="score-display">
                  <TrendingUp size={20} />
                  <span className="score-value">{(applicant.overall_score || 0).toFixed(1)}%</span>
                  <span className="score-label">Match Score</span>
                </div>
                <div className="score-breakdown">
                  <div className="score-item">
                    <span>Skills</span>
                    <span>{(applicant.skill_score || 0).toFixed(1)}%</span>
                  </div>
                  <div className="score-item">
                    <span>Experience</span>
                    <span>{(applicant.experience_score || 0).toFixed(1)}%</span>
                  </div>
                  <div className="score-item">
                    <span>Match</span>
                    <span>{(applicant.match_score || 0).toFixed(1)}%</span>
                  </div>
                </div>
              </div>
            )}

            {applicant.skills && applicant.skills.length > 0 && (
              <div className="skills-section">
                {applicant.skills.slice(0, 5).map((skill, idx) => (
                  <span key={idx} className="skill-tag">{skill}</span>
                ))}
                {applicant.skills.length > 5 && (
                  <span className="skill-tag">+{applicant.skills.length - 5} more</span>
                )}
              </div>
            )}

                {/* AI summary snippet */}
                {applicant.ai_summary && applicant.ai_summary !== "Unable to generate AI summary at this time." && (
                  <div className="ai-summary-preview">
                    <div className="ai-badge">
                      <Sparkles size={14} />
                      <span>AI Summary</span>
                    </div>
                    <p className="summary-text">{applicant.ai_summary.substring(0, 150)}...</p>
                  </div>
                )}

            {/* question count badge */}
            {applicant.interview_questions && applicant.interview_questions.length > 0 && (
              <div className="interview-questions-badge">
                <MessageSquare size={14} />
                <span>{applicant.interview_questions.length} Interview Questions Generated</span>
              </div>
            )}

            {/* no-resume warning */}
            {applicant.has_resume === false && (
              <div className="no-resume-notice">
                <FileText size={14} />
                <span>No resume uploaded - Basic application only</span>
              </div>
            )}

            <div className="applicant-actions">
              {/* shortlist / reject / hire */}
              {applicant.application_id && (
                <div className="status-actions">
                  {applicant.application_status !== 'shortlisted' && applicant.application_status !== 'hired' && (
                    <button
                      className="btn btn-success btn-sm"
                      onClick={() => handleStatusUpdate(applicant.application_id, 'shortlisted')}
                      disabled={updateStatusMutation.isLoading}
                      title="Shortlist this candidate"
                    >
                      <UserCheck size={16} />
                      Shortlist
                    </button>
                  )}
                  {applicant.application_status !== 'rejected' && (
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={() => {
                        if (window.confirm('Are you sure you want to reject this application?')) {
                          handleStatusUpdate(applicant.application_id, 'rejected');
                        }
                      }}
                      disabled={updateStatusMutation.isLoading}
                      title="Reject this application"
                    >
                      <XCircle size={16} />
                      Reject
                    </button>
                  )}
                  {applicant.application_status === 'shortlisted' && (
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={() => handleStatusUpdate(applicant.application_id, 'hired')}
                      disabled={updateStatusMutation.isLoading}
                      title="Mark as hired"
                    >
                      <CheckCircle size={16} />
                      Mark Hired
                    </button>
                  )}
                </div>
              )}
              
              {/* score/summary only with a real applicant row */}
              {applicant.has_resume !== false && typeof applicant.id === 'number' && (
                <>
                  {applicant.overall_score === 0 && (
                    <button
                      className="btn btn-secondary"
                      onClick={() => handleScore(applicant.id)}
                      disabled={scoreMutation.isLoading}
                    >
                      <TrendingUp size={16} />
                      Calculate Score
                    </button>
                  )}
                  {!applicant.ai_summary && (
                    <button
                      className="btn btn-outline"
                      onClick={() => handleGenerateSummary(applicant.id)}
                      disabled={summaryMutation.isLoading}
                    >
                      <Sparkles size={16} />
                      Generate AI Summary
                    </button>
                  )}
                </>
              )}
              <button
                className="btn btn-outline"
                onClick={() => setSelectedApplicant(applicant)}
              >
                <FileText size={16} />
                View Details
              </button>
              {applicant.resume_file_path && typeof applicant.id === 'number' && (
                <button
                  className="btn btn-outline"
                  onClick={() => {
                    applicantsApi.downloadResume(applicant.id)
                      .then(res => {
                        const url = window.URL.createObjectURL(new Blob([res.data]));
                        const link = document.createElement('a');
                        link.href = url;
                        link.setAttribute('download', `${applicant.first_name}_${applicant.last_name}_resume.${applicant.resume_file_type || 'pdf'}`);
                        document.body.appendChild(link);
                        link.click();
                        link.remove();
                      })
                      .catch(() => toast.error('Failed to download resume'));
                  }}
                >
                  <Download size={16} />
                  Download Resume
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {applicants.length === 0 && (
        <div className="empty-state">
          <FileText size={64} />
          <h3>No applicants yet</h3>
          <p>Upload a CV to get started</p>
          <button className="btn btn-primary" onClick={() => setIsUploadModalOpen(true)}>
            Upload CV
          </button>
        </div>
      )}

      {isUploadModalOpen && (
        <UploadModal
          jobs={jobs}
          onClose={() => setIsUploadModalOpen(false)}
        />
      )}

      {selectedApplicant && (
        <ApplicantDetail
          applicant={selectedApplicant}
          onClose={() => setSelectedApplicant(null)}
        />
      )}
    </div>
  );
};

export default Applicants;

