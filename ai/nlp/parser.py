# Resume parser - structured data from PDF / DOCX / TXT.
# Pipeline: text extract (PyMuPDF then PyPDF2 for PDFs, python-docx for Word)
# -> normalise -> spaCy NER (PERSON/ORG/GPE/DATE) if available, regex otherwise
# -> SkillExtractor pass (ontology + keyword lists).
from __future__ import annotations

import io
import re
from typing import Any, Dict, List, Optional, Tuple

import PyPDF2  # fallback when PyMuPDF isn't around

import logging

logger = logging.getLogger(__name__)

try:
    import fitz  # PyMuPDF

    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

from docx import Document

# spaCy optional - pure-regex fallback if import or model load fails
SPACY_AVAILABLE = False
_nlp = None
try:
    import spacy  # type: ignore[import]

    try:
        _nlp = spacy.load("en_core_web_sm")
        SPACY_AVAILABLE = True
        logger.info("spaCy en_core_web_sm loaded — NER enabled.")
    except OSError:
        logger.info(
            "spaCy model 'en_core_web_sm' not found. "
            "Run: python -m spacy download en_core_web_sm"
        )
except ImportError:
    logger.warning("spaCy not installed — regex-only résumé parsing active.")

from .skill_extraction import SkillExtractor
from .preprocess import TextPreprocessor

# degree keywords used by education extraction
_DEGREE_KEYWORDS = {
    "bachelor", "master", "phd", "doctorate", "degree",
    "university", "college", "b.s.", "m.s.", "b.a.", "m.a.",
    "msc", "bsc", "mba", "llb", "llm",
}

# headers that mark the start of the work-experience block
_WORK_SECTION_RE = re.compile(
    r"^\s*(work experience|experience|employment|career history|professional experience)\s*$",
    re.IGNORECASE,
)


class ResumeParser:
    # spaCy NER (if present) + regex fallback

    def __init__(self) -> None:
        self.skill_extractor = SkillExtractor()
        self.preprocessor = TextPreprocessor()

    # public API

    def parse_file(
        self, file_content: bytes, filename: str, use_ai: bool = False
    ) -> Dict[str, Any]:
        # Returns dict: first_name, last_name, email, phone, experience_years,
        # education, work_experience, skills, technical_skills, soft_skills,
        # entities, resume_text, timeline_check.
        # use_ai is dead - summarisation moved elsewhere
        ext = filename.rsplit(".", 1)[-1].lower()

        if ext == "pdf":
            raw_text = self._extract_from_pdf(file_content)
        elif ext in {"doc", "docx"}:
            raw_text = self._extract_from_docx(file_content)
        elif ext == "txt":
            raw_text = file_content.decode("utf-8", errors="replace")
        else:
            raise ValueError(f"Unsupported file type: {ext}")

        normalized = self.preprocessor.normalize_text(raw_text)

        # run spaCy once so every downstream extractor can read from the same Doc
        spacy_doc = None
        if SPACY_AVAILABLE and _nlp:
            try:
                spacy_doc = _nlp(raw_text[:8000])
            except Exception:
                logger.exception("spaCy NER pass failed; falling back to regex.")

        parsed = self._parse_text(normalized, raw_text, spacy_doc)

        parsed["skills"] = self.skill_extractor.extract_skills(normalized)
        parsed["technical_skills"] = self.skill_extractor.extract_technical_skills(normalized)
        parsed["soft_skills"] = self.skill_extractor.extract_soft_skills(normalized)

        return parsed

    # text extraction

    def _extract_from_pdf(self, file_content: bytes) -> str:
        if PYMUPDF_AVAILABLE:
            try:
                doc = fitz.open(stream=file_content, filetype="pdf")
                pages = [page.get_text() for page in doc]
                doc.close()
                return "\n".join(pages)
            except Exception:
                logger.exception("PyMuPDF extraction failed; falling back to PyPDF2.")

        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
        return "\n".join(
            (page.extract_text() or "") for page in pdf_reader.pages
        )

    def _extract_from_docx(self, file_content: bytes) -> str:
        doc = Document(io.BytesIO(file_content))
        return "\n".join(p.text for p in doc.paragraphs)

    # core parsing

    def _parse_text(
        self,
        normalized_text: str,
        original_text: str,
        spacy_doc=None,
    ) -> Dict[str, Any]:
        email = self.preprocessor.extract_email(original_text)
        phone = self.preprocessor.extract_phone(original_text)

        # build the entity map once from the precomputed Doc
        entities = self._entities_from_doc(spacy_doc) if spacy_doc else {}

        first_name, last_name = self._extract_name(original_text, spacy_doc)
        experience_years = self._extract_experience_years(normalized_text)
        education = self._extract_education(original_text, entities)
        work_experience = self._extract_work_experience(original_text, entities)

        parsed = {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": phone,
            "experience_years": experience_years,
            "education": education,
            "work_experience": work_experience,
            "resume_text": normalized_text,
            "entities": entities,
        }

        # timeline sanity check - future dates, overlaps, inflated experience. Must not crash parse.
        try:
            from ai.nlp.timeline_validator import validate_timeline
            parsed["timeline_check"] = validate_timeline(parsed)
        except Exception:  # pragma: no cover - defensive
            parsed["timeline_check"] = {"warnings": []}

        return parsed

    # spaCy NER

    def _entities_from_doc(self, doc) -> Dict[str, List[str]]:
        # deduplicated entity map from a spaCy Doc
        entities: Dict[str, List[str]] = {
            "PERSON": [], "ORG": [], "GPE": [], "DATE": [], "EDUCATION": [],
        }
        for ent in doc.ents:
            if ent.label_ in entities:
                text = ent.text.strip()
                if text and text not in entities[ent.label_]:
                    entities[ent.label_].append(text)

        # tag any sentence that mentions an education keyword
        edu_kw = _DEGREE_KEYWORDS
        for sent in doc.sents:
            lower = sent.text.lower()
            if any(kw in lower for kw in edu_kw):
                snippet = sent.text.strip()
                if snippet not in entities["EDUCATION"]:
                    entities["EDUCATION"].append(snippet)

        return entities

    # name

    def _extract_name(
        self, original_text: str, spacy_doc=None
    ) -> Tuple[str, str]:
        # spaCy PERSON first, else first non-empty line
        if spacy_doc is not None:
            # the name basically always appears in the first 500 chars
            for ent in spacy_doc.ents:
                if ent.label_ == "PERSON" and ent.start_char < 500:
                    parts = ent.text.strip().split()
                    if parts:
                        return parts[0], " ".join(parts[1:])

        # regex / first-line fallback
        lines = [ln.strip() for ln in original_text.split("\n") if ln.strip()]
        name = lines[0] if lines else ""
        name = re.sub(
            r"^(resume|cv|curriculum vitae)[:\s]*", "", name, flags=re.IGNORECASE
        ).strip()
        parts = name.split()
        return (parts[0] if parts else ""), (" ".join(parts[1:]) if len(parts) > 1 else "")

    # education

    def _extract_education(
        self, original_text: str, entities: Dict[str, List[str]]
    ) -> List[Dict[str, Any]]:
        # each entry gets institution_check - name matches known uni, not credential proof
        education: List[Dict[str, Any]] = []
        org_names = set(entities.get("ORG", []))

        # lazy import - parse still works without institutions dataset
        try:
            from ai.nlp.institution_lookup import get_verifier
            verifier = get_verifier()
        except Exception:  # pragma: no cover - defensive
            verifier = None

        for line in original_text.split("\n"):
            lower = line.lower()
            if not any(kw in lower for kw in _DEGREE_KEYWORDS):
                continue

            parts = re.split(r"[-–—]|,\s*", line, maxsplit=2)
            degree = parts[0].strip()
            institution = parts[1].strip() if len(parts) >= 2 else ""

            # no institution from regex - try spaCy ORG match
            if not institution:
                for org in org_names:
                    if org.lower() in lower:
                        institution = org
                        break

            entry: Dict[str, Any] = {
                "degree": degree,
                "institution": institution,
                "year": self.preprocessor.extract_year(line),
            }

            # institution_check - shown in recruiter UI next to the entry
            if verifier is not None and institution:
                entry["institution_check"] = verifier.verify(institution)
            else:
                entry["institution_check"] = {
                    "recognized": False,
                    "matched_name": None,
                    "confidence": 0.0,
                    "country": None,
                }

            if entry not in education:
                education.append(entry)

        return education[:5]

    # work experience

    def _extract_work_experience(
        self, original_text: str, entities: Dict[str, List[str]]
    ) -> List[Dict[str, Any]]:
        # Look for "Title - Company" / "Title | Company" / "Title at Company"
        # patterns. When the company half is fuzzy, cross-check against spaCy ORGs.
        experience: List[Dict[str, Any]] = []
        org_names = set(entities.get("ORG", []))
        lines = original_text.split("\n")

        for i, line in enumerate(lines):
            if not (" - " in line or " | " in line or re.search(r"\bat\b", line, re.IGNORECASE)):
                continue
            # ignore lines that are just section headers ("Experience" etc.)
            if _WORK_SECTION_RE.match(line):
                continue

            parts = re.split(r"\s+-\s+|\s+\|\s+|\s+at\s+", line, flags=re.IGNORECASE)
            if len(parts) < 2:
                continue

            title = parts[0].strip()
            company = parts[1].strip()

            # vague company split - try spaCy ORG match
            if company and not any(company.lower() in o.lower() or o.lower() in company.lower() for o in org_names):
                for org in org_names:
                    if org.lower() in line.lower():
                        company = org
                        break

            desc_lines: List[str] = []
            for j in range(i + 1, min(i + 5, len(lines))):
                next_line = lines[j].strip()
                if next_line and not re.match(r"^\d{4}", next_line):
                    desc_lines.append(next_line)

            experience.append({
                "title": title,
                "company": company,
                "duration": self.preprocessor.extract_duration(line),
                "description": " ".join(desc_lines),
            })

        return experience[:5]

    # experience years

    def _extract_experience_years(self, text: str) -> float:
        # prefer an explicit "N years of experience" string, else estimate from role count
        patterns = [
            r"(\d+)\+?\s*(?:years?|yrs?|yoe|years?\s+of\s+experience)",
            r"(?:experience|exp)[:\s]+(\d+)\+?",
            r"(\d+)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:professional|work|industry)",
        ]
        for pattern in patterns:
            for match in re.findall(pattern, text, flags=re.IGNORECASE):
                try:
                    return float(match)
                except ValueError:
                    continue

        # rough fallback - ~1.5 years per detected role
        work_exp = self._extract_work_experience(text, {})
        return float(len(work_exp)) * 1.5 if work_exp else 0.0

