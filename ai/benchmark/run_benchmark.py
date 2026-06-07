# Benchmark runner - 24 CVs, 2 jobs, real ScoringService + token-overlap baseline.
# Metrics: Spearman rho (1000-boot CI), NDCG@5, skill F1, experience MAE,
# Cohen weighted kappa (when rater B is filled), weight ablation.
# Outputs: results.json, results.md, scatter.png. Run: python ai/benchmark/run_benchmark.py
# Hand-rolled stats - numpy + matplotlib only, no scipy/sklearn/pandas.
from __future__ import annotations

import csv
import json
import math
import os
import random
import sys
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# path setup so the production scorer is importable from wherever this runs

HERE = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, "backend")
for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)

CVS_PATH = os.path.join(HERE, "cvs.json")
JOBS_PATH = os.path.join(HERE, "jobs.json")
LABELS_PATH = os.path.join(HERE, "labels.csv")
RESULTS_JSON = os.path.join(HERE, "results.json")
RESULTS_MD = os.path.join(HERE, "results.md")
SCATTER_PNG = os.path.join(HERE, "scatter.png")

RNG = random.Random(20260525)

# weight configs for the ablation. semantic_similarity_weight stays 0 so the
# result is SBERT-independent and reproducible without sentence-transformers.
ABLATION_CONFIGS: Dict[str, Dict[str, float]] = {
    "dissertation (40/40/20)": {
        "skill_weight": 0.40,
        "experience_weight": 0.40,
        "education_weight": 0.20,
        "semantic_similarity_weight": 0.0,
    },
    "skill-heavy (60/20/20)": {
        "skill_weight": 0.60,
        "experience_weight": 0.20,
        "education_weight": 0.20,
        "semantic_similarity_weight": 0.0,
    },
    "experience-heavy (20/60/20)": {
        "skill_weight": 0.20,
        "experience_weight": 0.60,
        "education_weight": 0.20,
        "semantic_similarity_weight": 0.0,
    },
    "equal (33/33/33)": {
        "skill_weight": 1.0 / 3,
        "experience_weight": 1.0 / 3,
        "education_weight": 1.0 / 3,
        "semantic_similarity_weight": 0.0,
    },
}

PRIMARY_CONFIG = "dissertation (40/40/20)"


# stats helpers - no scipy dependency


def _rankdata(values: List[float]) -> List[float]:
    # fractional ranks with ties averaged (matches scipy.stats.rankdata)
    indexed = sorted(enumerate(values), key=lambda iv: iv[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while j + 1 < len(indexed) and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0  # ranks are 1-based, average of tied positions
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg_rank
        i = j + 1
    return ranks


def spearman_rho(xs: List[float], ys: List[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return float("nan")
    rx = _rankdata(xs)
    ry = _rankdata(ys)
    return pearson_r(rx, ry)


def pearson_r(xs: List[float], ys: List[float]) -> float:
    n = len(xs)
    if n < 2:
        return float("nan")
    mx = sum(xs) / n
    my = sum(ys) / n
    sx2 = sum((x - mx) ** 2 for x in xs)
    sy2 = sum((y - my) ** 2 for y in ys)
    if sx2 == 0 or sy2 == 0:
        return float("nan")
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return cov / math.sqrt(sx2 * sy2)


def bootstrap_spearman_ci(
    xs: List[float],
    ys: List[float],
    n_boot: int = 1000,
    alpha: float = 0.05,
) -> Tuple[float, float]:
    # 1000-resample percentile CI for Spearman rho
    n = len(xs)
    if n < 4:
        return (float("nan"), float("nan"))
    rhos: List[float] = []
    for _ in range(n_boot):
        idx = [RNG.randrange(n) for _ in range(n)]
        bx = [xs[i] for i in idx]
        by = [ys[i] for i in idx]
        rho = spearman_rho(bx, by)
        if not math.isnan(rho):
            rhos.append(rho)
    if not rhos:
        return (float("nan"), float("nan"))
    rhos.sort()
    lo = rhos[int(alpha / 2 * len(rhos))]
    hi = rhos[int((1 - alpha / 2) * len(rhos)) - 1]
    return (round(lo, 4), round(hi, 4))


def ndcg_at_k(relevances: List[float], k: int) -> float:
    # NDCG@k with the standard 2^rel - 1 gain. relevances are in system order.
    def dcg(rels: List[float]) -> float:
        return sum((2 ** r - 1) / math.log2(i + 2) for i, r in enumerate(rels[:k]))
    actual = dcg(relevances)
    ideal = dcg(sorted(relevances, reverse=True))
    if ideal == 0:
        return float("nan")
    return actual / ideal


def cohen_weighted_kappa(a: List[int], b: List[int], n_categories: int = 5) -> float:
    # Cohen's kappa with quadratic weights for ordinal ratings 1..n_categories
    if len(a) != len(b) or len(a) == 0:
        return float("nan")
    weights = np.array(
        [[((i - j) ** 2) / ((n_categories - 1) ** 2) for j in range(n_categories)]
         for i in range(n_categories)]
    )
    confusion = np.zeros((n_categories, n_categories))
    for ai, bi in zip(a, b):
        confusion[ai - 1, bi - 1] += 1
    if confusion.sum() == 0:
        return float("nan")
    confusion /= confusion.sum()
    expected = np.outer(confusion.sum(axis=1), confusion.sum(axis=0))
    num = (weights * confusion).sum()
    den = (weights * expected).sum()
    if den == 0:
        return float("nan")
    return float(1.0 - num / den)


def bootstrap_kappa_ci(
    a: List[int],
    b: List[int],
    n_boot: int = 1000,
    alpha: float = 0.05,
    n_categories: int = 5,
) -> Tuple[float, float]:
    # Percentile bootstrap CI on quadratically-weighted kappa.
    # n=48 gives a wide CI - that's honest, not a bug
    n = len(a)
    if n < 4:
        return (float("nan"), float("nan"))
    kappas: List[float] = []
    for _ in range(n_boot):
        idx = [RNG.randrange(n) for _ in range(n)]
        ba = [a[i] for i in idx]
        bb = [b[i] for i in idx]
        k = cohen_weighted_kappa(ba, bb, n_categories=n_categories)
        if not math.isnan(k):
            kappas.append(k)
    if not kappas:
        return (float("nan"), float("nan"))
    kappas.sort()
    lo = kappas[int(alpha / 2 * len(kappas))]
    hi = kappas[int((1 - alpha / 2) * len(kappas)) - 1]
    return (round(lo, 4), round(hi, 4))


def exact_agreement(a: List[int], b: List[int]) -> float:
    # fraction of pairs where A == B
    if not a:
        return float("nan")
    return sum(1 for x, y in zip(a, b) if x == y) / len(a)


def adjacent_agreement(a: List[int], b: List[int], tolerance: int = 1) -> float:
    # fraction of pairs where |A - B| <= 1. Reported alongside κ because κ
    # alone is hard to read intuitively (Cicchetti & Sparrow, 1981).
    if not a:
        return float("nan")
    return sum(1 for x, y in zip(a, b) if abs(x - y) <= tolerance) / len(a)


def kappa_landis_koch_band(kappa: float) -> str:
    # Landis & Koch (1977) interpretation band
    if math.isnan(kappa):
        return "n/a"
    if kappa < 0.0:
        return "less than chance"
    if kappa < 0.20:
        return "slight"
    if kappa < 0.40:
        return "fair"
    if kappa < 0.60:
        return "moderate"
    if kappa < 0.80:
        return "substantial"
    return "almost perfect"


# token-overlap baseline - RQ2 comparator (Section 5.4)


def token_baseline_score(
    cv: Dict[str, Any],
    job: Dict[str, Any],
) -> float:
    # Jaccard-ish overlap of length>3 tokens
    job_text = ((job.get("description") or "") + " " + (job.get("requirements") or "")).lower()
    job_tokens = {t for t in _tokenise(job_text) if len(t) > 3}
    if not job_tokens:
        return 0.0
    cv_skill_tokens = {s.lower() for s in cv.get("true_skills", [])}
    cv_text = (cv.get("resume_text") or "").lower()
    cv_tokens = cv_skill_tokens | {t for t in _tokenise(cv_text) if len(t) > 3}
    overlap = job_tokens & cv_tokens
    return min(100.0, len(overlap) / len(job_tokens) * 100.0)


def _tokenise(text: str) -> List[str]:
    import re
    return re.findall(r"[a-z][a-z0-9+#./-]{2,}", text or "")


# Parsing metrics: skill F1 + experience MAE


def parsing_metrics(cvs: List[Dict[str, Any]]) -> Dict[str, Any]:
    # run each CV through the real ResumeParser, score against true_skills / true_yrs
    try:
        from ai.nlp import ResumeParser
    except Exception as exc:
        return {"error": f"ResumeParser unavailable: {exc}", "skill_macro_f1": None, "experience_mae": None}

    parser = ResumeParser()
    per_cv: List[Dict[str, Any]] = []
    f1s: List[float] = []
    abs_errors: List[float] = []

    for cv in cvs:
        text = cv["resume_text"].encode("utf-8")
        try:
            parsed = parser.parse_file(text, filename=f"{cv['id']}.txt", use_ai=False)
        except Exception as exc:
            per_cv.append({"id": cv["id"], "error": str(exc)})
            continue
        predicted = {s.strip().lower() for s in parsed.get("skills", []) if s}
        truth = {s.strip().lower() for s in cv.get("true_skills", [])}
        if predicted or truth:
            tp = len(predicted & truth)
            fp = len(predicted - truth)
            fn = len(truth - predicted)
            precision = tp / (tp + fp) if (tp + fp) else 0.0
            recall = tp / (tp + fn) if (tp + fn) else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        else:
            precision = recall = f1 = float("nan")
        predicted_yrs = float(parsed.get("experience_years") or 0.0)
        true_yrs = float(cv.get("true_yrs") or 0.0)
        abs_err = abs(predicted_yrs - true_yrs)
        per_cv.append({
            "id": cv["id"],
            "predicted_skills_n": len(predicted),
            "true_skills_n": len(truth),
            "precision": round(precision, 3) if not math.isnan(precision) else None,
            "recall": round(recall, 3) if not math.isnan(recall) else None,
            "f1": round(f1, 3) if not math.isnan(f1) else None,
            "predicted_yrs": round(predicted_yrs, 2),
            "true_yrs": round(true_yrs, 2),
            "yrs_abs_error": round(abs_err, 2),
        })
        if not math.isnan(f1):
            f1s.append(f1)
        abs_errors.append(abs_err)

    return {
        "skill_macro_f1": round(sum(f1s) / len(f1s), 3) if f1s else None,
        "experience_mae": round(sum(abs_errors) / len(abs_errors), 2) if abs_errors else None,
        "per_cv": per_cv,
    }


# scoring loop - real ScoringService on every (CV, job) pair


def score_all_pairs(
    cvs: List[Dict[str, Any]],
    jobs: List[Dict[str, Any]],
    weights: Optional[Dict[str, float]] = None,
) -> Dict[Tuple[str, str], float]:
    # if `weights` is given, monkey-patch DEFAULT_WEIGHTS for the duration
    # of the run so the production scorer uses our ablation config. Restored on exit.
    from app.services import scoring_service as ss_module
    from app.services.scoring_service import ScoringService

    original = dict(ss_module.DEFAULT_WEIGHTS)
    if weights is not None:
        ss_module.DEFAULT_WEIGHTS = dict(weights)
    try:
        svc = ScoringService(db=None)
        scores: Dict[Tuple[str, str], float] = {}
        for cv in cvs:
            for job in jobs:
                result = svc.calculate_scores(
                    resume_text=cv["resume_text"],
                    job_description=job["description"],
                    job_requirements=job.get("requirements", ""),
                    applicant_skills=cv.get("true_skills", []),
                    applicant_experience_years=cv.get("true_yrs", 0.0),
                    applicant_education=[],
                    applicant_work_experience=[],
                    recruiter_id=None,
                    job_id=None,
                    use_adaptive_weights=False,
                )
                scores[(cv["id"], job["id"])] = float(result["overall_score"])
        return scores
    finally:
        ss_module.DEFAULT_WEIGHTS = original


# label loading + κ

def load_labels(path: str) -> Tuple[Dict[Tuple[str, str], int], Dict[Tuple[str, str], Optional[int]]]:
    rater_a: Dict[Tuple[str, str], int] = {}
    rater_b: Dict[Tuple[str, str], Optional[int]] = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(line for line in f if not line.lstrip().startswith("#"))
        for row in reader:
            key = (row["cv_id"].strip(), row["job_id"].strip())
            rater_a[key] = int(row["rater_A_rank"])
            b_raw = (row.get("rater_B_rank") or "").strip()
            rater_b[key] = int(b_raw) if b_raw and b_raw.upper() != "TBD" else None
    return rater_a, rater_b


def inter_rater_stats(
    rater_a: Dict[Tuple[str, str], int],
    rater_b: Dict[Tuple[str, str], Optional[int]],
) -> Dict[str, Any]:
    # Full agreement panel. If rater B isn't complete, returns a clear note
    # rather than fabricating a number - stops me quoting half-finished kappa
    # quote a half-finished kappa in the dissertation.
    # When both raters are in, returns: weighted kappa + 95% CI (1000 boots),
    # exact + adjacent agreement, Spearman between raters, Landis & Koch band.
    pairs_with_both = [(rater_a[k], rater_b[k]) for k in rater_a if rater_b.get(k) is not None]
    if len(pairs_with_both) < len(rater_a):
        return {
            "weighted_kappa": None,
            "note": (
                f"rater_B has values for {len(pairs_with_both)}/{len(rater_a)} pairs; "
                "skipping inter-rater agreement. Fill rater_B_rank in labels.csv with a "
                "real second annotator before quoting kappa in the dissertation."
            ),
        }
    a_list = [int(a) for a, _ in pairs_with_both]
    b_list = [int(b) for _, b in pairs_with_both]
    kappa = cohen_weighted_kappa(a_list, b_list)
    ci_lo, ci_hi = bootstrap_kappa_ci(a_list, b_list)
    return {
        "n": len(pairs_with_both),
        "weighted_kappa": round(kappa, 3),
        "weighted_kappa_ci_lo": ci_lo,
        "weighted_kappa_ci_hi": ci_hi,
        "exact_agreement": round(exact_agreement(a_list, b_list), 3),
        "adjacent_agreement": round(adjacent_agreement(a_list, b_list), 3),
        "spearman_between_raters": round(spearman_rho(a_list, b_list), 3),
        "landis_koch_band": kappa_landis_koch_band(kappa),
    }


# back-compat alias - delete once nothing imports it
kappa_or_skip = inter_rater_stats


# reporting

def compute_per_job_metrics(
    jobs: List[Dict[str, Any]],
    cvs: List[Dict[str, Any]],
    scores: Dict[Tuple[str, str], float],
    human_means: Dict[Tuple[str, str], float],
) -> Dict[str, Dict[str, float]]:
    per_job: Dict[str, Dict[str, float]] = {}
    for job in jobs:
        keys = [(cv["id"], job["id"]) for cv in cvs]
        ai = [scores[k] for k in keys]
        human = [human_means[k] for k in keys]
        rho = spearman_rho(ai, human)
        lo, hi = bootstrap_spearman_ci(ai, human)
        ranked = sorted(zip(ai, human), key=lambda p: -p[0])
        ndcg5 = ndcg_at_k([h for _, h in ranked], k=5)
        per_job[job["id"]] = {
            "spearman_rho": round(rho, 4),
            "spearman_ci_lo": lo,
            "spearman_ci_hi": hi,
            "ndcg_at_5": round(ndcg5, 4) if not math.isnan(ndcg5) else None,
            "n": len(keys),
        }
    return per_job


def scatter_plot(
    cvs: List[Dict[str, Any]],
    jobs: List[Dict[str, Any]],
    scores: Dict[Tuple[str, str], float],
    human_means: Dict[Tuple[str, str], float],
    out_path: str,
) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        print("matplotlib unavailable; skipping scatter plot")
        return

    family_color = {"backend-python": "#1f77b4", "data-analyst": "#d62728"}
    cv_family = {cv["id"]: cv["family"] for cv in cvs}

    fig, ax = plt.subplots(figsize=(7, 5))
    for job in jobs:
        for cv in cvs:
            key = (cv["id"], job["id"])
            ax.scatter(
                scores[key], human_means[key],
                c=family_color.get(cv_family[cv["id"]], "gray"),
                alpha=0.7, edgecolor="black", linewidth=0.4, s=42,
            )
    ai_all = [scores[(cv["id"], job["id"])] for job in jobs for cv in cvs]
    hu_all = [human_means[(cv["id"], job["id"])] for job in jobs for cv in cvs]
    rho = spearman_rho(ai_all, hu_all)

    # least-squares regression line through the scatter
    xs = np.array(ai_all)
    ys = np.array(hu_all)
    if len(xs) > 1 and xs.std() > 0:
        slope, intercept = np.polyfit(xs, ys, 1)
        xline = np.linspace(xs.min(), xs.max(), 50)
        ax.plot(xline, slope * xline + intercept, "k--", alpha=0.5, linewidth=1.2)

    ax.set_xlabel("AI overall_score (production ScoringService, 40/40/20)")
    ax.set_ylabel("Mean human suitability rank (1-5)")
    ax.set_title(f"SmartRecruiter benchmark — Spearman rho = {rho:.3f}, n={len(ai_all)}")
    ax.set_ylim(0.5, 5.5)
    handles = [
        plt.Line2D([0], [0], marker="o", color="w", label="backend-python pairs",
                   markerfacecolor=family_color["backend-python"], markeredgecolor="black", markersize=8),
        plt.Line2D([0], [0], marker="o", color="w", label="data-analyst pairs",
                   markerfacecolor=family_color["data-analyst"], markeredgecolor="black", markersize=8),
    ]
    ax.legend(handles=handles, loc="lower right")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def interrater_confusion_plot(
    rater_a: Dict[Tuple[str, str], int],
    rater_b: Dict[Tuple[str, str], Optional[int]],
    out_path: str,
    n_categories: int = 5,
) -> bool:
    # 5x5 rater-A x rater-B confusion heatmap.
    # Returns False if there's nothing to render (rater B incomplete or no matplotlib).
    pairs = [(rater_a[k], rater_b[k]) for k in rater_a if rater_b.get(k) is not None]
    if len(pairs) < len(rater_a):
        return False
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return False

    matrix = np.zeros((n_categories, n_categories), dtype=int)
    for a, b in pairs:
        matrix[int(a) - 1, int(b) - 1] += 1

    fig, ax = plt.subplots(figsize=(5.2, 4.6))
    im = ax.imshow(matrix, cmap="Blues", aspect="equal")
    ax.set_xticks(range(n_categories))
    ax.set_yticks(range(n_categories))
    ax.set_xticklabels([str(i + 1) for i in range(n_categories)])
    ax.set_yticklabels([str(i + 1) for i in range(n_categories)])
    ax.set_xlabel("Rater B rating (1-5)")
    ax.set_ylabel("Rater A rating (1-5)")
    ax.set_title(f"Inter-rater confusion matrix (n={len(pairs)} pairs)")
    # cell counts - white text on dark cells for readability
    max_count = matrix.max() or 1
    for i in range(n_categories):
        for j in range(n_categories):
            count = matrix[i, j]
            color = "white" if count > max_count * 0.55 else "black"
            ax.text(j, i, str(count), ha="center", va="center",
                    color=color, fontsize=11, fontweight="bold")
    # thin grid lines between cells
    ax.set_xticks(np.arange(-0.5, n_categories, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, n_categories, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.5)
    ax.tick_params(which="minor", length=0)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="pairs")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return True


def write_markdown_report(results: Dict[str, Any], out_path: str) -> None:
    lines: List[str] = []
    lines.append("# SmartRecruiter Benchmark Results\n")
    lines.append("Auto-generated by `ai/benchmark/run_benchmark.py`. Do not edit by hand.\n")
    lines.append(f"- Pairs evaluated: **{results['n_pairs']}**")
    lines.append(f"- CVs: **{results['n_cvs']}** across {results['n_families']} families")
    lines.append(f"- Jobs: **{results['n_jobs']}**")
    lines.append("")

    lines.append("## RQ1/RQ2 — Spearman rho (production vs human mean rank)\n")
    lines.append("| Job | rho | 95% CI | NDCG@5 | n |")
    lines.append("|---|---|---|---|---|")
    for job_id, m in results["per_job_production"].items():
        ci = f"[{m['spearman_ci_lo']:.3f}, {m['spearman_ci_hi']:.3f}]" if m["spearman_ci_lo"] == m["spearman_ci_lo"] else "—"
        ndcg = f"{m['ndcg_at_5']:.3f}" if m["ndcg_at_5"] is not None else "—"
        lines.append(f"| {job_id} | {m['spearman_rho']:.3f} | {ci} | {ndcg} | {m['n']} |")
    lines.append("")
    pooled = results["pooled"]
    lines.append(
        f"**Pooled (all pairs, n={pooled['n']}):** Spearman rho = "
        f"**{pooled['production_rho']:.3f}** "
        f"(95% CI [{pooled['production_ci_lo']:.3f}, {pooled['production_ci_hi']:.3f}])\n"
    )

    lines.append("## RQ2 — token-overlap baseline vs production\n")
    lines.append("| Scorer | Pooled Spearman rho | 95% CI |")
    lines.append("|---|---|---|")
    lines.append(
        f"| Production (SBERT-weighted, default) | {pooled['production_rho']:.3f} | "
        f"[{pooled['production_ci_lo']:.3f}, {pooled['production_ci_hi']:.3f}] |"
    )
    lines.append(
        f"| Token-overlap baseline                | {pooled['baseline_rho']:.3f} | "
        f"[{pooled['baseline_ci_lo']:.3f}, {pooled['baseline_ci_hi']:.3f}] |"
    )
    lines.append("")

    lines.append("## Item 4C — weight-ablation table\n")
    lines.append("| Weight configuration | Pooled Spearman rho | 95% CI |")
    lines.append("|---|---|---|")
    for name, m in results["ablation"].items():
        lines.append(
            f"| {name} | {m['rho']:.3f} | [{m['ci_lo']:.3f}, {m['ci_hi']:.3f}] |"
        )
    lines.append("")

    lines.append("## Parsing — skill F1 and experience MAE\n")
    p = results["parsing"]
    if "error" in p:
        lines.append(f"> Parsing metrics unavailable: {p['error']}")
    else:
        lines.append(f"- Macro-F1 of skill extraction (vs ground-truth `true_skills`): **{p['skill_macro_f1']}**")
        lines.append(f"- MAE of `experience_years` (vs ground-truth `true_yrs`): **{p['experience_mae']} years**")
    lines.append("")

    lines.append("## Inter-rater agreement\n")
    k = results["kappa"]
    if k.get("weighted_kappa") is None:
        lines.append(f"> {k.get('note', 'kappa unavailable')}")
    else:
        lines.append("| Metric | Value |")
        lines.append("|---|---|")
        lines.append(
            f"| Cohen's quadratically-weighted kappa | **{k['weighted_kappa']:.3f}** "
            f"(95% CI [{k['weighted_kappa_ci_lo']:.3f}, {k['weighted_kappa_ci_hi']:.3f}]) |"
        )
        lines.append(
            f"| Landis & Koch (1977) band | **{k['landis_koch_band']}** |"
        )
        lines.append(
            f"| Exact agreement (rater A == rater B) | {k['exact_agreement']*100:.1f}% |"
        )
        lines.append(
            f"| Adjacent agreement (within 1 point) | {k['adjacent_agreement']*100:.1f}% |"
        )
        lines.append(
            f"| Spearman rho between raters | {k['spearman_between_raters']:.3f} |"
        )
        lines.append(f"| Pairs scored by both raters | {k['n']} |")
        lines.append("")
        lines.append("See `interrater.png` for the rater-A × rater-B confusion matrix.")
    lines.append("")

    lines.append("## Reproduction\n")
    lines.append("```")
    lines.append("python ai/benchmark/run_benchmark.py")
    lines.append("```")
    lines.append("Outputs: `results.json`, `results.md`, `scatter.png` in this directory.")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# main

def main() -> int:
    with open(CVS_PATH, encoding="utf-8") as f:
        cvs = json.load(f)["cvs"]
    with open(JOBS_PATH, encoding="utf-8") as f:
        jobs = json.load(f)["jobs"]
    rater_a, rater_b = load_labels(LABELS_PATH)

    # mean human rank per pair - rater A only until B is filled, then average both
    human_means: Dict[Tuple[str, str], float] = {}
    for key, a in rater_a.items():
        b = rater_b.get(key)
        human_means[key] = (a + b) / 2.0 if b is not None else float(a)

    # run all four ablation configs
    ablation_results: Dict[str, Dict[str, float]] = {}
    primary_scores: Dict[Tuple[str, str], float] = {}
    for name, weights in ABLATION_CONFIGS.items():
        scores = score_all_pairs(cvs, jobs, weights=weights)
        keys = list(rater_a.keys())
        ai = [scores[k] for k in keys]
        human = [human_means[k] for k in keys]
        rho = spearman_rho(ai, human)
        lo, hi = bootstrap_spearman_ci(ai, human)
        ablation_results[name] = {"rho": round(rho, 4), "ci_lo": lo, "ci_hi": hi}
        if name == PRIMARY_CONFIG:
            primary_scores = scores

    # token baseline
    baseline_scores = {
        (cv["id"], job["id"]): token_baseline_score(cv, job)
        for job in jobs for cv in cvs
    }
    keys = list(rater_a.keys())
    base_ai = [baseline_scores[k] for k in keys]
    prod_ai = [primary_scores[k] for k in keys]
    human = [human_means[k] for k in keys]
    pooled = {
        "n": len(keys),
        "production_rho": round(spearman_rho(prod_ai, human), 4),
        "baseline_rho": round(spearman_rho(base_ai, human), 4),
    }
    pooled["production_ci_lo"], pooled["production_ci_hi"] = bootstrap_spearman_ci(prod_ai, human)
    pooled["baseline_ci_lo"], pooled["baseline_ci_hi"] = bootstrap_spearman_ci(base_ai, human)

    per_job_production = compute_per_job_metrics(jobs, cvs, primary_scores, human_means)

    parsing = parsing_metrics(cvs)
    kappa = inter_rater_stats(rater_a, rater_b)

    scatter_plot(cvs, jobs, primary_scores, human_means, SCATTER_PNG)
    interrater_path = os.path.join(HERE, "interrater.png")
    interrater_rendered = interrater_confusion_plot(rater_a, rater_b, interrater_path)

    results = {
        "n_pairs": len(keys),
        "n_cvs": len(cvs),
        "n_families": len({cv["family"] for cv in cvs}),
        "n_jobs": len(jobs),
        "weight_config_primary": PRIMARY_CONFIG,
        "per_job_production": per_job_production,
        "pooled": pooled,
        "ablation": ablation_results,
        "parsing": parsing,
        "kappa": kappa,
        "scores": {
            f"{cv_id}::{job_id}": {
                "production": round(primary_scores[(cv_id, job_id)], 2),
                "baseline": round(baseline_scores[(cv_id, job_id)], 2),
                "rater_A": rater_a[(cv_id, job_id)],
                "rater_B": rater_b.get((cv_id, job_id)),
                "mean_human": round(human_means[(cv_id, job_id)], 2),
            }
            for (cv_id, job_id) in keys
        },
    }

    with open(RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    write_markdown_report(results, RESULTS_MD)
    print(f"Wrote: {RESULTS_JSON}\nWrote: {RESULTS_MD}\nWrote: {SCATTER_PNG}")
    if interrater_rendered:
        print(f"Wrote: {interrater_path}")
    else:
        print("(Skipped interrater.png — rater B is incomplete.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
