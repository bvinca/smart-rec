import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { fairnessApi } from '../api/fairness';
import FairnessChart from './FairnessChart';
import { Loader, AlertCircle } from 'lucide-react';
import toast from 'react-hot-toast';

const FairnessTrendsWidget = ({ jobId }) => {
  const { data: trendsData, isLoading, error } = useQuery({
    queryKey: ['fairness-trends', jobId],
    queryFn: () => fairnessApi.getTrends(jobId).then(res => res.data),
    enabled: !!jobId,
    retry: 1,
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to load fairness trends');
    }
  });

  if (isLoading) {
    return (
      <div className="fairness-trends-loading">
        <Loader className="spinner" />
        <p>Loading fairness trends...</p>
      </div>
    );
  }

  if (error || !trendsData || !trendsData.metrics || trendsData.metrics.length < 2) {
    return (
      <div className="fairness-trends-empty">
        <AlertCircle size={20} />
        <p>Need at least 2 fairness audits to show trends. Run fairness audits to build historical data.</p>
      </div>
    );
  }

  return (
    <div className="fairness-trends-widget">
      <FairnessChart metricsData={trendsData.metrics} />
      {trendsData.bias_reduction !== undefined && (
        <div className="bias-reduction-summary">
          <h4>Bias Reduction</h4>
          <p>
            {trendsData.bias_reduction > 0 ? '↓' : '↑'} 
            {Math.abs(trendsData.bias_reduction).toFixed(1)}% 
            {trendsData.bias_reduction > 0 ? 'reduction' : 'increase'} over time
          </p>
        </div>
      )}
    </div>
  );
};

export default FairnessTrendsWidget;

