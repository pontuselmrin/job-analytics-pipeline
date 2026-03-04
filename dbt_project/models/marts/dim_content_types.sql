{{
    config(
        materialized='table'
    )
}}

with content_types as (
    select distinct content_type
    from {{ ref('int_jobs_cleaned') }}
    where content_type != ''
)

select
    {{ dbt_utils.generate_surrogate_key(['content_type']) }} as content_type_key,
    content_type
from content_types
