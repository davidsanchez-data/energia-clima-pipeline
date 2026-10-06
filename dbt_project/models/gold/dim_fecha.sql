with rango as (
    select min(fecha) as d0, max(fecha) as d1 from {{ ref('stg_ree_demanda') }}
),

fechas as (
    select unnest(generate_series(d0, d1, interval 1 day))::date as fecha from rango
)

select
    fecha,
    year(fecha)    as anio,
    quarter(fecha) as trimestre,
    month(fecha)   as mes,
    ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto',
     'Septiembre','Octubre','Noviembre','Diciembre'][month(fecha)] as nombre_mes,
    isodow(fecha)  as dia_semana,
    ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo'][isodow(fecha)] as nombre_dia,
    isodow(fecha) >= 6 as es_fin_de_semana,
    case
        when month(fecha) in (12, 1, 2) then 'Invierno'
        when month(fecha) in (3, 4, 5)  then 'Primavera'
        when month(fecha) in (6, 7, 8)  then 'Verano'
        else 'Otoño'
    end as estacion
from fechas
