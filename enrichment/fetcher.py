"""Fetch job descriptions: PDF detection, download, and HTML text extraction."""

import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from config import USER_AGENT
from .config import MAX_DESCRIPTION_CHARS, REQUEST_TIMEOUT
from .org_config import (
    SSL_INSECURE_DOMAINS,
    PREFER_EMBEDDED_PDF_ORGS,
    NEXTJS_PLATFORMS,
    PLATFORM_A_DOMAINS,
    API_BASED_V1_DOMAINS,
    API_BASED_V2_DOMAINS,
    TABLE_INTERFACE_DOMAINS,
    PLAYWRIGHT_DOMAINS,
)

# Add scrapers dir to path so we can import base.fetch
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scrapers"))
from base import DEFAULT_HEADERS, fetch  # noqa: E402

# Markers indicating a page requires JavaScript to render meaningful content
JS_PLACEHOLDER_MARKERS = (
    "you need to enable javascript",
    "loading application",
    "loading\n.\n.\n.",
    "please wait",
)

PDF_POSITIVE_MARKERS = (
    "vacancy",
    "vacancy notice",
    "vacancy_notice",
    "notice",
    "call for expression",
    "call for expressions",
    "job profile",
    "job description",
    "recruitment",
    "position",
    "reference",
    "srb/",
    "vn-",
    "ta ",
    "ad ",
    "ast",
    "ca fg",
)

PDF_NEGATIVE_MARKERS = (
    "candidate manual",
    "online application manual",
    "manual",
    "privacy notice",
    "data protection notice",
    "cookie",
    "gdpr",
)


def _norm_words(text: str) -> set[str]:
    stop = {
        "with",
        "from",
        "into",
        "the",
        "and",
        "for",
        "this",
        "that",
        "your",
        "our",
        "about",
    }
    words = re.findall(r"[a-z0-9]{4,}", (text or "").lower())
    return {w for w in words if w not in stop}


def slugify(text: str, max_len: int = 80) -> str:
    """Convert text to a filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:max_len]


def _url_host(url: str) -> str:
    return (urlparse(url).netloc or "").lower()


def _verify_ssl(url: str) -> bool:
    return _url_host(url) not in SSL_INSECURE_DOMAINS


def _is_table_row_url(url: str) -> bool:
    """Check if URL points to a table-based interface with row fragments."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    return any(domain in host for domain in TABLE_INTERFACE_DOMAINS) and bool(
        re.search(r"row-(\d+)$", parsed.fragment or "")
    )


def _extract_table_row_index(url: str) -> int | None:
    """Extract row index from a table-based interface URL fragment."""
    parsed = urlparse(url)
    m = re.search(r"row-(\d+)$", parsed.fragment or "")
    if not m:
        return None
    return int(m.group(1))


def _request(url: str, method: str = "GET", **kwargs):
    return fetch(
        url,
        method=method,
        headers=kwargs.pop("headers", DEFAULT_HEADERS),
        timeout=kwargs.pop("timeout", REQUEST_TIMEOUT),
        verify=_verify_ssl(url),
        **kwargs,
    )


def detect_content_type(url: str) -> str:
    """Detect whether a URL points to a PDF or HTML page.

    Returns 'pdf' or 'html'.
    """
    if url.lower().endswith(".pdf"):
        return "pdf"

    try:
        resp = _request(url, method="HEAD")
        ct = resp.headers.get("Content-Type", "").lower()
        if "application/pdf" in ct:
            return "pdf"
    except Exception:
        pass

    return "html"


def download_pdf(url: str, org_abbrev: str, title: str, run_id: str = "default") -> str:
    """Download a PDF and return its relative path from project root.

    Saves to ops/runs/{run_id}/pdfs/{org_abbrev}/{slug}-{date}.pdf.
    Deletes partial downloads on failure.
    """
    from .config import get_pdf_dir

    pdf_dir = get_pdf_dir(run_id)
    org_dir = pdf_dir / org_abbrev
    org_dir.mkdir(parents=True, exist_ok=True)

    slug = slugify(title)
    filename = f"{slug}-{date.today().isoformat()}.pdf"
    filepath = org_dir / filename

    try:
        resp = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            stream=True,
            timeout=REQUEST_TIMEOUT,
            verify=_verify_ssl(url),
        )
        resp.raise_for_status()

        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        from .config import PROJECT_ROOT

        return str(filepath.relative_to(PROJECT_ROOT))
    except Exception:
        # Clean up partial download
        if filepath.exists():
            filepath.unlink()
        raise


def _download_table_row_pdf(
    url: str, org_abbrev: str, title: str, run_id: str = "default"
) -> str:
    """Download PDF from a table-based interface that triggers downloads via button clicks."""
    row_idx = _extract_table_row_index(url)
    if row_idx is None:
        raise RuntimeError("missing_table_row_index")

    from .config import get_pdf_dir

    PDF_DIR = get_pdf_dir(run_id)
    org_dir = PDF_DIR / org_abbrev
    org_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{slugify(title)}-{date.today().isoformat()}.pdf"
    filepath = org_dir / filename

    sys.path.insert(
        0, str(Path(__file__).resolve().parent.parent / "scrapers_playwright")
    )
    from playwright.sync_api import sync_playwright

    base_url = url.split("#", 1)[0]
    button_id = f"VACANCYNTGPAST\\${row_idx}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True, accept_downloads=True)
        page = context.new_page()
        page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2500)
        target_frame = None
        for frame in page.frames:
            try:
                html = frame.content()
            except Exception:
                continue
            if f"PROFILEGPAST${row_idx}" in html:
                target_frame = frame
                break
        if target_frame is None:
            browser.close()
            raise RuntimeError("table_frame_not_found")

        with page.expect_download(timeout=45000) as dl_info:
            target_frame.locator(f"#{button_id}").click()
        download = dl_info.value
        download.save_as(str(filepath))
        browser.close()

    if not filepath.exists() or filepath.stat().st_size == 0:
        raise RuntimeError("table_pdf_download_failed")

    from .config import PROJECT_ROOT

    return str(filepath.relative_to(PROJECT_ROOT))


def _is_legacy_ats_url(url: str) -> bool:
    """Check if a URL is a legacy ATS (Applicant Tracking System) job detail page.

    These systems store content URL-encoded in JavaScript and use .ftl templates.
    """
    lowered = url.lower()
    return "/careersection/" in lowered and "jobdetail.ftl" in lowered


def _extract_legacy_ats_description(html: str) -> str:
    """Extract job description from a legacy ATS detail page.

    These pages store content URL-encoded in JS. After decoding, the
    job detail lives inside a div.singleview container or requisitionDescription.
    """
    decoded = unquote(html)
    soup = BeautifulSoup(decoded, "html.parser")

    # The singleview div contains the rendered job description for all
    # legacy ATS template variants (MsoNormal-based and plain-span-based).
    container = soup.find("div", class_="singleview")
    if container:
        for tag in container.find_all(["script", "style"]):
            tag.decompose()
        text = container.get_text("\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.replace("\\:", ":").replace("\\;", ";")
        return text[:MAX_DESCRIPTION_CHARS]

    # Alternative template variant: content under requisitionDescription
    # with MsoNormal paragraphs.
    req = soup.find(id=re.compile(r"requisitionDescription", re.I))
    if req:
        mso_lines = []
        for node in req.find_all(class_=re.compile(r"MsoNormal", re.I)):
            line = node.get_text(" ", strip=True)
            if line and len(line) > 15:
                mso_lines.append(line)
        if mso_lines:
            text = "\n".join(mso_lines)
            text = re.sub(r"\n{3,}", "\n\n", text)
            text = text.replace("\\:", ":").replace("\\;", ";")
            return text[:MAX_DESCRIPTION_CHARS]

        req_text = req.get_text("\n", strip=True)
        if len(req_text) > 200:
            req_text = req_text.replace("\\:", ":").replace("\\;", ";")
            return req_text[:MAX_DESCRIPTION_CHARS]

    # Some legacy ATS variants embed description sections in one or more
    # `!|!!*!...` payload fragments. We score each fragment and keep the best.
    marker = "!|!!*!"
    if marker in decoded:
        keyword_markers = (
            "organizational setting",
            "minimum requirements",
            "technical skills",
            "responsibilities",
            "duties and responsibilities",
            "selection criteria",
            "job purpose",
            "qualifications",
            "required skills",
        )
        noise_markers = (
            "important notice",
            "how to apply",
            "additional information",
            "apply now",
        )

        best_text = ""
        best_score = -1
        parts = decoded.split(marker)[1:]
        for part in parts:
            # End fragment at the next known section or job-id delimiter.
            cut_points = []
            next_marker = part.find(marker)
            if next_marker != -1:
                cut_points.append(next_marker)
            job_delim = re.search(r"!\|!\d{6,8}!\|!", part)
            if job_delim:
                cut_points.append(job_delim.start())
            fragment_html = part[: min(cut_points)] if cut_points else part

            fragment_text = BeautifulSoup(fragment_html, "html.parser").get_text(
                "\n", strip=True
            )
            fragment_text = re.sub(r"\n{3,}", "\n\n", fragment_text)
            fragment_text = (
                fragment_text.replace("\\:", ":").replace("\\;", ";").strip()
            )
            if not fragment_text:
                continue

            lowered = fragment_text.lower()
            words = len(fragment_text.split())
            marker_hits = sum(1 for k in keyword_markers if k in lowered)
            noise_hits = sum(1 for k in noise_markers if k in lowered)

            # Prefer substantive sections and strongly prefer known JD markers.
            score = words + (marker_hits * 400) - (noise_hits * 120)
            if score > best_score:
                best_score = score
                best_text = fragment_text

        if best_text:
            return best_text[:MAX_DESCRIPTION_CHARS]

    return ""


def extract_html_description(url: str, use_playwright: bool = False) -> str:
    """Fetch a page and extract the main text content.

    Returns cleaned text capped at MAX_DESCRIPTION_CHARS.
    """
    if use_playwright:
        return _extract_with_playwright(url)

    api_v2_desc = _extract_api_based_description_v2(url)
    if api_v2_desc:
        return api_v2_desc

    platform_a_desc = _extract_platform_a_description(url)
    if platform_a_desc:
        return platform_a_desc

    api_v1_desc = _extract_api_based_description_v1(url)
    if api_v1_desc:
        return api_v1_desc

    resp = _request(url)
    nextjs_desc = _extract_nextjs_description_from_html(url, resp.text)
    if nextjs_desc:
        return nextjs_desc

    # Legacy ATS pages need special handling (content is URL-encoded in JS)
    if _is_legacy_ats_url(url):
        result = _extract_legacy_ats_description(resp.text)
        if result:
            return result

    parsed = _parse_html(resp.text)
    if _is_short_or_placeholder(parsed):
        pdf_link = _find_embedded_pdf_link(resp.text, url)
        if pdf_link:
            return ""
        if not use_playwright and _should_try_playwright(url, parsed, resp.text):
            try:
                parsed_pw = _extract_with_playwright(url)
                if len(parsed_pw) > len(parsed):
                    return parsed_pw
            except Exception:
                pass
    return parsed


def _extract_with_playwright(url: str) -> str:
    """Extract description using Playwright for JS-heavy pages."""
    sys.path.insert(
        0, str(Path(__file__).resolve().parent.parent / "scrapers_playwright")
    )
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        try:
            page.wait_for_load_state("networkidle", timeout=12000)
        except Exception:
            pass
        page.wait_for_timeout(4500)
        html = page.content()
        browser.close()

    return _parse_html(html)


def _parse_html(html: str) -> str:
    """Parse HTML and extract the main descriptive text."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove noise elements
    for tag in soup.find_all(["script", "style", "nav", "header", "footer"]):
        tag.decompose()

    selector_candidates = [
        "[itemprop='description']",
        "[data-careersite-propertyid='description']",
        ".jobdescription",
        "div.gestmax-container",
        "div.gestmax-template-container",
        "div#requisitionDescription",
        "div#requisitionDescriptionInterface",
        "article",
        "main",
        "[class*='job-description']",
        "[id*='job-description']",
        "[class*='description']",
        "[id*='description']",
        "body",
    ]

    best_text = ""
    for selector in selector_candidates:
        for node in soup.select(selector):
            text = node.get_text("\n", strip=True)
            text = _clean_text(text)
            if len(text) > len(best_text):
                best_text = text
        if len(best_text) >= 250:
            break

    return best_text[:MAX_DESCRIPTION_CHARS]


def _extract_nextjs_description_from_html(url: str, html: str) -> str:
    """Extract job description from Next.js application payloads.

    Some platforms embed JSON data in __NEXT_DATA__ script tags.
    """
    host = _url_host(url)
    if not any(platform in host for platform in NEXTJS_PLATFORMS):
        return ""

    soup = BeautifulSoup(html, "html.parser")
    data_tag = soup.find("script", id="__NEXT_DATA__")
    if not data_tag or not data_tag.string:
        return ""

    try:
        data = json.loads(data_tag.string)
    except Exception:
        return ""

    key_markers = (
        "description",
        "jobdescription",
        "job_description",
        "responsibil",
        "profile",
        "qualification",
        "requirement",
        "offer",
        "about",
    )
    noise_markers = (
        "job list",
        "please confirm this action",
        "privacy policy",
        "imprint",
        "navigation",
    )

    best_text = ""
    best_score = -1

    def _walk(node: object, path: str = "") -> None:
        nonlocal best_text, best_score
        if isinstance(node, dict):
            for k, v in node.items():
                next_path = f"{path}.{k}".lower() if path else str(k).lower()
                _walk(v, next_path)
            return
        if isinstance(node, list):
            for item in node:
                _walk(item, path)
            return
        if not isinstance(node, str):
            return

        candidate = _clean_text(
            BeautifulSoup(node, "html.parser").get_text("\n", strip=True)
        )
        if len(candidate) < 180:
            return

        lowered = candidate.lower()
        words = len(candidate.split())
        score = words
        if any(m in path for m in key_markers):
            score += 250
        if any(m in lowered for m in noise_markers):
            score -= 500
        if "job list" in lowered and "confirm" in lowered:
            score -= 500
        if score > best_score:
            best_score = score
            best_text = candidate

    _walk(data)
    if best_score < 80:
        return ""
    return best_text[:MAX_DESCRIPTION_CHARS]


def _clean_text(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.replace("\\:", ":").replace("\\;", ";")
    lines = [ln.strip() for ln in text.splitlines()]
    noise = {
        "view profile",
        "employee login",
        "create/ view profile",
        "language",
        "loading",
    }
    filtered = [ln for ln in lines if ln and ln.lower() not in noise]
    return "\n".join(filtered).strip()


def _extract_platform_a_description(url: str) -> str:
    """Extract job description from Platform A-style career sites.

    These sites use a specific URL structure: /job/{slug}
    and provide JSON APIs at /wday/cxs/{tenant}/{site}/job/{slug}
    """
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if not any(domain in host for domain in PLATFORM_A_DOMAINS):
        return ""

    path = parsed.path.rstrip("/")
    if path.endswith("/apply"):
        path = path[:-6]

    parts = [p for p in path.split("/") if p]
    if "job" not in parts:
        return ""

    job_idx = parts.index("job")
    if job_idx == 0:
        return ""

    site = parts[job_idx - 1]
    if re.fullmatch(r"[a-z]{2}-[a-z]{2}", site, flags=re.I) and job_idx >= 2:
        site = parts[job_idx - 2]
    slug = "/".join(parts[job_idx + 1 :])
    if not slug:
        return ""

    tenant = host.split(".")[0]
    api_url = f"{parsed.scheme}://{parsed.netloc}/wday/cxs/{tenant}/{site}/job/{slug}"

    try:
        resp = requests.get(
            api_url,
            headers={**DEFAULT_HEADERS, "Accept": "application/json"},
            timeout=REQUEST_TIMEOUT,
            verify=_verify_ssl(api_url),
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return ""

    posting = data.get("jobPostingInfo", {})
    if not isinstance(posting, dict):
        return ""

    desc_html = posting.get("jobDescription", "") or posting.get("description", "")
    if not desc_html:
        return ""

    soup = BeautifulSoup(desc_html, "html.parser")
    text = _clean_text(soup.get_text("\n", strip=True))
    return text[:MAX_DESCRIPTION_CHARS]


def _extract_api_based_description_v1(url: str) -> str:
    """Extract job description from API-based recruitment systems (variant 1).

    These systems expose a JSON API with job listings that can be matched by ID.
    """
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if not any(domain in host for domain in API_BASED_V1_DOMAINS):
        return ""
    match = re.search(r"/vacancies/(\d+)", parsed.path)
    if not match:
        return ""

    job_id = int(match.group(1))
    api_url = f"{parsed.scheme}://{parsed.netloc}/api/CurrentJobVacancies"

    try:
        resp = requests.get(
            api_url,
            headers={**DEFAULT_HEADERS, "Accept": "application/json, text/plain, */*"},
            timeout=REQUEST_TIMEOUT,
            verify=_verify_ssl(api_url),
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return ""

    if not isinstance(data, list):
        return ""
    match_item = next(
        (
            row
            for row in data
            if isinstance(row, dict) and row.get("jobVacancyId") == job_id
        ),
        None,
    )
    if not match_item:
        return ""

    html_fields = [
        match_item.get("jobDescription", ""),
        match_item.get("purposeforthepost", ""),
        match_item.get("requiredcompetencies", ""),
        match_item.get("maindutiesandresponsibilities", ""),
    ]
    merged = "\n".join(x for x in html_fields if isinstance(x, str) and x.strip())
    if not merged:
        return ""
    soup = BeautifulSoup(merged, "html.parser")
    text = _clean_text(soup.get_text("\n", strip=True))
    return text[:MAX_DESCRIPTION_CHARS]


def _extract_api_based_description_v2(url: str) -> str:
    """Extract job description from API-based recruitment systems (variant 2).

    These systems use RESTful APIs with UUID-based vacancy endpoints.
    """
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if not any(domain in host for domain in API_BASED_V2_DOMAINS):
        return ""
    match = re.search(r"/vacancy/([0-9a-f]{16,32})", parsed.path, flags=re.I)
    if not match:
        return ""

    vacancy_id = match.group(1)
    api_url = f"{parsed.scheme}://{parsed.netloc}/api/Vacancy/{vacancy_id}"

    try:
        resp = requests.get(
            api_url,
            headers={**DEFAULT_HEADERS, "Accept": "application/json, text/plain, */*"},
            timeout=REQUEST_TIMEOUT,
            verify=_verify_ssl(api_url),
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return ""

    if not isinstance(data, dict):
        return ""

    text = _api_payload_to_text(data)
    return text[:MAX_DESCRIPTION_CHARS]


def _api_payload_to_text(data: dict) -> str:
    """Convert API response payload with structured fields to text."""
    sections = []
    section_fields = (
        ("Description", "description"),
        ("Qualifications", "qualifications"),
        ("Skills", "skills"),
        ("Requirements", "requirements"),
        ("Conditions", "conditions"),
    )
    for heading, key in section_fields:
        raw = data.get(key, "")
        if not isinstance(raw, str) or not raw.strip():
            continue
        section_text = _clean_text(
            BeautifulSoup(raw, "html.parser").get_text("\n", strip=True)
        )
        if section_text:
            sections.append(f"{heading}\n{section_text}")

    if sections:
        title = str(data.get("title", "")).strip()
        ref = str(data.get("reference", "")).strip()
        header = "\n".join(x for x in (title, ref) if x)
        return "\n\n".join(([header] if header else []) + sections).strip()

    return ""


def _find_embedded_pdf_link(html: str, page_url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    pdf_link = soup.find("a", href=lambda h: h and ".pdf" in h.lower())
    if pdf_link and pdf_link.get("href"):
        return urljoin(page_url, pdf_link["href"])

    # Adequasys pages often expose "Download PDF" buttons without .pdf in URL.
    for link in soup.find_all("a", href=True):
        text = link.get_text(" ", strip=True).lower()
        if "download pdf" in text or ("pdf" in text and "download" in text):
            return urljoin(page_url, link["href"])

    return ""


def _extract_pdf_candidates(html: str, page_url: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[dict[str, str]] = []
    seen = set()

    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        if not href:
            continue
        text = link.get_text(" ", strip=True)
        lowered = (text + " " + href).lower()
        if (
            ".pdf" not in href.lower()
            and "pdf" not in text.lower()
            and "download pdf" not in lowered
        ):
            continue
        full = urljoin(page_url, href)
        if full in seen:
            continue
        seen.add(full)
        context = link.parent.get_text(" ", strip=True) if link.parent else ""
        candidates.append({"url": full, "text": text, "context": context[:400]})

    # Some sites (e.g. EBA careers) embed vacancy PDF URLs in JSON blobs
    # instead of rendering explicit anchor tags.
    normalized_html = html.replace("\\/", "/")
    raw_urls = re.findall(
        r'https?://[^\s"\'<>]+?\.pdf(?:\?[^\s"\'<>]*)?', normalized_html, flags=re.I
    )
    raw_urls += [
        urljoin(page_url, p)
        for p in re.findall(
            r'/[^\s"\'<>]+?\.pdf(?:\?[^\s"\'<>]*)?', normalized_html, flags=re.I
        )
    ]
    for full in raw_urls:
        if full in seen:
            continue
        seen.add(full)
        candidates.append({"url": full, "text": "", "context": ""})

    return candidates


def _score_pdf_candidate(candidate: dict[str, str], title: str) -> int:
    url = candidate.get("url", "")
    text = candidate.get("text", "")
    context = candidate.get("context", "")
    blob = f"{url} {text} {context}".lower()

    score = 0
    if ".pdf" in url.lower():
        score += 60
    if "download" in blob:
        score += 15

    for marker in PDF_POSITIVE_MARKERS:
        if marker in blob:
            score += 45

    for marker in PDF_NEGATIVE_MARKERS:
        if marker in blob:
            score -= 120
    if ".docx" in url.lower() or ".doc" in url.lower():
        score -= 200
    if "application form" in blob:
        score -= 120

    title_words = _norm_words(title)
    blob_words = _norm_words(blob)
    overlap = len(title_words & blob_words)
    score += min(120, overlap * 20)

    return score


def _select_embedded_pdf_link(
    html: str, page_url: str, title: str, org_abbrev: str
) -> str:
    candidates = _extract_pdf_candidates(html, page_url)
    if not candidates:
        return ""

    scored = sorted(
        ((_score_pdf_candidate(c, title=title), c.get("url", "")) for c in candidates),
        key=lambda x: x[0],
        reverse=True,
    )
    threshold = 30 if (org_abbrev or "").upper() in PREFER_EMBEDDED_PDF_ORGS else 60
    for best_score, best_url in scored:
        if not best_url or best_score < threshold:
            continue
        if detect_content_type(best_url) != "pdf":
            continue
        return best_url
    return ""


def _is_short_or_placeholder(text: str) -> bool:
    words = len((text or "").split())
    if len(text.strip()) < 120 or words < 50:
        return True
    lowered = text.lower()
    return any(marker in lowered for marker in JS_PLACEHOLDER_MARKERS)


def _should_try_playwright(url: str, text: str, html: str) -> bool:
    """Determine if a URL requires JavaScript rendering (Playwright)."""
    host = _url_host(url)
    if any(marker in text.lower() for marker in JS_PLACEHOLDER_MARKERS):
        return True
    if "oraclecloud" in host or any(domain in host for domain in PLAYWRIGHT_DOMAINS):
        return True
    if "enable javascript" in html.lower():
        return True
    return False


def classify_fetch_error(exc: Exception) -> tuple[str, str]:
    """Classify network/enrichment failures into normalized statuses."""
    msg = str(exc).lower()
    if "429" in msg or "too many requests" in msg:
        return "blocked_source", "http_429"
    if "403" in msg or "forbidden" in msg:
        return "blocked_source", "http_403"
    if "404" in msg or "not found" in msg:
        return "broken_link", "http_404"
    if "ssl" in msg or "certificate" in msg:
        return "blocked_source", "ssl_error"
    if "invalid url" in msg or "no scheme supplied" in msg:
        return "broken_link", "invalid_url"
    return "error", "fetch_error"


def fetch_job_content(
    url: str,
    org_abbrev: str,
    title: str,
    use_playwright: bool = False,
    run_id: str = "default",
) -> dict:
    """Fetch content for a single job URL.

    Returns dict with keys: content_type, description, pdf_path.
    """
    if not url:
        return {
            "content_type": "error",
            "description": "",
            "pdf_path": "",
            "enrich_status": "no_detail_url",
            "status_reason": "missing_url",
            "fetch_method": "none",
        }

    if _is_table_row_url(url):
        pdf_path = _download_table_row_pdf(url, org_abbrev, title, run_id)
        return {
            "content_type": "pdf",
            "description": "",
            "pdf_path": pdf_path,
            "enrich_status": "pdf",
            "status_reason": "table_download_button",
            "fetch_method": "playwright",
        }

    content_type = detect_content_type(url)

    if content_type == "pdf":
        pdf_path = download_pdf(url, org_abbrev, title, run_id)
        return {
            "content_type": "pdf",
            "description": "",
            "pdf_path": pdf_path,
            "enrich_status": "pdf",
            "status_reason": "",
            "fetch_method": "http",
        }

    resp = _request(url)
    pdf_link = _select_embedded_pdf_link(
        resp.text, url, title=title, org_abbrev=org_abbrev
    )

    if org_abbrev.upper() in PREFER_EMBEDDED_PDF_ORGS and pdf_link:
        pdf_path = download_pdf(pdf_link, org_abbrev, title, run_id)
        return {
            "content_type": "pdf",
            "description": "",
            "pdf_path": pdf_path,
            "enrich_status": "pdf",
            "status_reason": "embedded_pdf_preferred",
            "fetch_method": "http",
        }

    description = extract_html_description(url, use_playwright=use_playwright)
    if _is_short_or_placeholder(description) and pdf_link:
        pdf_path = download_pdf(pdf_link, org_abbrev, title, run_id)
        return {
            "content_type": "pdf",
            "description": "",
            "pdf_path": pdf_path,
            "enrich_status": "pdf",
            "status_reason": "embedded_pdf",
            "fetch_method": "http",
        }

    if _is_short_or_placeholder(description):
        reason = (
            "js_required"
            if any(m in description.lower() for m in JS_PLACEHOLDER_MARKERS)
            else "short_description"
        )
        status = "js_required" if reason == "js_required" else "short_content"
        return {
            "content_type": "html",
            "description": description,
            "pdf_path": "",
            "enrich_status": status,
            "status_reason": reason,
            "fetch_method": "http",
        }

    return {
        "content_type": "html",
        "description": description,
        "pdf_path": "",
        "enrich_status": "ok",
        "status_reason": "",
        "fetch_method": "http",
    }
