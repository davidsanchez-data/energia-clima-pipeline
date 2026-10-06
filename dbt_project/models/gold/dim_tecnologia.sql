select distinct
    md5(tecnologia) as tecnologia_id,
    tecnologia,
    tipo_renovable
from {{ ref('stg_ree_generacion') }}
