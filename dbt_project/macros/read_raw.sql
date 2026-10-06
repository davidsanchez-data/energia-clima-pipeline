{% macro read_raw(source_name) %}
{% set raw_path = env_var('DBT_RAW_PATH', var('raw_path')) %}
select
    filename                                   as _source_file,
    (json ->> '$.extracted_at')::timestamptz   as _extracted_at,
    json -> '$.payload'                        as payload
from read_json_objects('{{ raw_path }}/{{ source_name }}/*.json', filename = true)
{% endmacro %}
