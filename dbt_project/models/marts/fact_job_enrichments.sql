{{
    config(
        materialized='table'
    )
}}

with jobs as (
    select * from {{ ref('int_jobs_cleaned') }}
),

dim_orgs as (
    select * from {{ ref('dim_organizations') }}
),

dim_ct as (
    select * from {{ ref('dim_content_types') }}
),

dim_es as (
    select * from {{ ref('dim_enrich_statuses') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['jobs.id']) }} as job_key,
    dim_orgs.org_key,
    dim_ct.content_type_key,
    dim_es.status_key,
    jobs.title,
    jobs.url,
    jobs.description_clean,
    jobs.description_word_count,
    jobs.pdf_path,
    jobs.fetch_method,
    jobs.fetch_seconds,
    jobs.enriched_at
from jobs
left join dim_orgs on jobs.org_abbrev = dim_orgs.org_abbrev
left join dim_ct on jobs.content_type = dim_ct.content_type
left join dim_es
    on jobs.enrich_status = dim_es.enrich_status
    and jobs.status_reason = dim_es.status_reason
