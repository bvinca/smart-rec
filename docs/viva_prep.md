# Viva Preparation — SmartRecruiter (Bora Vinca, June 2026)

Rehearsed answers to the questions an examiner is most likely to ask. Each
answer is short on purpose; deliver the bracketed [follow-up] only if pressed.
All numbers in this file are verifiable against the committed artefact and
should be re-run on the official evaluation environment before the viva.

---

## Q1. "Your evaluation is n=3. How can you generalise?"

**Answer.** The seed corpus is n=3 and was kept primarily as a regression
fixture. Chapter 5 §5.7 reports a separate labelled benchmark of twenty-four
synthetic CVs across two job families and forty-eight (CV, job) pairs,
ranked 1–5 for suitability. On that benchmark the production scorer
achieves per-job Spearman ρ ≈ 0.67 with bootstrap 95 % CI computed over
1 000 resamples. I do not claim generalisation to real applicant pools —
the benchmark is synthetic and uses a single annotator pending rater B
labels.

[Follow-up if pressed on κ.] I deliberately do not quote inter-rater
agreement because rater B is held as `TBD` in `labels.csv`; the harness
refuses to compute κ on a single-annotator dataset rather than fabricate
agreement at κ = 1.

---

## Q2. "Does the synthetic-dataset test actually use your system?"

**Answer.** Yes. After the Day-1 fix
(`ai/tests/tier4/test_synthetic_dataset_correlation.py`), every assertion
runs against `app.services.scoring_service.ScoringService` via its public
entry point — the same class the API uses. The earlier inline `_score_candidate`
re-implementation was removed.

[Follow-up.] The test now skips gracefully if the production scorer cannot
be imported in the runner's environment, rather than substituting a
stand-in.

---

## Q3. "Why 40 % / 40 % / 20 % weights?"

**Answer.** The ablation in §5.7.4 (Table 5.6) reports pooled Spearman ρ
under four configurations. The default 40/40/20 is *defensible but not
optimal* on the benchmark: skill-heavy 60/20/20 scores ρ = 0.80 (against
0.62 at the default), experience-heavy 20/60/20 collapses to ρ = 0.34, and
equal 33/33/33 matches the default. The directional finding is that
over-weighting experience harms ranking quality far more than
over-weighting skills helps it.

[Follow-up.] I did not retune the dissertation default to 60/20/20 because
re-tuning to the benchmark would conflate the *test* with the *result* — a
classic over-fitting failure mode. The default stays as documented; the
ablation discloses what the corpus implies.

---

## Q4. "Is the LLM 'hybrid' path actually evaluated?"

**Answer.** No, the quantitative claims in Chapters 5.3–5.7 are produced
with `OPENAI_API_KEY` empty and `EMBEDDING_BACKEND=sbert`, so all reported
numbers are reproducible without an API key. The hybrid LLM path is
described qualitatively only. This is a deliberate honesty choice (NFR3
in Table 3.2) — using an API-gated path would couple academic
reproducibility to a third-party service.

---

## Q5. "What about prompt injection via CV text?"

**Answer.** §5.8 reports a five-payload adversarial probe through the
production scorer (`ai/tests/security/test_prompt_injection.py`). The four
LLM-targeted payloads move `overall_score` by 0.00 because the default
scoring path does not call the LLM — the score is governed by ontology
skill matching, experience years, and education tier. The probe surfaces
a different real attack surface: declaring twenty-one fake ontology skills
inflates `overall_score` by 40 points. That is a property of any
keyword-derived signal, not specific to my implementation, and it is
documented rather than claimed solved (§5.8 final paragraph).

[Follow-up.] The mitigation direction — weighting skill matches by
evidence in context (e.g., presence inside a dated employment block) —
is in the future-work list (§6.6).

---

## Q6. "Where is the right-to-erasure endpoint?"

**Answer.** The artefact does not currently expose `DELETE
/applications/{id}` with cascading purge of the parsed `Applicant`,
uploaded file, and `ai_audit_logs` row. The privacy posture today is:
applicants only see their own applications (verified by
`test_applicant_cannot_read_another_applicants_application` in
`backend/tests/test_rbac.py`), and demographics are opt-in. For a
production deployment, an erasure endpoint and a retention policy would
be required to satisfy GDPR Article 17; this is a stated production
prerequisite, not a present claim.

---

## Q7. "Your fairness metric flags experience gaps as bias. Is that meaningful?"

**Answer.** §5.5 already discusses this. MSD/DIR/SPD measure
*statistical* disparity between groups; interpretation is the human's
job. Comparing junior and senior applicants on the same job will produce
a large MSD because experience is a legitimate scoring input. The UI
presents the group means alongside the metrics rather than auto-correcting
scores, which is the correct division of labour between a measurement
tool and a recruiter.

---

## Q8. "How do I know the backend's role-based access actually works?"

**Answer.** Sixteen API-level tests in `backend/tests/` exercise the
guarantees, including:

* `test_recruiter_cannot_read_another_recruiters_application` (403 cross-recruiter)
* `test_applicant_cannot_read_another_applicants_application` (403 cross-applicant)
* `test_applicant_cannot_create_a_job` (403 on recruiter-only route)
* `test_refresh_rotates_and_revokes_old_token` (single-use refresh)
* `test_reused_refresh_token_revokes_entire_family` (theft response)

All sixteen pass against an in-memory FastAPI `TestClient` with rate
limits disabled for tests. Backend coverage from `pytest --cov=app` is
**38 %**; the uncovered remainder is dominated by the optional LLM/RAG
service modules that the API tests do not exercise by design.

---

## Q9. "Why does the token baseline beat your AI scorer on RQ2?"

**Answer.** The honest answer is the one in §5.7.3: on this pooled
benchmark the token baseline separates the two job families cleanly
because their vocabularies barely overlap, while the production scorer's
experience and education components reward seniority symmetrically across
families and dilute the family-fit signal. *Within* a family the
production scorer is competitive (Spearman ρ ≈ 0.67 per job), and the
skill-heavy ablation (60/20/20) closes most of the pooled gap (ρ = 0.80
vs baseline 0.88, overlapping CIs). The dissertation reports this
honestly rather than reframing the question to avoid the finding.

[Follow-up on why I did not retune.] See Q3.

---

## Q10. "What numbers in your dissertation are NOT reproducible on this
laptop right now?"

**Answer.** Three classes:

1. **Numbers from the n=3 seed corpus + SBERT-loaded scorer** (Table 5.1
   in §5.3). These require `sentence-transformers` installed; without it
   the scorer degrades to zero vectors with zero weight, which still
   produces deterministic heuristic scores but breaks the SBERT-specific
   sub-scores. Reproducible on the full evaluation environment.
2. **The SUS pilot (§5.6).** This is a one-off user study, not a
   re-runnable computation. Raw sheets are retained separately.
3. **The exact passed/skipped split for `pytest ai/tests`.** The
   committed suite collects 60 tests; the exact split depends on which
   optional dependencies are present. Regenerate with the command in §5.2.1.

Everything in §5.7 and §5.8 is reproducible from the committed corpus by
running `python ai/benchmark/run_benchmark.py` and
`pytest ai/tests/security`.

---

## Confidence cheat sheet for the viva

| Question class | Confidence | Where to point |
|----------------|-----------|----------------|
| "Show me the explanation panel" | High | `frontend/src/components/ScoreBreakdownChart.js` and `docs/figures/screenshots/explanation-panel.png` |
| "Show me the fairness audit" | High | `frontend/src/components/FairnessDashboard.js` and `ai/evaluation/fairness_checker.py` |
| "Show me how a score is decomposed" | High | `ai/explanation/xai_explainer.py:_compute_attributions` |
| "Where is the audit log written?" | High | `backend/app/services/ai_processor.py:_audit` |
| "How is PII redacted before the LLM?" | High | `ai/ai_utils/pii.py` + call sites in `ai/evaluation/evaluator.py`, `ai/rag/generator.py`, `ai/llm/email_generator.py` |
| "How big is a refresh-token attack window?" | Medium | `backend/app/services/auth_service.py:rotate_refresh_token` (single-use, 30-day expiry, family revoke on reuse) |
| "Can the system OCR a scanned CV?" | **Acknowledge gap** | §6.4 limitation 2; not implemented |
| "Could this make a hiring decision autonomously?" | **Defend by design** | §1.7 scope, §3.6.1 human-in-the-loop principle, `Application.hire_decision` is a human-driven field |
