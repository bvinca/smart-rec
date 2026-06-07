# Text normalisation + regex extractors for email, phone, year, duration.
import re
from typing import Optional


class TextPreprocessor:

    @staticmethod
    def normalize_text(text: str) -> str:
        # collapse runs of newlines, strip oddball chars, normalise whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[^\w\s\.\,\;\:\-\'\(\)\/]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n', text)

        return text.strip()

    @staticmethod
    def extract_email(text: str) -> Optional[str]:
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        return emails[0] if emails else None

    @staticmethod
    def extract_phone(text: str) -> Optional[str]:
        phone_patterns = [
            r'\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
            r'\+?\d{1,3}[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',
            r'\(\d{3}\)\s?\d{3}[-.\s]?\d{4}',
        ]
        for pattern in phone_patterns:
            matches = re.findall(pattern, text)
            if matches:
                return matches[0]
        return None

    @staticmethod
    def extract_year(text: str) -> Optional[str]:
        year_match = re.search(r'\b(19|20)\d{2}\b', text)
        return year_match.group() if year_match else None

    @staticmethod
    def extract_duration(text: str) -> Optional[str]:
        # try a few date-range formats
        duration_patterns = [
            r'(\d{4})\s*-\s*(\d{4}|present|current)',
            r'(\w+\s+\d{4})\s*-\s*(\w+\s+\d{4}|present|current)',
            r'(\d{1,2}/\d{4})\s*-\s*(\d{1,2}/\d{4}|present|current)',
        ]

        for pattern in duration_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group()
        return None

