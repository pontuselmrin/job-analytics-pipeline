{{
    config(
        materialized='table'
    )
}}

with orgs as (
    select * from {{ ref('stg_organizations') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['org_abbrev']) }} as org_key,
    org_abbrev,
    org_name,
    enriched_at
from orgs
