# Institution claim validation - NOT credential verification.
# Checks the institution name on a CV matches a recognised university. Does
# NOT prove the candidate attended; that needs paid services (NSC, HEDD)
# which are out of scope.
# Uses ai/data/institutions.json + difflib.SequenceMatcher for fuzzy matching.
# No network calls - deterministic, same CV always same answer.
# Example: verifier.verify("MIT") -> recognized=True, matched_name=
#   "Massachusetts Institute of Technology", confidence=1.0, country="United States".
from __future__ import annotations

import json
import logging
import os
import re
import threading
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# Fuzzy threshold tuned empirically: accepts "MIT" -> full name (via alias list),
# accepts "Oxford University" / "University of Oxford" symmetry, rejects
# "Random College of Stuff". Bump if you grow the dataset.
_DEFAULT_RECOGNITION_THRESHOLD = 0.86

# stop-words stripped from the normalisation key
_STOP_TOKENS = {"the", "of", "at", "in", "and", "&"}


def _normalise(name: str) -> str:
    # lowercase, strip punctuation, drop stop-words, collapse whitespace
    if not name:
        return ""
    lowered = name.lower()
    # punctuation -> spaces (handles "St.", "Ph.D.", "U.S.")
    cleaned = re.sub(r"[^\w\s-]", " ", lowered)
    # split on whitespace or hyphen
    tokens = [t for t in re.split(r"[\s-]+", cleaned) if t and t not in _STOP_TOKENS]
    return " ".join(tokens)


class InstitutionVerifier:
    # fuzzy-match a claimed institution against the known list

    def __init__(
        self,
        institutions: List[Dict[str, Any]],
        recognition_threshold: float = _DEFAULT_RECOGNITION_THRESHOLD,
    ) -> None:
        self.recognition_threshold = recognition_threshold
        # flat index: normalised key -> canonical entry (name + aliases)
        # both map to the same canonical record
        self._index: List[Tuple[str, Dict[str, Any]]] = []
        for inst in institutions:
            name = inst.get("name", "")
            if not name:
                continue
            self._index.append((_normalise(name), inst))
            for alias in inst.get("aliases", []) or []:
                if alias:
                    self._index.append((_normalise(alias), inst))

    # verify
    def verify(self, claimed_name: str) -> Dict[str, Any]:
        # returns dict: recognized (bool), matched_name (str or None),
        # confidence (float 0-1 = SequenceMatcher ratio), country (str or None)
        if not claimed_name or not claimed_name.strip():
            return self._empty_result()

        query = _normalise(claimed_name)
        if not query:
            return self._empty_result()

        # scan canonical + alias index for the best match
        best_ratio = 0.0
        best_entry: Optional[Dict[str, Any]] = None
        for key, entry in self._index:
            ratio = SequenceMatcher(None, query, key).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_entry = entry
                if ratio == 1.0:
                    break  # short-circuit on perfect match

        if best_entry is None:
            return self._empty_result()

        recognised = best_ratio >= self.recognition_threshold
        return {
            "recognized": recognised,
            "matched_name": best_entry["name"] if recognised else None,
            "confidence": round(best_ratio, 3),
            "country": best_entry.get("country") if recognised else None,
        }

    # helpers
    @staticmethod
    def _empty_result() -> Dict[str, Any]:
        return {
            "recognized": False,
            "matched_name": None,
            "confidence": 0.0,
            "country": None,
        }


# loader

_VERIFIER: Optional[InstitutionVerifier] = None
_VERIFIER_LOCK = threading.Lock()


def _default_dataset_path() -> str:
    # bundled institutions.json next to the package
    return os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data",
        "institutions.json",
    )


def get_verifier() -> InstitutionVerifier:
    # process-wide singleton. If the dataset can't load, returns an empty
    # verifier (everything = unrecognised) so the caller never has to deal with None.
    global _VERIFIER
    if _VERIFIER is not None:
        return _VERIFIER
    with _VERIFIER_LOCK:
        if _VERIFIER is not None:
            return _VERIFIER
        path = _default_dataset_path()
        try:
            with open(path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            institutions = payload.get("institutions", []) if isinstance(payload, dict) else []
            _VERIFIER = InstitutionVerifier(institutions)
            logger.info(
                "InstitutionVerifier loaded: %d entries from %s.",
                len(institutions),
                path,
            )
        except Exception:  # pragma: no cover - defensive
            logger.exception("Failed to load institutions dataset at %s.", path)
            _VERIFIER = InstitutionVerifier(institutions=[])
        return _VERIFIER
