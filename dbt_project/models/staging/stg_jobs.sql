select
    id,
    org_abbrev,
    title,
    url,
    content_type,
    description,
    pdf_path,
    enriched_at,
    enrich_error,
    enrich_status,
    status_reason,
    fetch_method,
    fetch_seconds
from {{ source('raw', 'jobs') }}
where enrich_status != 'error'
