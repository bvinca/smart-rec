import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { fairnessApi } from '../api/fairness';
import { Shield, TrendingUp, AlertTriangle, CheckCircle, BarChart3, Download, Loader, Info } from 'lucide-react';
import toast from 'react-hot-toast';
import './FairnessDashboard.css';

// hover-triggered popup for fairness metric definitions
const InfoTooltip = ({ children }) => (
  <span className="info-tooltip">
    <Info size={14} className="info-tooltip-icon" />
    <span className="info-tooltip-content">{children}</span>
  </span>
);

const FairnessDashboard = ({ jobId = null }) => {
  const [showVisualization, setShowVisualization] = useState(false);
  const [visualizationData, setVisualizationData] = useState(null);
  const [isGeneratingViz, setIsGeneratingViz] = useState(false);

  // fairness audit for this job (all jobs if jobId is null)
  const { data: auditResult, isLoading, error: auditError, refetch } = useQuery({
    queryKey: ['fairness-audit', jobId],
    queryFn: () => fairnessApi.auditFairness(jobId).then(res => res.data),
    enabled: true,
    retry: 1,
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to load fairness audit');
    }
  });

  // backend renders heatmap + distribution PNGs
  const generateVisualization = async () => {
    setIsGeneratingViz(true);
    try {
      const response = await fairnessApi.generateVisualization(jobId);
      setVisualizationData(response.data);
      setShowVisualization(true);
      toast.success('Visualization generated successfully');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to generate visualization');
    } finally {
      setIsGeneratingViz(false);
    }
  };

  if (isLoading) {
    return (
      <div className="fairness-dashboard loading">
        <Loader className="spinner" />
        <p>Loading fairness audit...</p>
      </div>
    );
  }

  if (!auditResult) {
    const detail = auditError?.response?.data?.detail;
    return (
      <div className="fairness-dashboard error">
        <AlertTriangle size={24} />
        <p>{detail || 'No fairness data available. Need at least 2 applicants to perform audit.'}</p>
      </div>
    );
  }

  const {
    bias_detected,
    bias_magnitude,
    mean_score_difference,
    disparate_impact_ratio,
    fairness_status,
    group_analysis,
    recommendations = [],
    metrics_summary = {},
    message
  } = auditResult;

  const getStatusIcon = () => {
    if (fairness_status === 'fair') return <CheckCircle className="status-icon fair" />;
    if (fairness_status === 'warning') return <AlertTriangle className="status-icon warning" />;
    return <AlertTriangle className="status-icon bias" />;
  };

  const getStatusColor = () => {
    if (fairness_status === 'fair') return '#10b981';
    if (fairness_status === 'warning') return '#f59e0b';
    return '#ef4444';
  };

  return (
    <div className="fairness-dashboard">
      <div className="dashboard-header">
        <div className="header-title">
          <Shield size={24} />
          <h2>AI Fairness Audit</h2>
        </div>
        <button
          onClick={generateVisualization}
          disabled={isGeneratingViz}
          className="btn-generate-viz"
        >
          {isGeneratingViz ? (
            <>
              <Loader className="spinner-small" />
              Generating...
            </>
          ) : (
            <>
              <BarChart3 size={18} />
              Generate Visualization
            </>
          )}
        </button>
      </div>

      {/* status */}
      <div className="status-card" style={{ borderColor: getStatusColor() }}>
        <div className="status-header">
          {getStatusIcon()}
          <div>
            <h3>
              Fairness Status: {fairness_status?.toUpperCase() || 'UNKNOWN'}
              <InfoTooltip>
                The overall verdict.
                <strong> FAIR</strong> = groups look balanced.
                <strong> WARNING</strong> = something looks off — worth a closer look.
                <strong> BIAS_DETECTED</strong> = one group is scoring much higher than another.
              </InfoTooltip>
            </h3>
            <p className="status-message">{message}</p>
          </div>
        </div>
      </div>

      {/* MSD / DIR / bias */}
      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-header">
            <TrendingUp size={20} />
            <span>Mean Score Difference (MSD)</span>
            <InfoTooltip>
              The score gap between the best- and worst-performing groups.
              Anything above <strong>10 points</strong> is a gap big enough to be
              worth checking the scoring for bias.
            </InfoTooltip>
          </div>
          <div className="metric-value">
            {mean_score_difference?.toFixed(2) || 'N/A'} points
          </div>
          <div className="metric-target">
            Target: &lt; 10 points
            {metrics_summary.msd_status && (
              <span className={`status-badge ${metrics_summary.msd_status.includes('Pass') ? 'pass' : 'fail'}`}>
                {metrics_summary.msd_status}
              </span>
            )}
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <Shield size={20} />
            <span>Disparate Impact Ratio (DIR)</span>
            <InfoTooltip>
              Are groups being shortlisted at similar rates? Stay between
              <strong> 0.8 and 1.2</strong>. Below 0.8 means one group is being
              passed over much more often. A value of 0 usually just means
              the groups are too small to compare fairly.
            </InfoTooltip>
          </div>
          <div className="metric-value">
            {disparate_impact_ratio?.toFixed(3) || 'N/A'}
          </div>
          <div className="metric-target">
            Target: 0.8 - 1.2 (80% rule)
            {metrics_summary.dir_status && (
              <span className={`status-badge ${metrics_summary.dir_status.includes('Pass') ? 'pass' : 'fail'}`}>
                {metrics_summary.dir_status}
              </span>
            )}
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <AlertTriangle size={20} />
            <span>Bias Magnitude</span>
            <InfoTooltip>
              The same score gap, shown as a percentage.
              <strong> Lower is better.</strong>
            </InfoTooltip>
          </div>
          <div className="metric-value" style={{ color: bias_detected ? '#ef4444' : '#10b981' }}>
            {bias_magnitude?.toFixed(2) || '0.00'}%
          </div>
          <div className="metric-target">
            {bias_detected ? '⚠️ Bias detected' : '✅ No bias detected'}
          </div>
        </div>
      </div>

      {/* per-group stats */}
      {group_analysis && Object.keys(group_analysis).length > 0 && (
        <div className="group-analysis">
          <h3>Group Analysis</h3>
          <div className="group-cards">
            {Object.entries(group_analysis).map(([group, stats]) => (
              <div key={group} className="group-card">
                <div className="group-name">{group}</div>
                <div className="group-stats">
                  <div className="stat-item">
                    <span className="stat-label">Mean Score:</span>
                    <span className="stat-value">{stats.mean_score?.toFixed(2) || 'N/A'}%</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-label">Std Dev:</span>
                    <span className="stat-value">{stats.std_dev?.toFixed(2) || 'N/A'}</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-label">Count:</span>
                    <span className="stat-value">{stats.count || 0}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* suggested fixes */}
      {recommendations && recommendations.length > 0 && (
        <div className="recommendations">
          <h3>Recommendations</h3>
          <ul>
            {recommendations.map((rec, index) => (
              <li key={index}>{rec}</li>
            ))}
          </ul>
        </div>
      )}

      {/* chart images */}
      {showVisualization && visualizationData && (
        <div className="visualization-section">
          <h3>Fairness Visualizations</h3>
          <div className="viz-container">
            {visualizationData.heatmap_path && (
              <div className="viz-item">
                <h4>Score Heatmap</h4>
                <img
                  src={`http://localhost:8000/${visualizationData.heatmap_path.replace(/\\/g, '/')}`}
                  alt="Fairness Heatmap"
                  onError={(e) => {
                    e.target.style.display = 'none';
                    toast.error('Could not load heatmap image');
                  }}
                />
              </div>
            )}
            {visualizationData.distribution_path && (
              <div className="viz-item">
                <h4>Score Distribution</h4>
                <img
                  src={`http://localhost:8000/${visualizationData.distribution_path.replace(/\\/g, '/')}`}
                  alt="Score Distribution"
                  onError={(e) => {
                    e.target.style.display = 'none';
                    toast.error('Could not load distribution plot');
                  }}
                />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default FairnessDashboard;

