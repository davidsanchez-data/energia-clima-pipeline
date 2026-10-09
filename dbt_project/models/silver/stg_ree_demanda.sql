{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='fecha',
    on_schema_change='fail'
) }}

with valores as (
    select
        _extracted_at,
        unnest(from_json(
            payload -> '$.included[0].attributes.values',
            '[{"value": "DOUBLE", "datetime": "VARCHAR"}]'
        )) as v
    from {{ ref('brz_ree_demanda') }}
    {% if is_incremental() %}
    -- solo los ficheros extraídos después de la última carga
    where _extracted_at > (select max(_extracted_at) from {{ this }})
    {% endif %}
),

tipado as (
    select
        left(v.datetime, 10)::date as fecha,   -- fecha local, sin pasar por UTC
        v.value                    as demanda_mwh,
        _extracted_at
    from valores
)

select * from tipado
qualify row_number() over (partition by fecha order by _extracted_at desc) = 1
