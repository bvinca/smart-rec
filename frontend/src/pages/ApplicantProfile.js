import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Upload, User, Mail, Building, Sparkles, MessageSquare, FileText } from 'lucide-react';
import { profileApi } from '../api/profile';
import { enhancementApi } from '../api/enhancement';
import { useAuth } from '../context/AuthContext';
import toast from 'react-hot-toast';
import './ApplicantProfile.css';

const ApplicantProfile = () => {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [selectedFile, setSelectedFile] = useState(null);
  const [resumeAnalysis, setResumeAnalysis] = useState(null);

  const { data: profile, isLoading } = useQuery({
    queryKey: ['profile'],
    queryFn: () => profileApi.get().then(res => res.data || res),
  });

  const { data: resumeData, isLoading: resumeLoading, refetch: refetchResume } = useQuery({
    queryKey: ['resume'],
    queryFn: () => profileApi.getResume().then(res => res.data || res),
    enabled: user?.role === 'applicant',
  });

  const updateMutation = useMutation({
    mutationFn: (data) => profileApi.update(data),
    onSuccess: () => {
      queryClient.invalidateQueries(['profile']);
      toast.success('Profile updated successfully');
    },
    onError: () => {
      toast.error('Failed to update profile');
    },
  });

  const uploadMutation = useMutation({
    mutationFn: (file) => profileApi.uploadResume(file),
    onSuccess: () => {
      queryClient.invalidateQueries(['resume']);
      refetchResume();
      toast.success('Resume uploaded successfully');
      setSelectedFile(null);
    },
    onError: (error) => {
      console.error('Upload error:', error);
      toast.error(error?.response?.data?.detail || 'Failed to upload resume');
    },
  });

  const generateSummaryMutation = useMutation({
    mutationFn: async () => {
      console.log('Calling profileApi.generateSummary()');
      try {
        const response = await profileApi.generateSummary();
        console.log('API call successful, response:', response);
        return response;
      } catch (error) {
        console.error('API call failed:', error);
        console.error('Error details:', {
          message: error?.message,
          response: error?.response,
          status: error?.response?.status,
          data: error?.response?.data
        });
        throw error;
      }
    },
    onSuccess: (response) => {
      console.log('Summary generation success:', response);
      const responseData = response?.data || response;
      console.log('Response data:', responseData);
      
      // refetch either way (success or server-side fail)
      queryClient.invalidateQueries(['resume']);
      refetchResume();

      if (responseData?.summary && responseData.summary !== "Unable to generate AI summary at this time." && responseData.summary !== null) {
        toast.success('AI summary generated successfully');
      } else {
        // show backend error text if summary failed
        const errorMsg = responseData?.error || responseData?.message || 'Failed to generate AI summary. Please check your OpenAI API key and quota.';
        toast.error(errorMsg, { duration: 8000 }); // give them time to read
      }
    },
    onError: (error) => {
      console.error('Summary generation error:', error);
      console.error('Error response:', error?.response);
      console.error('Error data:', error?.response?.data);
      const errorMessage = error?.response?.data?.detail || error?.response?.data?.message || error?.message || 'Failed to generate AI summary';
      console.error('Error message:', errorMessage);
      toast.error(errorMessage);
    },
  });

  const analyzeResumeMutation = useMutation({
    mutationFn: () => {
      const resumeText = resumeData?.extracted_data?.resume_text || resumeData?.resume_text || '';
      return enhancementApi.analyzeResume(
        resumeText,
        '', // profile analysis, no job context
        ''
      );
    },
    onSuccess: (response) => {
      setResumeAnalysis(response.data);
      toast.success('Resume analysis complete!');
    },
    onError: (error) => {
      const errorMsg = error.response?.data?.detail || error.message || 'Failed to analyze resume';
      toast.error(errorMsg);
    },
  });

  const handleFileChange = (e) => {
    setSelectedFile(e.target.files[0]);
  };

  const handleUpload = () => {
    if (selectedFile) {
      uploadMutation.mutate(selectedFile);
    }
  };

  const handleUpdate = (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const data = {
      first_name: formData.get('first_name'),
      last_name: formData.get('last_name'),
    };
    updateMutation.mutate(data);
  };

  if (isLoading) {
    return (
      <div className="loading-container">
        <div className="loading"></div>
        <p>Loading profile...</p>
      </div>
    );
  }

  return (
    <div className="applicant-profile">
      <div className="profile-header">
        <h1>My Profile</h1>
        <p>Manage your personal information and resume</p>
      </div>

      <div className="profile-content">
        <div className="profile-section">
          <h2>Personal Information</h2>
          <form onSubmit={handleUpdate}>
            <div className="form-group">
              <label>
                <Mail size={16} />
                Email
              </label>
              <input type="email" value={profile?.email || user?.email} disabled />
            </div>
            <div className="form-group">
              <label>
                <User size={16} />
                First Name
              </label>
              <input
                type="text"
                name="first_name"
                defaultValue={profile?.first_name || ''}
              />
            </div>
            <div className="form-group">
              <label>
                <User size={16} />
                Last Name
              </label>
              <input
                type="text"
                name="last_name"
                defaultValue={profile?.last_name || ''}
              />
            </div>
            <button type="submit" className="btn btn-primary" disabled={updateMutation.isLoading}>
              {updateMutation.isLoading ? 'Saving...' : 'Save Changes'}
            </button>
          </form>
        </div>

        <div className="profile-section">
          <h2>Resume</h2>
          <div className="resume-upload">
            <div className="upload-area">
              <Upload size={32} />
              <p>Upload your resume (PDF or DOCX)</p>
              <input
                type="file"
                accept=".pdf,.doc,.docx"
                onChange={handleFileChange}
                style={{ display: 'none' }}
                id="resume-upload"
              />
              <label htmlFor="resume-upload" className="btn btn-secondary">
                Choose File
              </label>
              {selectedFile && (
                <p className="file-name">{selectedFile.name}</p>
              )}
            </div>
            {selectedFile && (
              <button
                className="btn btn-primary"
                onClick={handleUpload}
                disabled={uploadMutation.isLoading}
              >
                {uploadMutation.isLoading ? 'Uploading...' : 'Upload Resume'}
              </button>
            )}
          </div>

          {/* parsed resume block */}
          {resumeLoading ? (
            <div className="loading-state">
              <p>Loading resume data...</p>
            </div>
          ) : resumeData?.extracted_data ? (
            <div className="resume-data">
              <h3>Parsed Resume Information</h3>
              <div className="resume-info-grid">
                {resumeData.extracted_data.skills && resumeData.extracted_data.skills.length > 0 && (
                  <div className="info-item">
                    <h4>Skills</h4>
                    <div className="skills-list">
                      {resumeData.extracted_data.skills.map((skill, idx) => (
                        <span key={idx} className="skill-tag">{skill}</span>
                      ))}
                    </div>
                  </div>
                )}
                
                {resumeData.extracted_data.experience_years > 0 && (
                  <div className="info-item">
                    <h4>Experience</h4>
                    <p>{resumeData.extracted_data.experience_years} years</p>
                  </div>
                )}

                {resumeData.extracted_data.education && resumeData.extracted_data.education.length > 0 && (
                  <div className="info-item">
                    <h4>Education</h4>
                    <ul>
                      {resumeData.extracted_data.education.map((edu, idx) => (
                        <li key={idx}>
                          {edu.degree && `${edu.degree} `}
                          {edu.major && `in ${edu.major} `}
                          {edu.institution && `from ${edu.institution}`}
                          {edu.year && ` (${edu.year})`}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {resumeData.extracted_data.work_experience && resumeData.extracted_data.work_experience.length > 0 && (
                  <div className="info-item">
                    <h4>Work Experience</h4>
                    <ul>
                      {resumeData.extracted_data.work_experience.map((exp, idx) => (
                        <li key={idx}>
                          <strong>{exp.title}</strong>
                          {exp.company && ` at ${exp.company}`}
                          {exp.duration && ` (${exp.duration})`}
                          {exp.description && <p className="exp-description">{exp.description}</p>}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {resumeData.extracted_data.ai_summary && resumeData.extracted_data.ai_summary !== "Unable to generate AI summary at this time." ? (
                  <div className="info-item ai-section">
                    <h4>
                      <Sparkles size={18} />
                      AI Summary
                    </h4>
                    <p className="ai-text">{resumeData.extracted_data.ai_summary}</p>
                  </div>
                ) : resumeData.extracted_data.resume_text ? (
                  <div className="info-item ai-section">
                    <h4>
                      <Sparkles size={18} />
                      AI Summary
                    </h4>
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        console.log('Generate summary button clicked');
                        console.log('Resume data:', resumeData);
                        generateSummaryMutation.mutate();
                      }}
                      disabled={generateSummaryMutation.isLoading}
                      style={{ marginBottom: '10px', display: 'block' }}
                    >
                      {generateSummaryMutation.isLoading ? 'Generating...' : 'Generate AI Summary'}
                    </button>
                    {generateSummaryMutation.isError && (
                      <div className="ai-text ai-unavailable" style={{ color: '#dc3545', marginTop: '10px', padding: '10px', backgroundColor: '#fff3cd', border: '1px solid #ffc107', borderRadius: '4px' }}>
                        <strong>Error:</strong> {generateSummaryMutation.error?.response?.data?.message || generateSummaryMutation.error?.response?.data?.error || generateSummaryMutation.error?.message || 'Failed to generate AI summary. Please check your OpenAI API key and backend logs.'}
                      </div>
                    )}
                    {generateSummaryMutation.isSuccess && !resumeData.extracted_data.ai_summary && (
                      <div className="ai-text ai-unavailable" style={{ color: '#dc3545', marginTop: '10px', padding: '10px', backgroundColor: '#fff3cd', border: '1px solid #ffc107', borderRadius: '4px' }}>
                        <strong>Note:</strong> Summary generation failed. This is likely due to OpenAI API quota limits. Please check your OpenAI account billing and add credits.
                      </div>
                    )}
                    {!generateSummaryMutation.isError && !generateSummaryMutation.isSuccess && !resumeData.extracted_data.ai_summary && (
                      <p className="ai-text ai-unavailable">
                        AI summary is currently unavailable. Click the button above to generate one.
                      </p>
                    )}
                  </div>
                ) : null}

                {resumeData.extracted_data.interview_questions && resumeData.extracted_data.interview_questions.length > 0 && (
                  <div className="info-item">
                    <h4>
                      <MessageSquare size={18} />
                      Suggested Interview Questions
                    </h4>
                    <ol className="questions-list">
                      {resumeData.extracted_data.interview_questions.map((question, idx) => (
                        <li key={idx}>{question}</li>
                      ))}
                    </ol>
                  </div>
                )}

                {resumeData.extracted_data.resume_text && (
                  <div className="info-item">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                      <h4>Resume Analysis</h4>
                      <button 
                        className="btn btn-secondary btn-sm" 
                        onClick={() => analyzeResumeMutation.mutate()}
                        disabled={analyzeResumeMutation.isLoading}
                        style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', padding: '6px 12px' }}
                      >
                        <FileText size={14} />
                        {analyzeResumeMutation.isLoading ? 'Analyzing...' : 'Analyze Resume'}
                      </button>
                    </div>
                    {resumeAnalysis && (
                      <div className="resume-analysis" style={{ 
                        marginTop: '15px', 
                        padding: '15px', 
                        backgroundColor: '#fef3c7', 
                        borderRadius: '8px',
                        border: '1px solid #fde68a'
                      }}>
                        <h5 style={{ marginTop: 0, color: '#92400e' }}>Resume Feedback</h5>
                        {resumeAnalysis.summary_feedback && (
                          <p style={{ marginBottom: '12px', fontSize: '14px', whiteSpace: 'pre-wrap' }}>
                            {resumeAnalysis.summary_feedback}
                          </p>
                        )}
                        
                        {resumeAnalysis.strengths && resumeAnalysis.strengths.length > 0 && (
                          <div style={{ marginBottom: '12px' }}>
                            <strong style={{ color: '#10b981' }}>Strengths:</strong>
                            <ul style={{ margin: '4px 0', paddingLeft: '20px', fontSize: '14px' }}>
                              {resumeAnalysis.strengths.map((strength, idx) => (
                                <li key={idx}>{strength}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        
                        {resumeAnalysis.weaknesses && resumeAnalysis.weaknesses.length > 0 && (
                          <div style={{ marginBottom: '12px' }}>
                            <strong style={{ color: '#ef4444' }}>Areas for Improvement:</strong>
                            <ul style={{ margin: '4px 0', paddingLeft: '20px', fontSize: '14px' }}>
                              {resumeAnalysis.weaknesses.map((weakness, idx) => (
                                <li key={idx}>{weakness}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        
                        {resumeAnalysis.missing_skills && resumeAnalysis.missing_skills.length > 0 && (
                          <div style={{ marginBottom: '12px' }}>
                            <strong style={{ color: '#f59e0b' }}>Missing Skills to Consider:</strong>
                            <ul style={{ margin: '4px 0', paddingLeft: '20px', fontSize: '14px' }}>
                              {resumeAnalysis.missing_skills.map((skill, idx) => (
                                <li key={idx}>{skill}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        
                        {resumeAnalysis.keyword_suggestions && resumeAnalysis.keyword_suggestions.length > 0 && (
                          <div>
                            <strong style={{ color: '#3b82f6' }}>Keyword Suggestions:</strong>
                            <div style={{ marginTop: '4px' }}>
                              {resumeAnalysis.keyword_suggestions.map((keyword, idx) => (
                                <span key={idx} className="skill-tag" style={{ backgroundColor: '#dbeafe', color: '#1e40af', marginRight: '6px', marginBottom: '4px' }}>
                                  {keyword}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="no-resume-data">
              <p>No parsed resume data available. Upload a resume when applying to a job to see parsed information.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ApplicantProfile;

