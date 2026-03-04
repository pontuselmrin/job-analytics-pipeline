{{
    config(
        materialized='table'
    )
}}

with jobs as (
    select * from {{ ref('stg_jobs') }}
),

boilerplate as (
    select
        org_abbrev,
        lower(sentence) as sentence
    from {{ source('raw', 'boilerplate_sentences') }}
),

sentences as (
    select
        j.id,
        j.org_abbrev,
        j.title,
        j.url,
        j.content_type,
        j.description,
        j.pdf_path,
        j.enriched_at,
        j.enrich_status,
        j.status_reason,
        j.fetch_method,
        j.fetch_seconds,
        trim(s.sentence) as sentence,
        s.ordinality as sentence_order
    from jobs j,
    lateral regexp_split_to_table(j.description, E'(?<=[.!?])\\s+|\\n+') with ordinality as s(sentence, ordinality)
),

filtered as (
    select
        s.*
    from sentences s
    left join boilerplate b
        on s.org_abbrev = b.org_abbrev
        and lower(trim(regexp_replace(s.sentence, '\\s+', ' ', 'g'))) = b.sentence
    where b.sentence is null
),

reassembled as (
    select
        id,
        coalesce(
            regexp_replace(
                string_agg(sentence, '. ' order by sentence_order),
                '\s{3,}', '  ', 'g'
            ),
            ''
        ) as description_clean
    from filtered
    group by id
),

final as (
    select
        j.id,
        j.org_abbrev,
        j.title,
        j.url,
        j.content_type,
        coalesce(r.description_clean, '') as description_clean,
        array_length(
            string_to_array(
                trim(regexp_replace(j.description, '\s+', ' ', 'g')),
                ' '
            ),
            1
        ) as description_word_count,
        j.pdf_path,
        j.enriched_at,
        j.enrich_status,
        j.status_reason,
        j.fetch_method,
        j.fetch_seconds
    from jobs j
    left join reassembled r on j.id = r.id
)

select * from final
