"""Command line entry point for the AIFE measurement pipeline."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path

from aife.canonicalize import canonicalize
from aife.config import ConfigError, Settings
from aife.extract import extract, write_jsonl
from aife.score import score_postings, task_shares
from aife.vertex import TeacherClient


def _read_domains(path: Path) -> set[str]:
    with path.open(encoding="utf-8", errors="ignore") as handle:
        return {row[0].strip() for row in csv.reader(handle) if row and row[0].strip()}


def _read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _write_csv(rows: list[dict], destination: Path, fieldnames: list[str]) -> None:
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def cmd_extract(args: argparse.Namespace) -> int:
    corpus = sorted(args.corpus.glob("*.gz"))
    if not corpus:
        print(f"No .gz corpus files found in {args.corpus}", file=sys.stderr)
        return 1

    domains = _read_domains(args.domains)
    postings = extract(corpus, domains)
    write_jsonl(postings, args.output)
    print(f"Extracted {len(postings)} postings for {len(domains)} target domains")
    return 0


def cmd_canonicalize(args: argparse.Namespace) -> int:
    client = TeacherClient(Settings.from_env())
    domains = sorted(_read_domains(args.domains))
    firms = asyncio.run(canonicalize(client, domains, args.reference_year))
    _write_csv(
        [asdict(firm) for firm in firms],
        args.output,
        ["canonical_name", "firm_age", "firm_size", "country", "developed"],
    )
    dropped = len(domains) - len(firms)
    print(
        f"Resolved {len(firms)} firms from {len(domains)} domains "
        f"({dropped} collapsed or dropped)"
    )
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    client = TeacherClient(Settings.from_env())
    postings = _read_jsonl(args.postings)
    scores = asyncio.run(score_postings(client, postings))
    _write_csv(
        [asdict(score) for score in scores],
        args.output,
        ["domain", "short_summary", "aife_score", "category"],
    )

    missing = len(postings) - len(scores)
    shares = task_shares(scores)
    mean = sum(score.aife_score for score in scores) / len(scores) if scores else 0.0
    print(f"Scored {len(scores)} postings ({missing} unusable), mean AIFE {mean:.3f}")
    print("  " + "  ".join(f"{name} {share:.1%}" for name, share in shares.items()))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aife", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract_parser = subparsers.add_parser(
        "extract", help="select one representative posting per domain from the WDC corpus"
    )
    extract_parser.add_argument(
        "--corpus", type=Path, required=True, help="directory of .gz N-Quads dumps"
    )
    extract_parser.add_argument(
        "--domains", type=Path, required=True, help="CSV whose first column is a domain"
    )
    extract_parser.add_argument("--output", type=Path, required=True, help="destination JSONL")
    extract_parser.set_defaults(func=cmd_extract)

    canon_parser = subparsers.add_parser("canonicalize", help="resolve domains to firm entities")
    canon_parser.add_argument("--domains", type=Path, required=True)
    canon_parser.add_argument("--output", type=Path, required=True)
    canon_parser.add_argument(
        "--reference-year", type=int, required=True, help="year firm_age is measured against"
    )
    canon_parser.set_defaults(func=cmd_canonicalize)

    score_parser = subparsers.add_parser("score", help="assign AIFE scores and task labels")
    score_parser.add_argument(
        "--postings", type=Path, required=True, help="JSONL produced by `aife extract`"
    )
    score_parser.add_argument("--output", type=Path, required=True)
    score_parser.set_defaults(func=cmd_score)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as error:
        print(error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
