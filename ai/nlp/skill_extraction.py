# Legacy keyword-list skill extractor.
# Production path uses skill_ontology.py (101 skills, 10 categories).
# Kept for tech/soft split that older code paths still call.
from typing import List
import re


class SkillExtractor:

    def __init__(self):
        # technical skills - hand-curated keyword set
        self.technical_skills = {
            # languages
            'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'go', 'rust', 'kotlin', 'swift',
            'php', 'ruby', 'perl', 'scala', 'r', 'matlab', 'dart', 'lua',

            # web
            'react', 'vue', 'angular', 'node.js', 'express', 'django', 'flask', 'fastapi', 'spring',
            'html', 'css', 'sass', 'less', 'bootstrap', 'tailwind', 'jquery', 'next.js', 'nuxt.js',
            'graphql', 'rest api', 'soap', 'webpack', 'vite', 'npm', 'yarn',

            # databases
            'sql', 'postgresql', 'mysql', 'mongodb', 'redis', 'cassandra', 'elasticsearch',
            'oracle', 'sqlite', 'dynamodb', 'neo4j', 'couchdb', 'firebase',

            # cloud + devops
            'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'terraform', 'ansible', 'jenkins',
            'github actions', 'gitlab ci', 'circleci', 'travis ci',
            'linux', 'bash', 'shell scripting', 'powershell', 'vagrant', 'packer',

            # ML / AI
            'machine learning', 'deep learning', 'nlp', 'computer vision', 'tensorflow', 'pytorch',
            'keras', 'scikit-learn', 'pandas', 'numpy', 'opencv', 'nltk', 'spacy',

            # mobile
            'android', 'ios', 'react native', 'flutter', 'xamarin', 'ionic',

            # misc
            'git', 'svn', 'mercurial', 'microservices', 'api design', 'agile', 'scrum', 'kanban',
            'ci/cd', 'tdd', 'bdd', 'devops', 'sre', 'monitoring', 'logging',
        }

        # soft skills
        self.soft_skills = {
            'communication', 'leadership', 'teamwork', 'problem solving', 'critical thinking',
            'time management', 'project management', 'collaboration', 'adaptability', 'creativity',
            'analytical thinking', 'attention to detail', 'multitasking', 'negotiation',
            'presentation', 'public speaking', 'mentoring', 'coaching', 'conflict resolution',
        }

        self.all_skills = self.technical_skills | self.soft_skills

    def extract_skills(self, text: str) -> List[str]:
        # case-insensitive keyword sweep + a couple of "Xxx developer/engineer" patterns
        text_lower = text.lower()
        found_skills = set()

        for skill in self.all_skills:
            if skill in text_lower:
                found_skills.add(skill.title())

            # word-boundary check catches "Python" inside "python programming" etc
            skill_pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(skill_pattern, text_lower, re.IGNORECASE):
                found_skills.add(skill.title())

        # "X developer" / "proficient in X" patterns - second extraction pass
        skill_patterns = [
            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:developer|engineer|specialist|expert|professional)',
            r'(?:proficient|experienced|skilled|expert)\s+in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        ]

        for pattern in skill_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                match_lower = match.lower()
                for skill in self.all_skills:
                    if skill in match_lower or match_lower in skill:
                        found_skills.add(skill.title())

        return sorted(list(found_skills))

    def extract_technical_skills(self, text: str) -> List[str]:
        all_skills = self.extract_skills(text)
        return [s for s in all_skills if s.lower() in self.technical_skills]

    def extract_soft_skills(self, text: str) -> List[str]:
        all_skills = self.extract_skills(text)
        return [s for s in all_skills if s.lower() in self.soft_skills]

