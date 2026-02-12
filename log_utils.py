import json
from datetime import datetime
from pathlib import Path

LOG_FILE = Path(__file__).parent / "scrape_log.json"


def load_log():
    with open(LOG_FILE) as f:
        return json.load(f)


def save_log(log):
    log["last_updated"] = datetime.now().isoformat()
    log["summary"]["total"] = len(log["sites"])
    log["summary"]["success"] = sum(1 for s in log["sites"] if s["status"] == "success")
    log["summary"]["partial"] = sum(1 for s in log["sites"] if s["status"] == "partial")
    log["summary"]["failed"] = sum(1 for s in log["sites"] if s["status"] == "failed")
    log["summary"]["skipped"] = sum(1 for s in log["sites"] if s["status"] == "skipped")
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)


def log_site(name, url, status, script_file=None, vacancies_found=None,
             has_pagination=False, notes=""):
    """
    Log a site's scraping outcome.

    status: "success" | "partial" | "failed" | "skipped"
    """
    log = load_log()

    # Remove existing entry if present
    log["sites"] = [s for s in log["sites"] if s["name"] != name]

    log["sites"].append({
        "name": name,
        "url": url,
        "status": status,
        "script_file": script_file,
        "vacancies_found": vacancies_found,
        "has_pagination": has_pagination,
        "notes": notes,
        "timestamp": datetime.now().isoformat()
    })

    save_log(log)
    print(f"[{status.upper()}] {name}: {notes}")


def show_progress():
    log = load_log()
    s = log["summary"]
    print(f"\nProgress: {s['total']} sites processed")
    print(f"  Success: {s['success']}")
    print(f"  Partial: {s['partial']}")
    print(f"  Failed:  {s['failed']}")
    print(f"  Skipped: {s['skipped']}")
