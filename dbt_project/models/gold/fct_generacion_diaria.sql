select
    fecha,
    md5(tecnologia) as tecnologia_id,
    generacion_mwh,
    cuota_mix
from {{ ref('stg_ree_generacion') }}
