from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class SensitivePattern:
    key: str
    description: str
    pattern: re.Pattern[str]


TEXT_PATTERNS: tuple[SensitivePattern, ...] = (
    SensitivePattern(
        key="host_users_path",
        description="host-specific /Users path literal",
        pattern=re.compile(r"/Users/[^\s'\"`]+"),
    ),
    SensitivePattern(
        key="macos_temp_path",
        description="macOS temp/cache path literal",
        pattern=re.compile(r"/(?:private/)?var/folders/[^\s'\"`]+"),
    ),
    SensitivePattern(
        key="personal_name_sample",
        description="personal sample marker from browser fixtures",
        pattern=re.compile(r"Hi,\s*Yifeng|Yifeng\[Terry\]\s*Yu"),
    ),
)


def find_sensitive_text_hits(text: str) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    for item in TEXT_PATTERNS:
        for match in item.pattern.finditer(text):
            hits.append((item.description, match.group(0)))
    return hits
