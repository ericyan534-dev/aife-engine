# AIFE Engine

[![CI](https://github.com/ericyan534-dev/aife-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/ericyan534-dev/aife-engine/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

Measuring firm-level AI adoption from online job postings.

**AI Intensity for Employment (AIFE)** turns unstructured hiring text into a firm–year
panel variable. Every job posting is scored 0–10 for how deeply the role engages with AI,
and labelled by the cognitive nature of the work — **Routine**, **Complex**, or
**Creative**. Aggregated to the firm, those scores become an adoption index and a task
composition, which is what downstream labor-market analysis actually needs.

The measure exists because the usual alternatives do not work at this granularity.
Keyword searches for "AI" or "machine learning" cannot tell a company that *builds* models
from one that merely *buys* a tool with a model inside it, and published occupation-level
exposure indices describe *potential* exposure rather than *revealed* adoption.

## Scope of this repository

This repository contains the **measurement pipeline** — the stage that converts raw web
data into scored firm–year observations:

| Stage | Module | What it does |
|---|---|---|
| Corpus extraction | `aife.nquads`, `aife.extract` | Stream Web Data Commons N-Quads dumps, reassemble `schema.org/JobPosting` records, and keep the longest posting per domain |
| Entity canonicalization | `aife.canonicalize` | Resolve heterogeneous employer domains to single legal entities with firm age, size, country, and development status |
| Teacher scoring | `aife.score` | Assign each posting an AIFE score and a task label under deterministic decoding |
| Index construction | `aife.score` | `aife_index` and `task_shares` aggregate postings to the firm–year level |

Not included here. The wider study additionally covers student-model distillation into a ModernBERT encoder, human-in-the-loop calibration, the econometric analysis (two-way fixed effects, event study, shift-share IV), and the Temporal Fusion Transformer forecasting system. Those components are described in the manuscript; their code is not part of this release. Nothing in this repository should be read as reproducing the paper's reported estimates.


## Install

```bash
pip install -e ".[dev]"
cp .env.example .env      # then set AIFE_PROJECT_ID
```

Scoring and canonicalization call Vertex AI, so they need a Google Cloud project with
Vertex quota and working application-default credentials:

```bash
gcloud auth application-default login
```

Extraction is purely local and needs no credentials.

## Usage

```bash
# 1. Pull one representative posting per firm out of the WDC dumps.
aife extract \
  --corpus  /path/to/wdc/2024 \
  --domains 2024.csv \
  --output  postings-2024.jsonl

# 2. Resolve domains to canonical firms with demographic covariates.
aife canonicalize \
  --domains        2024.csv \
  --reference-year 2025 \
  --output         firms-2024.csv

# 3. Score each posting and label its task content.
aife score \
  --postings postings-2024.jsonl \
  --output   scores-2024.csv
```

Step 3 prints the mean AIFE score and the Routine/Complex/Creative shares for the year.

## Design notes

**Longest-posting heuristic.** One posting per firm–year enters the labelled set: the one
with the longest description. Longer descriptions carry more granular task and skill
detail, it prevents high-volume hirers from dominating, and it keeps each record inside
the model context window. The cost is a bias toward larger, more professionalized
employers — real, and worth stating.

**Deterministic decoding.** Temperature 0 and top-*k* 1, so repeated runs over identical
input give identical labels. Safety filters are disabled: ordinary technical vocabulary
("kill process", "master/slave architecture") otherwise trips false positives on
legitimate engineering job descriptions.

**Failures are dropped, not defaulted.** A batch whose response fails validation is
excluded rather than backfilled with a neutral score. Substituting a default would drag
every firm-level mean toward that value and quietly corrupt the panel. The CLI reports how
many records were discarded.

**Prompts are data.** Both prompts live in `src/aife/prompts/` as plain text rather than
embedded string literals, since the exact wording is a methodological choice that belongs
under review and version control.

## Data source

[Web Data Commons](https://webdatacommons.org/) Schema.org extraction, `JobPosting` class,
derived from Common Crawl. The dumps are N-Quads, one RDF statement per line, with the
fourth element recording the source page — so every extracted field remains traceable to
the page it came from. The corpus is not redistributed here; download it from WDC directly.

## Limitations

- **Demand-side only.** Job postings measure labor *demand*. They say nothing about worker
  supply, skills, wages, or whether anyone was hired.
- **Coverage bias.** The corpus over-represents English-language, digitally posted roles at
  formal-sector firms. Informal labor markets and firms without a web presence are absent.
- **Generated regressor.** AIFE is a model output, not a verified fact about a firm. It
  captures stated hiring intent, not deployed technology.
- **Firm covariates are model estimates.** `firm_age`, `firm_size`, and `country` come from
  the language model, not a company registry, and carry the corresponding error.

## Citation

Liqian Yan, Yintong Chen, and Zichun Qiu. *The AIFE Engine: A Computational Framework to
Quantify and Forecast the Great Labor Reallocation.* Regeneron International Science and
Engineering Fair, 2026.

See [`CITATION.cff`](CITATION.cff).

## License

Licensed under the [Apache License 2.0](LICENSE).
