"""Teacher scoring: assign each posting an AIFE intensity score and a task label."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from aife import prompts
from aife.vertex import TeacherClient

DEFAULT_BATCH_SIZE = 20
DESCRIPTION_CHAR_LIMIT = 2500

CATEGORIES = ("Routine", "Complex", "Creative")
SCORE_MIN, SCORE_MAX = 0.0, 10.0


@dataclass(frozen=True)
class Score:
    domain: str
    short_summary: str
    aife_score: float
    category: str


def _coerce(record: dict) -> Score | None:
    domain = record.get("id")
    if not domain:
        return None
    try:
        score = float(record["aife_score"])
    except (KeyError, TypeError, ValueError):
        return None
    if not SCORE_MIN <= score <= SCORE_MAX:
        return None
    category = record.get("category")
    if category not in CATEGORIES:
        return None
    return Score(
        domain=str(domain),
        short_summary=str(record.get("short_summary", "")),
        aife_score=score,
        category=category,
    )


async def _score_batch(client: TeacherClient, postings: Sequence[dict]) -> list[Score]:
    payload = [
        {
            "id": posting.get("domain", "unknown"),
            "title": posting.get("title") or "Unknown",
            "description": (posting.get("description") or "")[:DESCRIPTION_CHAR_LIMIT],
        }
        for posting in postings
    ]
    records = await client.complete_json(prompts.load("aife_scoring").format(batch_data=payload))
    if records is None:
        return []
    return [score for record in records if (score := _coerce(record)) is not None]


async def score_postings(
    client: TeacherClient,
    postings: Sequence[dict],
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> list[Score]:
    """Score every posting. Batches that fail validation are dropped, not defaulted.

    Silently substituting a neutral score would bias the firm-level mean toward
    whatever default was chosen, so unusable responses are excluded instead.
    """
    batches = [postings[i : i + batch_size] for i in range(0, len(postings), batch_size)]
    results = await asyncio.gather(*(_score_batch(client, batch) for batch in batches))
    return [score for batch in results for score in batch]


def aife_index(scores: Iterable[Score]) -> float | None:
    """Firm-year AIFE index: mean posting score normalized to [0, 1]."""
    values = [score.aife_score for score in scores]
    if not values:
        return None
    return sum(values) / len(values) / SCORE_MAX


def task_shares(scores: Sequence[Score]) -> dict[str, float]:
    """Share of postings in each task category. Returns zeros for an empty input."""
    if not scores:
        return {category: 0.0 for category in CATEGORIES}
    total = len(scores)
    return {
        category: sum(score.category == category for score in scores) / total
        for category in CATEGORIES
    }
