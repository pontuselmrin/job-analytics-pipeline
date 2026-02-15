# Tests

This directory contains unit, integration, and contract tests for the scraping project.

### Setup

1. **Copy the example configuration:**
   ```bash
   cp tests/test_config_local.py.example tests/test_config_local.py
   ```

2. **Edit `test_config_local.py` with real organization data** (optional):
   - If you don't create this file, tests will use generic placeholder data from `test_config.py`

3. **Run tests:**
   ```bash
   pytest tests/
   ```

### How It Works

- `test_config.py` - Main config module that imports from `test_config_local.py` if it exists
- `test_config_local.py.example` - Template showing the config structure
- `test_config_local.py` - Your local config with real data


## Test Structure

- `unit/` - Fast unit tests for individual functions and modules
- `integration/` - Tests that verify artifact schemas and data structure
- `contract/` - Quality gate tests for production runs
- `fixtures/` - Shared test fixtures and quality gate configurations
- `conftest.py` - Pytest configuration and shared fixtures

## Test Categories

### Core Tests (Work Everywhere)
These tests work with or without local scraper implementations:
- `test_base_fetch_retry.py` - HTTP retry logic
- `test_fetcher_utils.py` - Content fetching utilities
- `test_runner_logging.py` - Runner and logging functionality
- `test_quality_gate_helpers.py` - Quality validation helpers
