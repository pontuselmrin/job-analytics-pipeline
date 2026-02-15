"""Organization-specific configuration template.

Copy this file to org_config.py and fill in your own organization lists.
"""

# Organizations whose detail pages require JavaScript rendering (Playwright)
# Add organizations that use client-side rendering frameworks
PLAYWRIGHT_ORGS = {
    # Example: "ORG_ABBREV",
}

# Domains that require JavaScript rendering for detail pages
PLAYWRIGHT_DOMAINS = {
    # Example: "careers.example.com",
}

# Domains built on Next.js or similar frameworks
NEXTJS_PLATFORMS = {
    # Example: "jobs.example.com",
}

# Domains using a specific ATS platform (variant A)
PLATFORM_A_DOMAINS = {
    # Example: "example.com",
}

# Domains with a JSON API (v1 schema)
API_BASED_V1_DOMAINS = {
    # Example: "api.example.com",
}

# Domains with a JSON API (v2 schema)
API_BASED_V2_DOMAINS = {
    # Example: "api.example.com",
}

# Domains that render job listings in HTML tables
TABLE_INTERFACE_DOMAINS = {
    # Example: "careers.example.com",
}

# Organizations where embedded PDF descriptions are preferred over HTML
PREFER_EMBEDDED_PDF_ORGS = {
    # Example: "ORG_ABBREV",
}

# Domains with SSL certificate issues (disable verification)
SSL_INSECURE_DOMAINS = {
    # Example: "legacy.example.com",
}
