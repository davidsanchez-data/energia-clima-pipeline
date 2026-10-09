{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['ciudad', 'fecha'],
    on_schema_change='fail'
) }}

with ciudades as (
    select
        _extracted_at,
        unnest(from_json(payload,
            '[{"ciudad": "VARCHAR",
               "daily": {"time": ["VARCHAR"],
                         "temperature_2m_max": ["DOUBLE"],
                         "temperature_2m_min": ["DOUBLE"],
                         "temperature_2m_mean": ["DOUBLE"],
                         "precipitation_sum": ["DOUBLE"]}}]'
        )) as c
    from {{ ref('brz_meteo_diario') }}
    {% if is_incremental() %}
    -- solo los ficheros extraídos después de la última carga
    where _extracted_at > (select max(_extracted_at) from {{ this }})
    {% endif %}
),

dias as (
    select
        _extracted_at,
        c.ciudad,
        unnest(c.daily."time")::date          as fecha,
        unnest(c.daily.temperature_2m_max)    as temp_max_c,
        unnest(c.daily.temperature_2m_min)    as temp_min_c,
        unnest(c.daily.temperature_2m_mean)   as temp_media_c,
        unnest(c.daily.precipitation_sum)     as precipitacion_mm
    from ciudades
)

select * from dias
qualify row_number() over (partition by ciudad, fecha order by _extracted_at desc) = 1
