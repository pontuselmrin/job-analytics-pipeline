{{
    config(
        materialized='table'
    )
}}

with statuses as (
    select distinct
        enrich_status,
        status_reason
    from {{ ref('int_jobs_cleaned') }}
    where enrich_status != ''
)

select
    {{ dbt_utils.generate_surrogate_key(['enrich_status', 'status_reason']) }} as status_key,
    enrich_status,
    status_reason
from statuses
