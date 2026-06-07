# pre-commit hook: block commits that look like real secrets
# exit 0 = clean, exit 1 = possible leak

from __future__ import annotations

import re
import sys
from pathlib import Path

# patterns that smell like real secrets
_DENY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # openai / anthropic / huggingface keys
    ("OpenAI API key", re.compile(r'sk-[A-Za-z0-9]{20,}')),
    ("Anthropic API key", re.compile(r'sk-ant-[A-Za-z0-9\-]{20,}')),
    ("HuggingFace token", re.compile(r'hf_[A-Za-z0-9]{20,}')),
    # aws
    ("AWS access key ID", re.compile(r'AKIA[0-9A-Z]{16}')),
    ("AWS secret (assignment)", re.compile(r'aws_secret_access_key\s*=\s*[A-Za-z0-9/+]{30,}')),
    # postgres dsn with real password
    ("DB URL with password", re.compile(r'postgresql://[^:]+:[^@]{6,}@')),
    # private key blocks
    ("Private key block", re.compile(r'-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----')),
    # high-entropy env vars (not placeholders)
    (
        "Possible secret in env assignment",
        re.compile(
            r'^(?:SECRET_KEY|JWT_SECRET|PASSWORD|PASSWD|API_KEY)\s*=\s*(?!change-me|your-|<|""|\'\')'
            r'[A-Za-z0-9+/\-_]{16,}',
            re.MULTILINE,
        ),
    ),
]

# filenames that should never land in git
_DENY_FILENAMES = {".env", "credentials.json", "serviceAccountKey.json"}


def check_file(path: Path) -> list[str]:
    violations: list[str] = []

    if path.name in _DENY_FILENAMES:
        violations.append(f"  {path}: file must not be committed ({path.name})")
        return violations

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return violations

    for label, pattern in _DENY_PATTERNS:
        if pattern.search(content):
            violations.append(f"  {path}: {label} detected")

    return violations


def main(argv: list[str]) -> int:
    all_violations: list[str] = []
    for arg in argv:
        p = Path(arg)
        if p.is_file():
            all_violations.extend(check_file(p))

    if all_violations:
        print("ERROR: Potential secret / credential leakage detected:\n")
        for v in all_violations:
            print(v)
        print(
            "\nIf these are false positives, move the value to a .env file "
            "(git-ignored) or use an environment variable."
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
