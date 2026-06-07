# Fairness trend charts - MSD + DIR over time, plus bias-reduction view.
# Viz deps (matplotlib/seaborn/pandas) all guarded; methods return success=False if missing.
from typing import Dict, List, Any, Optional
import sys
import os

import logging
logger = logging.getLogger(__name__)

# optional viz deps
MATPLOTLIB_AVAILABLE = False
SEABORN_AVAILABLE = False

try:
    import matplotlib
    matplotlib.use('Agg')  # headless
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    logger.info("matplotlib not available. Install with: pip install matplotlib")
    plt = None

try:
    import seaborn as sns
    SEABORN_AVAILABLE = True
except ImportError:
    logger.info("seaborn not available. Install with: pip install seaborn")
    sns = None

PANDAS_AVAILABLE = False
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    logger.info("pandas not available. Install with: pip install pandas")
    pd = None

# add backend to path
backend_path = os.path.join(os.path.dirname(__file__), '../../../backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

try:
    from app.models import FairnessMetric
except ImportError:
    FairnessMetric = None
    logger.info("FairnessMetric model not available")


class FairnessTrendsVisualizer:
    # MSD + DIR over time, bias-reduction summary

    def __init__(self, output_dir: str = "ai/reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def plot_fairness_trends(
        self,
        metrics_data: List[Dict[str, Any]],
        output_filename: str = "fairness_trends.png"
    ) -> Dict[str, Any]:
        # metrics_data rows must have: created_at, mean_score_difference,
        # disparate_impact_ratio, bias_magnitude
        if not MATPLOTLIB_AVAILABLE or not PANDAS_AVAILABLE:
            return {
                "success": False,
                "file_path": None,
                "message": "matplotlib and pandas required for visualization"
            }
        
        if not metrics_data or len(metrics_data) < 2:
            return {
                "success": False,
                "file_path": None,
                "message": "Need at least 2 data points to plot trends"
            }
        
        try:
            df = pd.DataFrame(metrics_data)

            # parse timestamps + sort chronologically
            if 'created_at' in df.columns:
                df['created_at'] = pd.to_datetime(df['created_at'])
                df = df.sort_values('created_at')
            
            # two stacked subplots: MSD on top, DIR below
            fig, axes = plt.subplots(2, 1, figsize=(12, 10))

            # MSD over time - target line at 10
            ax1 = axes[0]
            if 'mean_score_difference' in df.columns:
                ax1.plot(df['created_at'], df['mean_score_difference'], 
                        marker='o', linewidth=2, markersize=6, label='MSD')
                ax1.axhline(y=10, color='r', linestyle='--', alpha=0.5, label='Target (< 10)')
                ax1.set_ylabel('Mean Score Difference (MSD)', fontsize=12)
                ax1.set_title('Fairness Trend: Mean Score Difference Over Time', 
                             fontsize=14, fontweight='bold', pad=20)
                ax1.legend()
                ax1.grid(True, alpha=0.3)
            
            # DIR over time - shaded acceptable band 0.8-1.2
            ax2 = axes[1]
            if 'disparate_impact_ratio' in df.columns:
                ax2.plot(df['created_at'], df['disparate_impact_ratio'], 
                        marker='s', linewidth=2, markersize=6, label='DIR', color='green')
                ax2.axhline(y=0.8, color='r', linestyle='--', alpha=0.5, label='Lower bound (0.8)')
                ax2.axhline(y=1.2, color='r', linestyle='--', alpha=0.5, label='Upper bound (1.2)')
                ax2.fill_between(df['created_at'], 0.8, 1.2, alpha=0.2, color='green', label='Acceptable range')
                ax2.set_ylabel('Disparate Impact Ratio (DIR)', fontsize=12)
                ax2.set_xlabel('Date', fontsize=12)
                ax2.set_title('Fairness Trend: Disparate Impact Ratio Over Time', 
                             fontsize=14, fontweight='bold', pad=20)
                ax2.legend()
                ax2.grid(True, alpha=0.3)
            
            plt.tight_layout()

            output_path = os.path.join(self.output_dir, output_filename)
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close()

            # quick trend stats - direction + delta vs first point
            trend_stats = {}
            if 'mean_score_difference' in df.columns:
                msd_values = df['mean_score_difference'].values
                if len(msd_values) > 1:
                    trend_stats['msd_trend'] = 'decreasing' if msd_values[-1] < msd_values[0] else 'increasing'
                    trend_stats['msd_change'] = float(msd_values[-1] - msd_values[0])
                    trend_stats['msd_improvement'] = msd_values[-1] < msd_values[0]
            
            if 'disparate_impact_ratio' in df.columns:
                dir_values = df['disparate_impact_ratio'].values
                if len(dir_values) > 1:
                    trend_stats['dir_trend'] = 'improving' if 0.8 <= dir_values[-1] <= 1.2 else 'needs_attention'
                    trend_stats['dir_change'] = float(dir_values[-1] - dir_values[0])
            
            return {
                "success": True,
                "file_path": output_path,
                "message": f"Trends plot saved to {output_path}",
                "trend_statistics": trend_stats
            }
            
        except Exception as e:
            import traceback
            logger.exception(f"FairnessTrendsVisualizer: Error generating trends plot: {e}")
            logger.info(f"FairnessTrendsVisualizer: Traceback: {traceback.format_exc()}")
            return {
                "success": False,
                "file_path": None,
                "message": f"Error generating plot: {str(e)}"
            }
    
    def plot_bias_reduction(
        self,
        metrics_data: List[Dict[str, Any]],
        output_filename: str = "bias_reduction.png"
    ) -> Dict[str, Any]:
        # bias magnitude over time, plus initial vs final % reduction summary
        if not MATPLOTLIB_AVAILABLE or not PANDAS_AVAILABLE:
            return {
                "success": False,
                "file_path": None,
                "message": "matplotlib and pandas required"
            }
        
        try:
            df = pd.DataFrame(metrics_data)
            
            if 'created_at' in df.columns:
                df['created_at'] = pd.to_datetime(df['created_at'])
                df = df.sort_values('created_at')
            
            plt.figure(figsize=(12, 6))
            
            if 'bias_magnitude' in df.columns:
                plt.plot(df['created_at'], df['bias_magnitude'], 
                        marker='o', linewidth=2, markersize=8, color='red', label='Bias Magnitude')
                plt.axhline(y=10, color='orange', linestyle='--', alpha=0.7, label='Warning threshold (10%)')
                plt.fill_between(df['created_at'], 0, df['bias_magnitude'], 
                               alpha=0.3, color='red')
                plt.ylabel('Bias Magnitude (%)', fontsize=12)
                plt.xlabel('Date', fontsize=12)
                plt.title('Bias Reduction Over Time', fontsize=14, fontweight='bold', pad=20)
                plt.legend()
                plt.grid(True, alpha=0.3)
                plt.tight_layout()
                
                output_path = os.path.join(self.output_dir, output_filename)
                plt.savefig(output_path, dpi=300, bbox_inches='tight')
                plt.close()
                
                # % reduction since first measurement
                if len(df) > 1:
                    initial_bias = df['bias_magnitude'].iloc[0]
                    final_bias = df['bias_magnitude'].iloc[-1]
                    reduction = ((initial_bias - final_bias) / initial_bias * 100) if initial_bias > 0 else 0
                    
                    return {
                        "success": True,
                        "file_path": output_path,
                        "message": f"Bias reduction plot saved to {output_path}",
                        "reduction_percentage": round(reduction, 2),
                        "initial_bias": round(float(initial_bias), 2),
                        "final_bias": round(float(final_bias), 2)
                    }
                
                return {
                    "success": True,
                    "file_path": output_path,
                    "message": f"Bias reduction plot saved to {output_path}"
                }
            
            return {
                "success": False,
                "file_path": None,
                "message": "bias_magnitude column not found in data"
            }
            
        except Exception as e:
            import traceback
            logger.exception(f"FairnessTrendsVisualizer: Error generating bias reduction plot: {e}")
            logger.info(f"FairnessTrendsVisualizer: Traceback: {traceback.format_exc()}")
            return {
                "success": False,
                "file_path": None,
                "message": f"Error generating plot: {str(e)}"
            }

