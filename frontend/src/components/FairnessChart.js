import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { TrendingDown, TrendingUp } from 'lucide-react';
import './FairnessChart.css';

const FairnessChart = ({ metricsData = [] }) => {
  if (!metricsData || metricsData.length < 2) {
    return (
      <div className="fairness-chart-empty">
        <p>Need at least 2 data points to display trends</p>
      </div>
    );
  }

  // shape data for recharts
  const chartData = metricsData.map((metric, index) => ({
    date: new Date(metric.created_at).toLocaleDateString(),
    msd: metric.mean_score_difference || 0,
    dir: metric.disparate_impact_ratio || 1.0,
    bias: metric.bias_magnitude || 0
  }));

  // first vs last point for trend arrows
  const msdTrend = chartData.length > 1
    ? (chartData[chartData.length - 1].msd < chartData[0].msd ? 'down' : 'up')
    : null;
  const biasTrend = chartData.length > 1
    ? (chartData[chartData.length - 1].bias < chartData[0].bias ? 'down' : 'up')
    : null;

  return (
    <div className="fairness-chart">
      <div className="chart-header">
        <h3>Fairness Trends Over Time</h3>
        <div className="trend-indicators">
          {msdTrend && (
            <div className={`trend-indicator ${msdTrend}`}>
              {msdTrend === 'down' ? <TrendingDown size={16} /> : <TrendingUp size={16} />}
              <span>MSD {msdTrend === 'down' ? '↓' : '↑'}</span>
            </div>
          )}
          {biasTrend && (
            <div className={`trend-indicator ${biasTrend}`}>
              {biasTrend === 'down' ? <TrendingDown size={16} /> : <TrendingUp size={16} />}
              <span>Bias {biasTrend === 'down' ? '↓' : '↑'}</span>
            </div>
          )}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" />
          <YAxis yAxisId="left" />
          <YAxis yAxisId="right" orientation="right" />
          <Tooltip />
          <Legend />
          <Line 
            yAxisId="left"
            type="monotone" 
            dataKey="msd" 
            stroke="#8884d8" 
            name="Mean Score Difference (MSD)"
            strokeWidth={2}
          />
          <Line 
            yAxisId="right"
            type="monotone" 
            dataKey="dir" 
            stroke="#82ca9d" 
            name="Disparate Impact Ratio (DIR)"
            strokeWidth={2}
          />
          <Line 
            yAxisId="left"
            type="monotone" 
            dataKey="bias" 
            stroke="#ff7300" 
            name="Bias Magnitude (%)"
            strokeWidth={2}
          />
        </LineChart>
      </ResponsiveContainer>

      <div className="chart-footer">
        <div className="metric-summary">
          <div className="metric-item">
            <span className="metric-label">Current MSD:</span>
            <span className="metric-value">
              {chartData[chartData.length - 1]?.msd.toFixed(2) || 'N/A'} points
            </span>
          </div>
          <div className="metric-item">
            <span className="metric-label">Current DIR:</span>
            <span className="metric-value">
              {chartData[chartData.length - 1]?.dir.toFixed(3) || 'N/A'}
            </span>
          </div>
          <div className="metric-item">
            <span className="metric-label">Current Bias:</span>
            <span className="metric-value">
              {chartData[chartData.length - 1]?.bias.toFixed(2) || 'N/A'}%
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FairnessChart;

