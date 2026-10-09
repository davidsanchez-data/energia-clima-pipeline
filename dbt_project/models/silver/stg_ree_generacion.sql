{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['fecha', 'tecnologia'],
    on_schema_change='fail'
) }}

with tecnologias as (
    select
        _extracted_at,
        unnest(from_json(
            payload -> '$.included',
            '[{"attributes": {"title": "VARCHAR", "type": "VARCHAR",
               "values": [{"value": "DOUBLE", "percentage": "DOUBLE", "datetime": "VARCHAR"}]}}]'
        )) as t
    from {{ ref('brz_ree_generacion') }}
    {% if is_incremental() %}
    -- solo los ficheros extraídos después de la última carga
    where _extracted_at > (select max(_extracted_at) from {{ this }})
    {% endif %}
),

valores as (
    select
        _extracted_at,
        t.attributes.title as tecnologia,
        t.attributes.type  as tipo_renovable,
        unnest(t.attributes."values") as v
    from tecnologias
),

tipado as (
    select
        left(v.datetime, 10)::date as fecha,   -- fecha local, sin pasar por UTC
        tecnologia,
        tipo_renovable,
        v.value      as generacion_mwh,
        v.percentage as cuota_mix,             -- fracción 0-1 sobre el total del día
        _extracted_at
    from valores
    where tecnologia not ilike '%total%'
)

select * from tipado
qualify row_number() over (partition by fecha, tecnologia order by _extracted_at desc) = 1
