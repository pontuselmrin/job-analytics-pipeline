"""Batch definitions for review-driven scraper/enrichment stabilization."""

BATCHES: dict[str, dict] = {
    "B01": {
        "label": "Blocked + Unstable Sources",
        "orgs": ["Council", "AMLA", "UNFCCC", "EDA"],
        "notes": "First human-review batch focusing on blocked/empty edge cases plus one control org.",
    },
}
