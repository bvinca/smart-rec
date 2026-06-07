# Fairness viz - heatmap + boxplot of scores by demographic group.
# matplotlib/seaborn/pandas imports guarded; missing deps -> success=False.
from typing import Dict, List, Any, Optional
import sys
import os

import logging
logger = logging.getLogger(__name__)

# optional viz deps - guarded so import works without matplotlib/seaborn/pandas
MATPLOTLIB_AVAILABLE = False
SEABORN_AVAILABLE = False

try:
    import matplotlib
    matplotlib.use('Agg')  # headless backend
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

NUMPY_AVAILABLE = False
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    logger.info("numpy not available. Install with: pip install numpy")
    np = None


class BiasVisualizer:
    # heatmaps + boxplots of score distributions per group, for the fairness reports

    def __init__(self, output_dir: str = "ai/reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def plot_bias_heatmap(
        self,
        candidate_data: List[Dict[str, Any]],
        group_col: str = "group",
        score_col: str = "overall_score",
        output_filename: str = "fairness_heatmap.png"
    ) -> Dict[str, Any]:
        # returns dict: success, file_path, message
        if not MATPLOTLIB_AVAILABLE or not PANDAS_AVAILABLE:
            return {
                "success": False,
                "file_path": None,
                "message": "matplotlib and pandas required for visualization. Install with: pip install matplotlib pandas"
            }

        try:
            df = pd.DataFrame(candidate_data)

            if group_col not in df.columns or score_col not in df.columns:
                return {
                    "success": False,
                    "file_path": None,
                    "message": f"Missing required columns: {group_col} or {score_col}"
                }

            # mean/std/count pivot - heatmap shows the mean row
            pivot = df.pivot_table(
                values=score_col,
                index=group_col,
                aggfunc=['mean', 'std', 'count']
            )

            # flatten the MultiIndex columns into "agg_col" names
            pivot.columns = ['_'.join(col).strip() for col in pivot.columns.values]

            plt.figure(figsize=(10, 6))

            if SEABORN_AVAILABLE:
                # seaborn heatmap - nicer default styling
                sns.heatmap(
                    pivot[['mean_' + score_col]].T,
                    annot=True,
                    fmt='.2f',
                    cmap='coolwarm',
                    center=pivot['mean_' + score_col].mean(),
                    cbar_kws={'label': 'Average Score'},
                    linewidths=0.5,
                    linecolor='gray'
                )
            else:
                # plain matplotlib fallback
                plt.imshow(pivot[['mean_' + score_col]].T.values, cmap='coolwarm', aspect='auto')
                plt.colorbar(label='Average Score')
                plt.xticks(range(len(pivot.index)), pivot.index, rotation=45, ha='right')
                plt.yticks([0], ['Mean Score'])

            plt.title('AI Fairness Heatmap by Group', fontsize=14, fontweight='bold', pad=20)
            plt.xlabel('Group', fontsize=12)
            plt.ylabel('Score Type', fontsize=12)
            plt.tight_layout()

            output_path = os.path.join(self.output_dir, output_filename)
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close()

            return {
                "success": True,
                "file_path": output_path,
                "message": f"Heatmap saved to {output_path}"
            }

        except Exception as e:
            import traceback
            logger.exception(f"BiasVisualizer: Error generating heatmap: {e}")
            logger.info(f"Traceback: {traceback.format_exc()}")
            return {
                "success": False,
                "file_path": None,
                "message": f"Error generating heatmap: {str(e)}"
            }

    def plot_score_distribution(
        self,
        candidate_data: List[Dict[str, Any]],
        group_col: str = "group",
        score_col: str = "overall_score",
        output_filename: str = "score_distribution.png"
    ) -> Dict[str, Any]:
        # box plot of score distribution per group
        if not MATPLOTLIB_AVAILABLE or not PANDAS_AVAILABLE:
            return {
                "success": False,
                "file_path": None,
                "message": "matplotlib and pandas required for visualization"
            }

        try:
            df = pd.DataFrame(candidate_data)

            if group_col not in df.columns or score_col not in df.columns:
                return {
                    "success": False,
                    "file_path": None,
                    "message": f"Missing required columns: {group_col} or {score_col}"
                }

            plt.figure(figsize=(12, 6))

            if SEABORN_AVAILABLE:
                # seaborn boxplot + scatter overlay
                sns.boxplot(data=df, x=group_col, y=score_col, palette='Set2')
                sns.stripplot(data=df, x=group_col, y=score_col, color='black', alpha=0.3, size=3)
            else:
                # matplotlib fallback
                groups = df[group_col].unique()
                data_by_group = [df[df[group_col] == group][score_col].values for group in groups]
                plt.boxplot(data_by_group, labels=groups)

            plt.title('Score Distribution by Group', fontsize=14, fontweight='bold', pad=20)
            plt.xlabel('Group', fontsize=12)
            plt.ylabel('Score', fontsize=12)
            plt.grid(axis='y', alpha=0.3)
            plt.tight_layout()

            output_path = os.path.join(self.output_dir, output_filename)
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close()

            return {
                "success": True,
                "file_path": output_path,
                "message": f"Distribution plot saved to {output_path}"
            }

        except Exception as e:
            import traceback
            logger.exception(f"BiasVisualizer: Error generating distribution plot: {e}")
            logger.info(f"Traceback: {traceback.format_exc()}")
            return {
                "success": False,
                "file_path": None,
                "message": f"Error generating plot: {str(e)}"
            }

    def generate_comprehensive_report(
        self,
        candidate_data: List[Dict[str, Any]],
        group_col: str = "group",
        score_col: str = "overall_score",
        output_prefix: str = "fairness_report"
    ) -> Dict[str, Any]:
        # bundles heatmap + distribution plot + summary stats into one call
        results = {
            "heatmap": self.plot_bias_heatmap(
                candidate_data, group_col, score_col,
                f"{output_prefix}_heatmap.png"
            ),
            "distribution": self.plot_score_distribution(
                candidate_data, group_col, score_col,
                f"{output_prefix}_distribution.png"
            )
        }

        # summary stats per group
        if PANDAS_AVAILABLE:
            try:
                df = pd.DataFrame(candidate_data)
                if group_col in df.columns and score_col in df.columns:
                    summary = df.groupby(group_col)[score_col].agg(['mean', 'std', 'min', 'max', 'count'])
                    results["summary_statistics"] = summary.to_dict('index')
                else:
                    results["summary_statistics"] = {}
            except Exception as e:
                results["summary_statistics"] = {"error": str(e)}
        else:
            results["summary_statistics"] = {}

        results["success"] = results["heatmap"]["success"] or results["distribution"]["success"]

        return results

