import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { analyticsApi } from '../api/analytics';
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from 'recharts';
import { TrendingUp, Users, Briefcase, Award } from 'lucide-react';
import './Analytics.css';

const Analytics = () => {
  const { data: analytics, isLoading } = useQuery({
    queryKey: ['analytics'],
    queryFn: () => analyticsApi.get().then(res => res.data),
  });

  if (isLoading) {
    return (
      <div className="loading-container">
        <div className="loading"></div>
        <p>Loading analytics...</p>
      </div>
    );
  }

  if (!analytics) {
    return <div>No analytics data available</div>;
  }

  const stats = {
    totalJobs: analytics.total_jobs,
    totalApplicants: analytics.total_applications,
    averageScore: analytics.average_score.toFixed(1),
    shortlisted: analytics.shortlisted_applications,
  };

  const statusData = [
    { name: 'Pending', value: analytics.pending_applications },
    { name: 'Shortlisted', value: analytics.shortlisted_applications },
    { name: 'Rejected', value: analytics.rejected_applications },
    { name: 'Hired', value: analytics.hired_applications },
  ];

  const COLORS = ['#2563eb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];

  return (
    <div className="analytics-page">
      <div className="page-header">
        <div>
          <h1>Analytics Dashboard</h1>
          <p>Insights and statistics about your recruitment process</p>
        </div>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon" style={{ background: '#dbeafe' }}>
            <Briefcase size={24} color="#2563eb" />
          </div>
          <div className="stat-content">
            <h3>{stats.totalJobs}</h3>
            <p>Total Jobs</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ background: '#d1fae5' }}>
            <Users size={24} color="#10b981" />
          </div>
          <div className="stat-content">
            <h3>{stats.totalApplicants}</h3>
            <p>Total Applicants</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ background: '#fef3c7' }}>
            <TrendingUp size={24} color="#f59e0b" />
          </div>
          <div className="stat-content">
            <h3>{stats.averageScore}%</h3>
            <p>Average Match Score</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ background: '#ddd6fe' }}>
            <Award size={24} color="#8b5cf6" />
          </div>
          <div className="stat-content">
            <h3>{stats.shortlisted}</h3>
            <p>Shortlisted</p>
          </div>
        </div>
      </div>

      <div className="charts-grid">
        <div className="chart-card">
          <h2>Applicant Status Distribution</h2>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={statusData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {statusData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card">
          <h2>Top Skills</h2>
          <div className="top-skills">
            {analytics.top_skills?.slice(0, 10).map((skill, index) => (
              <div key={index} className="skill-item">
                <span className="skill-name">{skill.skill}</span>
                <span className="skill-count">{skill.count}</span>
              </div>
            )) || <p>No skills data available</p>}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Analytics;

