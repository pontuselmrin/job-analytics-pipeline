select
    org_abbrev,
    org_name,
    enriched_at
from {{ source('raw', 'organizations') }}
