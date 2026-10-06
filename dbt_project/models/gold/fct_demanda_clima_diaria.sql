with demanda as (
    select fecha, demanda_mwh from {{ ref('stg_ree_demanda') }}
),

clima as (
    -- media de las 5 ciudades como aproximación nacional
    select
        fecha,
        round(avg(temp_media_c), 2)     as temp_media_c,
        max(temp_max_c)                 as temp_max_c,
        min(temp_min_c)                 as temp_min_c,
        round(avg(precipitacion_mm), 2) as precipitacion_media_mm
    from {{ ref('stg_meteo_diario') }}
    group by fecha
),

generacion as (
    select
        fecha,
        sum(generacion_mwh) filter (where tipo_renovable = 'Renovable') as generacion_renovable_mwh,
        sum(generacion_mwh)                                            as generacion_total_mwh
    from {{ ref('stg_ree_generacion') }}
    group by fecha
)

select
    d.fecha,
    d.demanda_mwh,
    c.temp_media_c,
    c.temp_max_c,
    c.temp_min_c,
    c.precipitacion_media_mm,
    greatest(18 - c.temp_media_c, 0) as grados_dia_calefaccion,
    greatest(c.temp_media_c - 18, 0) as grados_dia_refrigeracion,
    g.generacion_renovable_mwh,
    g.generacion_total_mwh,
    round(g.generacion_renovable_mwh / nullif(g.generacion_total_mwh, 0) * 100, 2) as pct_renovable
from demanda d
left join clima c      using (fecha)
left join generacion g using (fecha)
