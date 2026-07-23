"""Minimal N-Quads reader for the Web Data Commons JobPosting corpus."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from urllib.parse import urlparse

_ESCAPES = (("\\n", "\n"), ("\\t", "\t"), ('\\"', '"'))


@dataclass(frozen=True)
class Quad:
    subject: str
    predicate: str
    obj: str

    @property
    def is_blank_subject(self) -> bool:
        return self.subject.startswith("_:")


def parse_line(line: str) -> Quad | None:
    """Parse one N-Quads line. Returns None if the line is malformed."""
    parts = line.split(" ", 2)
    if len(parts) < 3:
        return None

    subject, predicate, rest = parts
    if rest.startswith(("<", "_:")):
        obj = rest.split(" ", 1)[0]
    else:
        end = rest.rfind('"')
        if end <= 0:
            return None
        obj = rest[1:end]
        for escaped, literal in _ESCAPES:
            obj = obj.replace(escaped, literal)

    return Quad(subject, predicate, obj)


def normalize_domain(value: str | None) -> str | None:
    """Reduce a URL or bare host to a lowercase registrable domain."""
    if not value:
        return None
    if not value.startswith("http"):
        value = f"http://{value}"
    host = urlparse(value).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or None


def group_by_subject(lines: Iterator[str]) -> Iterator[tuple[str, list[Quad]]]:
    """Yield (subject URI, quads) groups.

    The WDC dumps keep every quad describing one page contiguous, so a subject
    change marks a record boundary. Blank nodes belong to the preceding URI.
    """
    subject: str | None = None
    buffer: list[Quad] = []

    for line in lines:
        if not line.strip():
            continue
        quad = parse_line(line)
        if quad is None:
            continue

        if not quad.is_blank_subject and quad.subject != subject:
            if subject is not None and buffer:
                yield subject, buffer
            subject = quad.subject
            buffer = []

        buffer.append(quad)

    if subject is not None and buffer:
        yield subject, buffer
