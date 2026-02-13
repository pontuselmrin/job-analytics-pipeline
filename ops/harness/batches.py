"""Batch definitions for review-driven scraper/enrichment stabilization."""

BATCHES: dict[str, dict] = {
    "B01": {
        "label": "Blocked + Unstable Sources",
        "orgs": ["Council", "AMLA", "EDA"],
        "notes": "First human-review batch focusing on blocked/empty edge cases plus one control org.",
    },
    "B02": {
        "label": "Alphabetical Rollout: ACER to CEDEFOP",
        "orgs": ["ACER", "BEREC", "BIS", "CEB", "CEDEFOP"],
        "notes": "Next five scrapers from scrapers/ alphabetical order, excluding prior-batch orgs.",
    },
}
