# Skill ontology - canonical names + aliases.
# JS, node, k8s -> JavaScript, Node.js, Kubernetes. Parser and scorer both use this.
# Each entry: aliases, category (10 groups), weight (default 1.0).
# Fairness audit flags skills with inflated weights as a bias risk.
# 101 skills across 10 categories. Same API could swap in ESCO/O*NET later.

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class SkillEntry:
    canonical: str
    aliases: FrozenSet[str]
    category: str = "general"
    weight: float = 1.0


def _entry(canonical: str, aliases: Iterable[str], category: str = "general", weight: float = 1.0) -> SkillEntry:
    alias_set = frozenset({canonical.lower(), *(a.lower() for a in aliases)})
    return SkillEntry(canonical=canonical, aliases=alias_set, category=category, weight=weight)


# static ontology data
_SKILLS: Tuple[SkillEntry, ...] = (
    # programming languages
    _entry("Python", ["py", "python3"], "language"),
    _entry("Java", ["java se", "java ee"], "language"),
    _entry("JavaScript", ["js", "ecmascript", "vanilla js"], "language"),
    _entry("TypeScript", ["ts"], "language"),
    _entry("C++", ["cpp", "c plus plus"], "language"),
    _entry("C#", ["csharp", "c sharp"], "language"),
    _entry("Go", ["golang"], "language"),
    _entry("Rust", [], "language"),
    _entry("Kotlin", [], "language"),
    _entry("Swift", [], "language"),
    _entry("PHP", [], "language"),
    _entry("Ruby", [], "language"),
    _entry("Scala", [], "language"),
    _entry("R", ["r language"], "language"),
    _entry("MATLAB", ["matlab"], "language"),
    _entry("SQL", ["t-sql", "pl/sql", "ansi sql"], "language"),
    _entry("Bash", ["shell", "shell scripting", "bash scripting"], "language"),
    _entry("PowerShell", ["pwsh"], "language"),
    # web frontend
    _entry("React", ["react.js", "reactjs"], "frontend"),
    _entry("Next.js", ["next", "nextjs"], "frontend"),
    _entry("Vue.js", ["vue", "vuejs", "vue 3"], "frontend"),
    _entry("Angular", ["angularjs", "angular 2+"], "frontend"),
    _entry("Svelte", ["sveltekit"], "frontend"),
    _entry("HTML", ["html5"], "frontend"),
    _entry("CSS", ["css3"], "frontend"),
    _entry("Tailwind CSS", ["tailwind", "tailwindcss"], "frontend"),
    _entry("Bootstrap", [], "frontend"),
    _entry("Redux", ["redux toolkit"], "frontend"),
    _entry("GraphQL", ["graph ql"], "frontend"),
    # backend frameworks
    _entry("FastAPI", ["fast api"], "backend"),
    _entry("Django", ["django rest framework", "drf"], "backend"),
    _entry("Flask", [], "backend"),
    _entry("Node.js", ["node", "nodejs"], "backend"),
    _entry("Express.js", ["express", "expressjs"], "backend"),
    _entry("Spring Boot", ["spring", "springboot"], "backend"),
    _entry("ASP.NET", ["asp.net core", "dotnet"], "backend"),
    _entry("Ruby on Rails", ["rails"], "backend"),
    _entry("REST API", ["rest", "restful api"], "backend"),
    _entry("gRPC", [], "backend"),
    # databases
    _entry("PostgreSQL", ["postgres", "psql", "pg"], "database"),
    _entry("MySQL", ["maria db", "mariadb"], "database"),
    _entry("SQLite", [], "database"),
    _entry("MongoDB", ["mongo"], "database"),
    _entry("Redis", [], "database"),
    _entry("Elasticsearch", ["elastic search"], "database"),
    _entry("DynamoDB", [], "database"),
    _entry("Cassandra", [], "database"),
    _entry("Neo4j", [], "database"),
    _entry("Snowflake", [], "database"),
    # cloud
    _entry("AWS", ["amazon web services"], "cloud"),
    _entry("Azure", ["microsoft azure"], "cloud"),
    _entry("GCP", ["google cloud", "google cloud platform"], "cloud"),
    _entry("Kubernetes", ["k8s"], "cloud"),
    _entry("Docker", ["containerization"], "cloud"),
    _entry("Terraform", ["iac"], "cloud"),
    _entry("Ansible", [], "cloud"),
    _entry("Helm", [], "cloud"),
    _entry("Linux", ["unix"], "cloud"),
    # CI / devops
    _entry("Git", ["github", "gitlab"], "devops"),
    _entry("GitHub Actions", ["gh actions"], "devops"),
    _entry("GitLab CI", ["gitlab pipelines"], "devops"),
    _entry("Jenkins", [], "devops"),
    _entry("CircleCI", [], "devops"),
    _entry("CI/CD", ["continuous integration", "continuous delivery"], "devops"),
    _entry("Microservices", ["micro services"], "devops"),
    _entry("Agile", ["scrum", "kanban"], "process"),
    # ML / data science
    _entry("Machine Learning", ["ml", "machine-learning"], "ml", weight=1.2),
    _entry("Deep Learning", ["dl", "deep-learning"], "ml", weight=1.2),
    _entry("Natural Language Processing", ["nlp"], "ml", weight=1.2),
    _entry("Computer Vision", ["cv", "image processing"], "ml"),
    _entry("TensorFlow", ["tf"], "ml"),
    _entry("PyTorch", ["torch"], "ml"),
    _entry("Keras", [], "ml"),
    _entry("scikit-learn", ["sklearn", "scikit learn"], "ml"),
    _entry("Pandas", [], "ml"),
    _entry("NumPy", [], "ml"),
    _entry("spaCy", [], "ml"),
    _entry("NLTK", [], "ml"),
    _entry("Hugging Face", ["huggingface", "transformers"], "ml"),
    _entry("LangChain", [], "ml"),
    _entry("LLM", ["large language model", "gpt", "openai"], "ml"),
    _entry("RAG", ["retrieval augmented generation"], "ml"),
    _entry("Sentence-BERT", ["sbert", "sentence bert"], "ml"),
    # data / BI
    _entry("Apache Spark", ["spark", "pyspark"], "data"),
    _entry("Hadoop", [], "data"),
    _entry("Airflow", [], "data"),
    _entry("dbt", [], "data"),
    _entry("Tableau", [], "data"),
    _entry("Power BI", ["powerbi"], "data"),
    # mobile
    _entry("Android", [], "mobile"),
    _entry("iOS", [], "mobile"),
    _entry("React Native", ["reactnative"], "mobile"),
    _entry("Flutter", [], "mobile"),
    # soft skills (lighter weight)
    _entry("Communication", ["communication skills"], "soft", weight=0.6),
    _entry("Leadership", ["team leadership"], "soft", weight=0.6),
    _entry("Teamwork", ["team work", "collaboration"], "soft", weight=0.6),
    _entry("Problem Solving", ["problem-solving"], "soft", weight=0.6),
    _entry("Critical Thinking", ["critical-thinking"], "soft", weight=0.6),
    _entry("Time Management", ["time-management"], "soft", weight=0.6),
    _entry("Project Management", ["pm"], "soft", weight=0.7),
    _entry("Mentoring", ["coaching"], "soft", weight=0.6),
)


_TECHNICAL_CATEGORIES = {
    "language", "frontend", "backend", "database", "cloud",
    "devops", "ml", "data", "mobile",
}


# lookup helpers around the static ontology
class SkillOntology:

    def __init__(self, entries: Tuple[SkillEntry, ...] = _SKILLS) -> None:
        self.entries: Tuple[SkillEntry, ...] = entries
        self._by_alias: Dict[str, SkillEntry] = {}
        for entry in entries:
            for alias in entry.aliases:
                self._by_alias[alias] = entry
        # one big regex of all aliases, longest-first so "react native" beats "react".
        # word boundary [A-Za-z0-9_] - "React Native." closes cleanly while
        # the longest-first alternation still keeps C++, C#, Node.js (with internal
        # +, #, .) intact.
        sorted_aliases = sorted(self._by_alias.keys(), key=len, reverse=True)
        pattern = "|".join(re.escape(a) for a in sorted_aliases if a)
        self._regex = re.compile(
            rf"(?<![A-Za-z0-9_])({pattern})(?![A-Za-z0-9_])",
            re.IGNORECASE,
        )

    # normalisation
    def normalise(self, term: str) -> Optional[str]:
        # map a single term (case-insensitive) to its canonical form
        if not term:
            return None
        entry = self._by_alias.get(term.lower().strip())
        return entry.canonical if entry else None

    def normalise_list(self, terms: Iterable[str]) -> List[str]:
        # normalise + dedupe, preserving original order
        seen: List[str] = []
        for term in terms:
            canonical = self.normalise(term) or term.strip()
            if canonical and canonical not in seen:
                seen.append(canonical)
        return seen

    # extraction
    def find_in_text(self, text: str) -> List[str]:
        # canonical skill names found in `text` (deduplicated, ordered)
        if not text:
            return []
        seen: List[str] = []
        for match in self._regex.finditer(text):
            canonical = self.normalise(match.group(0))
            if canonical and canonical not in seen:
                seen.append(canonical)
        return seen

    # weighting / categorisation
    def weight_for(self, canonical: str) -> float:
        for entry in self.entries:
            if entry.canonical == canonical:
                return entry.weight
        return 1.0

    def is_technical(self, canonical: str) -> bool:
        for entry in self.entries:
            if entry.canonical == canonical:
                return entry.category in _TECHNICAL_CATEGORIES
        return False

    def category_for(self, canonical: str) -> str:
        for entry in self.entries:
            if entry.canonical == canonical:
                return entry.category
        return "general"


# module singleton - regex compile is expensive, do it once
ontology = SkillOntology()


__all__ = ["SkillOntology", "SkillEntry", "ontology"]
