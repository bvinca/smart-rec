from ai.visualization.skill_gap_visualizer import SkillGapVisualizer

def test_skill_similarity():
    visualizer = SkillGapVisualizer()
    result = visualizer.compute_skill_similarity(
        job_skills=["Python", "Docker"],
        candidate_skills=["Python", "Flask"]
    )
    assert isinstance(result, dict)
    assert "skill_matches" in result
    assert "missing_skills" in result
    assert "strong_matches" in result
    assert "weak_matches" in result
    assert "overall_alignment" in result
    assert isinstance(result["skill_matches"], dict)
    # similarity scores should land in 0-100
    for score in result["skill_matches"].values():
        assert 0 <= score <= 100
