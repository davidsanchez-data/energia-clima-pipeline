with valores as (
    select
        _extracted_at,
        unnest(from_json(
            payload -> '$.included[0].attributes.values',
            '[{"value": "DOUBLE", "datetime": "VARCHAR"}]'
        )) as v
    from {{ ref('brz_ree_demanda') }}
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
