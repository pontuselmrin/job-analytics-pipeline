# TDD + Batch Review Workflow

## Goal
Use test-driven development for scraper/enrichment changes and pause after each batch for human review + commit.

## Steps Per Batch
1. Write or update unit + contract tests for the batch orgs.
2. Implement scraper/enrichment code to satisfy tests.
3. Run:
   - `uv run pytest tests/unit tests/contract/test_batch_<id>_contract.py tests/integration/test_batch_<id>_integration.py`
4. Run batch harness:
   - `uv run python ops/harness/run_batch.py --batch <ID>`
5. Review generated report files under `ops/reports/batches/`.
6. Human review checkpoint: approve and commit.
7. Move to next batch.

## Notes
- `ops/harness/enrichment_matrix.py` is operational tooling (non-core) for diagnostics and reports.
- Core functionality should stay under `scrapers/`, `scrapers_playwright/`, and `enrichment/`.
