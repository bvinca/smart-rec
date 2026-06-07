import React from 'react';
import { CheckCircle, FileText, Sparkles, TrendingUp } from 'lucide-react';
import './ApplicationSuccess.css';

const ApplicationSuccess = ({ applicationData, onClose }) => {
  if (!applicationData) return null;

  const parsedResume = applicationData.parsed_resume;
  const aiSummary = applicationData.ai_summary;
  const interviewQuestions = applicationData.interview_questions;
  const matchScore = applicationData.match_score;

  return (
    <div className="application-success">
      <div className="success-header">
        <CheckCircle size={48} className="success-icon" />
        <h2>Application Submitted Successfully!</h2>
        <p>Your resume has been parsed and analyzed</p>
      </div>

      {parsedResume && (
        <div className="parsed-data-section">
          <h3>
            <FileText size={20} />
            Parsed Resume Information
          </h3>
          <div className="parsed-info">
            <div className="info-item">
              <strong>Name:</strong> {parsedResume.name}
            </div>
            {parsedResume.email && (
              <div className="info-item">
                <strong>Email:</strong> {parsedResume.email}
              </div>
            )}
            {parsedResume.phone && (
              <div className="info-item">
                <strong>Phone:</strong> {parsedResume.phone}
              </div>
            )}
            {parsedResume.experience_years > 0 && (
              <div className="info-item">
                <strong>Experience:</strong> {parsedResume.experience_years} years
              </div>
            )}
            {parsedResume.skills && parsedResume.skills.length > 0 && (
              <div className="info-item">
                <strong>Skills Detected:</strong>
                <div className="skills-list">
                  {parsedResume.skills.slice(0, 10).map((skill, idx) => (
                    <span key={idx} className="skill-tag">{skill}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {matchScore !== null && matchScore !== undefined && (
        <div className="match-score-section">
          <h3>
            <TrendingUp size={20} />
            Match Score
          </h3>
          <div className="score-display">
            <div className="score-value">{matchScore.toFixed(1)}%</div>
            <p>Your resume matches {matchScore.toFixed(1)}% with this job position</p>
          </div>
        </div>
      )}

      {aiSummary && (
        <div className="ai-summary-section">
          <h3>
            <Sparkles size={20} />
            AI Summary
          </h3>
          <p className="ai-text">{aiSummary}</p>
        </div>
      )}

      {interviewQuestions && interviewQuestions.length > 0 && (
        <div className="interview-questions-section">
          <h3>Suggested Interview Questions</h3>
          <p className="section-note">These questions may be asked during your interview:</p>
          <ul className="questions-list">
            {interviewQuestions.map((question, idx) => (
              <li key={idx}>{question}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="success-actions">
        <button className="btn btn-primary" onClick={onClose}>
          View My Applications
        </button>
      </div>
    </div>
  );
};

export default ApplicationSuccess;

