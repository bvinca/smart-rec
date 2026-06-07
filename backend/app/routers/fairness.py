# fairness audit - MSD/DIR/SPD metrics and bias viz
# groups by CV tiers (no consent) or self-declared demographics (consent required)

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

# ai/ imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from ai.evaluation.fairness_checker import FairnessChecker  # noqa: E402

from app import models, schemas  # noqa: E402
from app.database import get_db  # noqa: E402
from app.dependencies import require_recruiter  # noqa: E402

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/fairness", tags=["fairness"])

_checker: Optional[FairnessChecker] = None


def _get_checker() -> FairnessChecker:
    global _checker
    if _checker is None:
        _checker = FairnessChecker()
    return _checker


# grouping helpers
_DEMOGRAPHIC_KEYS = {"gender", "age_band", "ethnicity", "disability"}
_TIER_KEYS = {"experience_tier", "education_tier"}


def _experience_tier(years: float) -> str:
    if years is None:
        return "unknown"
    if years < 1:
        return "entry"
    if years < 3:
        return "junior"
    if years < 6:
        return "mid"
    if years < 10:
        return "senior"
    return "lead"


_STEM_KEYWORDS = (
    "computer", "engineering", "science", "technology",
    "math", "statistics", "physics", "data",
)


def _education_tier(applicant: models.Applicant) -> str:
    if not applicant.education:
        return "unknown"
    blob = " ".join(
        (edu.get("degree", "") + " " + edu.get("institution", "")).lower()
        for edu in applicant.education
    )
    return "stem" if any(keyword in blob for keyword in _STEM_KEYWORDS) else "non_stem"


def _candidate_rows(
    db: Session,
    job_id: Optional[int],
    group_key: str,
    require_consent: bool,
) -> List[Dict[str, Any]]:
    # per-candidate dicts for FairnessChecker
    query = db.query(models.Applicant)
    if job_id is not None:
        query = query.filter(models.Applicant.job_id == job_id)
    applicants = query.all()
    if not applicants:
        return []

    rows: List[Dict[str, Any]] = []
    user_lookup: Dict[str, models.User] = {}

    if require_consent:
        # join users by email for consenting demographics
        emails = {a.email for a in applicants if a.email}
        if emails:
            users = db.query(models.User).filter(models.User.email.in_(emails)).all()
            user_lookup = {u.email: u for u in users}

    for applicant in applicants:
        score = applicant.overall_score or 0.0
        if group_key == "experience_tier":
            group = _experience_tier(applicant.experience_years or 0.0)
        elif group_key == "education_tier":
            group = _education_tier(applicant)
        elif group_key in _DEMOGRAPHIC_KEYS:
            user = user_lookup.get(applicant.email)
            if not user or not user.demographic_consent:
                continue  # skip non-consenting
            value = getattr(user, f"demographic_{group_key}", None)
            if not value:
                continue
            group = str(value)
        else:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Unsupported group_key. Use 'experience_tier', 'education_tier', "
                    "or one of " + ", ".join(sorted(_DEMOGRAPHIC_KEYS)) + " (with consent)."
                ),
            )

        rows.append(
            {
                "group": group,
                "overall_score": score,
                "skill_score": applicant.skill_score or 0.0,
                "experience_score": applicant.experience_score or 0.0,
                "education_score": applicant.education_score or 0.0,
            }
        )
    return rows


# routes
@router.post("/audit", response_model=schemas.FairnessAuditResponse)
def audit_fairness(
    request: schemas.FairnessAuditRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_recruiter),
):
    # run MSD/DIR audit on one job or whole pool
    if request.job_id is not None:
        job = db.query(models.Job).filter(
            models.Job.id == request.job_id,
            models.Job.recruiter_id == current_user.id,
        ).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

    group_key = (request.group_key or "experience_tier").lower()
    require_consent = group_key in _DEMOGRAPHIC_KEYS

    rows = _candidate_rows(db, request.job_id, group_key, require_consent)
    if len(rows) < 2:
        raise HTTPException(
            status_code=400,
            detail=(
                "Need at least two scored candidates with the requested grouping to audit. "
                + ("Demographic groupings only consider users who have consented." if require_consent else "")
            ),
        )

    checker = _get_checker()
    result = checker.comprehensive_fairness_audit(
        candidate_data=rows,
        group_key="group",
        score_key=request.score_key or "overall_score",
        threshold=request.threshold or 10.0,
        pass_threshold=request.pass_threshold or 70.0,
    )

    # persist for trends chart
    try:
        metric = models.FairnessMetric(
            job_id=request.job_id,
            mean_score_difference=result.get("mean_score_difference", 0.0),
            disparate_impact_ratio=result.get("disparate_impact_ratio", 1.0),
            bias_magnitude=result.get("bias_magnitude", 0.0),
            bias_detected=result.get("bias_detected", False),
            group_analysis=result.get("group_analysis", {}),
            candidate_count=len(rows),
            threshold_used=request.threshold or 10.0,
        )
        db.add(metric)
        db.commit()
    except Exception:  # pragma: no cover - logging only
        logger.exception("Failed to persist fairness metric.")

    result["group_key"] = group_key
    return result


@router.post("/visualize")
def generate_fairness_visualization(
    request: schemas.FairnessAuditRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_recruiter),
):
    # heatmap + distribution PNGs for dashboard
    from ai.evaluation.bias_visualizer import BiasVisualizer  # local import - heavy deps

    if request.job_id is not None:
        job = db.query(models.Job).filter(
            models.Job.id == request.job_id,
            models.Job.recruiter_id == current_user.id,
        ).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

    group_key = (request.group_key or "experience_tier").lower()
    require_consent = group_key in _DEMOGRAPHIC_KEYS
    rows = _candidate_rows(db, request.job_id, group_key, require_consent)
    if len(rows) < 2:
        raise HTTPException(
            status_code=400,
            detail="Need at least two scored candidates to visualise.",
        )

    visualizer = BiasVisualizer()
    output_prefix = (
        f"fairness_job_{request.job_id}" if request.job_id else "fairness_global"
    ) + f"_{group_key}"
    report = visualizer.generate_comprehensive_report(
        candidate_data=rows,
        group_col="group",
        score_col=request.score_key or "overall_score",
        output_prefix=output_prefix,
    )
    return {
        "success": report.get("success", False),
        "heatmap_path": (report.get("heatmap") or {}).get("file_path"),
        "distribution_path": (report.get("distribution") or {}).get("file_path"),
        "summary_statistics": report.get("summary_statistics", {}),
        "group_key": group_key,
    }


@router.get("/trends/{job_id}", response_model=dict)
def get_fairness_trends(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_recruiter),
):
    # historical fairness metrics for trends chart
    job = db.query(models.Job).filter(
        models.Job.id == job_id,
        models.Job.recruiter_id == current_user.id,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    metrics = db.query(models.FairnessMetric).filter(
        models.FairnessMetric.job_id == job_id
    ).order_by(models.FairnessMetric.created_at.asc()).all()

    metrics_data = [
        {
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "mean_score_difference": float(m.mean_score_difference),
            "disparate_impact_ratio": float(m.disparate_impact_ratio),
            "bias_magnitude": float(m.bias_magnitude),
            "bias_detected": m.bias_detected,
            "candidate_count": m.candidate_count,
        }
        for m in metrics
    ]

    if len(metrics_data) < 2:
        return {
            "job_id": job_id,
            "metrics": metrics_data,
            "message": "At least two audits are required to compute trends.",
        }

    try:
        from ai.visualization.fairness_trends_visualizer import FairnessTrendsVisualizer

        visualizer = FairnessTrendsVisualizer()
        trends_result = visualizer.plot_fairness_trends(
            metrics_data=metrics_data,
            output_filename=f"fairness_trends_job_{job_id}.png",
        )
        bias_result = visualizer.plot_bias_reduction(
            metrics_data=metrics_data,
            output_filename=f"bias_reduction_job_{job_id}.png",
        )
    except Exception:  # pragma: no cover - matplotlib problems
        logger.exception("Trends visualisation failed.")
        trends_result = {}
        bias_result = {}

    return {
        "job_id": job_id,
        "metrics_count": len(metrics_data),
        "metrics": metrics_data,
        "trends_plot": trends_result.get("file_path"),
        "bias_reduction_plot": bias_result.get("file_path"),
        "trend_statistics": trends_result.get("trend_statistics", {}),
        "bias_reduction": bias_result.get("reduction_percentage"),
    }
