# Evalbench

Local replay and evaluation tooling for the commerce-agent pipeline.

## Available Suites

- `router`
- `text`
- `image`
- `multimodal`
- `e2e`
- `all`

## Run

```bash
python -m devtools.evalbench.runner --suite text
python -m devtools.evalbench.runner --suite image
python -m devtools.evalbench.runner --suite all --output devtools/evalbench/reports/latest.json
```

## Requirements

Before running retrieval suites, make sure:

1. PostgreSQL is up
2. the schema is applied
3. tiny seed is loaded
4. semantic indexes are built

## Current Scope

The current runner focuses on:

- intent replay
- text/image/multimodal path replay
- expected top product checks
- trace capture

It is designed to expand later with richer ranking metrics and HTML reports.
