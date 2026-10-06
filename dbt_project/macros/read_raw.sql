{% macro read_raw(source_name) %}
select
    filename                                   as _source_file,
    (json ->> '$.extracted_at')::timestamptz   as _extracted_at,
    json -> '$.payload'                        as payload
from read_json_objects('{{ var("raw_path") }}/{{ source_name }}/*.json', filename = true)
{% endmacro %}
