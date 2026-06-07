# institution claim-validation tests
# checks recognised vs unknown, abbreviations, fuzzy typos (not positional in the dataset)

from __future__ import annotations

import os
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ai.nlp.institution_lookup import (  # noqa: E402
    InstitutionVerifier,
    _normalise,
    get_verifier,
)


class TestNormalisation:
    def test_lowercase_strip_punctuation(self):
        assert _normalise("Massachusetts Institute of Technology") == "massachusetts institute technology"

    def test_drops_stopwords(self):
        assert _normalise("The University of York") == "university york"

    def test_handles_punctuation(self):
        assert _normalise("King's College London.") == "king s college london"

    def test_empty_input(self):
        assert _normalise("") == ""
        assert _normalise(None) == ""  # type: ignore[arg-type]


class TestVerifierAgainstBundledDataset:
    # smoke tests against the shipped dataset

    def test_exact_canonical_name_recognised(self):
        verifier = get_verifier()
        result = verifier.verify("Massachusetts Institute of Technology")
        assert result["recognized"] is True
        assert result["matched_name"] == "Massachusetts Institute of Technology"
        assert result["confidence"] >= 0.99

    def test_abbreviation_via_alias_recognised(self):
        verifier = get_verifier()
        result = verifier.verify("MIT")
        assert result["recognized"] is True
        assert result["matched_name"] == "Massachusetts Institute of Technology"

    def test_word_order_variant_recognised(self):
        # "oxford university" should map to "university of oxford"
        verifier = get_verifier()
        result = verifier.verify("Oxford University")
        assert result["recognized"] is True
        assert result["matched_name"] == "University of Oxford"

    def test_local_campus_recognised(self):
        verifier = get_verifier()
        result = verifier.verify("CITY College")
        assert result["recognized"] is True
        assert "York Europe Campus" in result["matched_name"]

    def test_unknown_institution_not_recognised(self):
        verifier = get_verifier()
        result = verifier.verify("Definitely Not A Real University")
        assert result["recognized"] is False
        assert result["matched_name"] is None
        assert result["confidence"] < 0.86

    def test_empty_input_not_recognised(self):
        verifier = get_verifier()
        result = verifier.verify("")
        assert result["recognized"] is False
        assert result["confidence"] == 0.0

    def test_returned_country_metadata(self):
        verifier = get_verifier()
        result = verifier.verify("ETH Zurich")
        assert result["recognized"] is True
        assert result["country"] == "Switzerland"


class TestVerifierWithSyntheticDataset:
    # unit tests on a tiny hand-built dataset

    @pytest.fixture
    def verifier(self) -> InstitutionVerifier:
        dataset = [
            {"name": "Example University", "aliases": ["EU"], "country": "Examplandia"},
            {"name": "Sample Institute of Technology", "aliases": ["SIT"], "country": "Demoland"},
        ]
        return InstitutionVerifier(dataset)

    def test_alias_resolves_to_canonical(self, verifier):
        result = verifier.verify("SIT")
        assert result["recognized"] is True
        assert result["matched_name"] == "Sample Institute of Technology"
        assert result["country"] == "Demoland"

    def test_minor_typo_still_recognised(self, verifier):
        # missing trailing "e" in "institute" should still match
        result = verifier.verify("Sample Institut of Technology")
        assert result["recognized"] is True

    def test_completely_different_string_not_recognised(self, verifier):
        result = verifier.verify("Totally Unrelated College of Nonsense")
        assert result["recognized"] is False
