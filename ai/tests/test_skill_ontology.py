# skill ontology unit tests
# aliases collapse, substring matches don't false-positive

from __future__ import annotations

import pytest

from ai.nlp.skill_ontology import ontology


@pytest.mark.parametrize(
    "alias,expected",
    [
        ("JS", "JavaScript"),
        ("ts", "TypeScript"),
        ("k8s", "Kubernetes"),
        ("postgres", "PostgreSQL"),
        ("py", "Python"),
        ("nodejs", "Node.js"),
        ("nlp", "Natural Language Processing"),
        ("sklearn", "scikit-learn"),
    ],
)
def test_aliases_normalise(alias, expected):
    assert ontology.normalise(alias) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        # "react" inside "reaction" should not match
        ("The reaction was strong.", []),
        # two skills, deduped
        ("Built APIs with FastAPI and used PostgreSQL alongside postgres.", ["FastAPI", "PostgreSQL"]),
        # react native wins over react (longest match first)
        ("Worked on mobile apps with React Native.", ["React Native"]),
    ],
)
def test_find_in_text(text, expected):
    assert ontology.find_in_text(text) == expected


def test_normalise_list_dedupes_and_preserves_order():
    inputs = ["JS", "JavaScript", "ts", "TS", "Python", "Python"]
    assert ontology.normalise_list(inputs) == ["JavaScript", "TypeScript", "Python"]


def test_unknown_skill_is_returned_unchanged_in_normalise_list():
    inputs = ["Python", "MyCustomFramework"]
    assert ontology.normalise_list(inputs) == ["Python", "MyCustomFramework"]
