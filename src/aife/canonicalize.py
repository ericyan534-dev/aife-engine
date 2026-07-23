"""Resolve raw web domains to canonical firm entities with demographic covariates."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from aife import prompts
from aife.vertex import TeacherClient

DEFAULT_BATCH_SIZE = 50
UNKNOWN = "UNKNOWN"

_FIELDS = ("canonical_name", "firm_age", "firm_size", "country", "developed")


@dataclass(frozen=True)
class Firm:
    canonical_name: str
    firm_age: int
    firm_size: int
    country: str
    developed: int


def _coerce(record: dict) -> Firm | None:
    if not all(field in record for field in _FIELDS):
        return None
    name = str(record["canonical_name"]).strip()
    if not name or name.upper() == UNKNOWN:
        return None
    try:
        return Firm(
            canonical_name=name,
            firm_age=int(record["firm_age"]),
            firm_size=int(record["firm_size"]),
            country=str(record["country"]),
            developed=int(record["developed"]),
        )
    except (TypeError, ValueError):
        return None


async def _canonicalize_batch(
    client: TeacherClient, domains: list[str], reference_year: int
) -> list[Firm]:
    template = prompts.load("canonicalize").replace("REFERENCE_YEAR", str(reference_year))
    records = await client.complete_json(template.format(domains=domains))
    if records is None:
        return []
    return [firm for record in records if (firm := _coerce(record)) is not None]


async def canonicalize(
    client: TeacherClient,
    domains: list[str],
    reference_year: int,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> list[Firm]:
    """Map domains to distinct firms, dropping entries the model cannot resolve.

    Domains that resolve to the same legal entity collapse into one Firm, so the
    result is typically shorter than the input.
    """
    batches = [domains[i : i + batch_size] for i in range(0, len(domains), batch_size)]
    results = await asyncio.gather(
        *(_canonicalize_batch(client, batch, reference_year) for batch in batches)
    )

    seen: dict[str, Firm] = {}
    for firm in (firm for batch in results for firm in batch):
        seen.setdefault(firm.canonical_name, firm)
    return list(seen.values())
