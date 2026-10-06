FROM apache/airflow:3.3.2-python3.12

# Cosmos en el entorno de Airflow
RUN pip install --no-cache-dir "apache-airflow==${AIRFLOW_VERSION}" "astronomer-cosmos>=1.15,<2"

# dbt aislado en su propio venv, con las mismas versiones que en local
RUN python -m venv /opt/airflow/dbt_venv \
 && /opt/airflow/dbt_venv/bin/pip install --no-cache-dir dbt-core==1.12.5 dbt-duckdb==1.11.0
