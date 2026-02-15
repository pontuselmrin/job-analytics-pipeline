## Running Orgs
```bash
# Single org
uv run python -m ops.run_orgs --org <orgname>

# Multiple orgs
uv run python -m ops.run_orgs --org <orgname1> --org <orgname2>

# All orgs
uv run python -m ops.run_orgs --all

# All orgs, threaded
uv run python -m ops.run_orgs --all --parallel-orgs 8

# Quick iteration (skip tests)
uv run python -m ops.run_orgs --org <orgname> --max-jobs-per-org 2 --skip-tests
```
