"""Extract one representative job posting per firm-year from the WDC corpus.

Implements the longest-posting heuristic: for each domain, the posting with the
longest description is retained, since longer descriptions carry more granular
task and skill detail.
"""

from __future__ import annotations

import gzip
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

from aife.nquads import Quad, group_by_subject, normalize_domain


@dataclass
class Posting:
    domain: str
    url: str
    title: str | None
    description: str
    firm_name: str | None
    location: str | None


# Ordered most specific first: "addressLocality" also contains "address".
_BLANK_NODE_MARKERS = ("addresslocality", "addresscountry", "address", "name")


def _index_blank_nodes(quads: Iterable[Quad]) -> dict[str, dict[str, str]]:
    nodes: dict[str, dict[str, str]] = {}
    for quad in quads:
        if not quad.is_blank_subject:
            continue
        key = quad.predicate.lower()
        for marker in _BLANK_NODE_MARKERS:
            if marker in key:
                nodes.setdefault(quad.subject, {})[marker] = quad.obj
                break
    return nodes


def _resolve_location(place_node: str, blank_nodes: dict[str, dict[str, str]]) -> str | None:
    node = blank_nodes.get(place_node, {})
    address_node = node.get("address", place_node)
    props = blank_nodes.get(address_node, {})
    parts = [v for k, v in props.items() if k in ("addresslocality", "addresscountry")]
    return ", ".join(parts) if parts else None


def build_posting(subject: str, quads: list[Quad]) -> Posting | None:
    """Assemble a Posting from the quads describing a single page."""
    domain = normalize_domain(subject.strip("<>"))
    if domain is None:
        return None

    blank_nodes = _index_blank_nodes(quads)
    title = description = org_node = place_node = None

    for quad in quads:
        if quad.is_blank_subject:
            continue
        key = quad.predicate.lower()
        if "title" in key:
            title = quad.obj
        elif "description" in key:
            description = quad.obj
        elif "hiringorganization" in key:
            org_node = quad.obj
        elif "joblocation" in key:
            place_node = quad.obj

    return Posting(
        domain=domain,
        url=subject.strip("<>"),
        title=title,
        description=description or "",
        firm_name=blank_nodes.get(org_node, {}).get("name") if org_node else None,
        location=_resolve_location(place_node, blank_nodes) if place_node else None,
    )


def extract(corpus_files: Iterable[Path], domains: set[str]) -> dict[str, Posting]:
    """Return the longest posting seen for each requested domain."""
    best: dict[str, Posting] = {}

    for path in corpus_files:
        with gzip.open(path, "rt", encoding="utf-8", errors="ignore") as handle:
            for subject, quads in group_by_subject(handle):
                domain = normalize_domain(subject.strip("<>"))
                if domain not in domains:
                    continue
                posting = build_posting(subject, quads)
                if posting is None:
                    continue
                incumbent = best.get(domain)
                if incumbent is None or len(posting.description) > len(incumbent.description):
                    best[domain] = posting

    return best


def write_jsonl(postings: dict[str, Posting], destination: Path) -> None:
    with destination.open("w", encoding="utf-8") as handle:
        for posting in postings.values():
            handle.write(json.dumps(asdict(posting), ensure_ascii=False) + "\n")
