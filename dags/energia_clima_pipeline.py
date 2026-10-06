"""Pipeline diario: extracción REE + Open-Meteo → dbt (bronze → silver → gold)."""
from datetime import date, datetime, timedelta
from pathlib import Path

from airflow.sdk import dag, task
from cosmos import DbtTaskGroup, ExecutionConfig, ProfileConfig, ProjectConfig, RenderConfig
from cosmos.constants import TestBehavior

from include.extract.extract import extract_meteo, extract_ree

DBT_PROJECT = Path("/opt/airflow/dbt_project")


def ventana(dia: str) -> tuple[date, date]:
    """Desde el día 1 del mes de hace 7 días hasta el día objetivo.
    Así se rellenan los días que la API aún no tenía, también al cambiar de mes."""
    fin = date.fromisoformat(dia)
    return (fin - timedelta(days=7)).replace(day=1), fin


@dag(
    schedule="0 6 * * *",              # 06:00 UTC: los datos de ayer ya están publicados
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    max_active_tasks=1,                # DuckDB: un solo escritor
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
    tags=["energia", "dbt", "medallion"],
)
def energia_clima_pipeline():

    @task
    def dia_objetivo(**context) -> str:
        ref = context.get("logical_date") or context["dag_run"].run_after
        return (ref - timedelta(days=1)).date().isoformat()

    @task
    def extraer_ree(dia: str) -> None:
        extract_ree(*ventana(dia))

    @task
    def extraer_meteo(dia: str) -> None:
        extract_meteo(*ventana(dia))
    
        @task.bash
    def exportar_gold() -> str:
        # Usa el Python del venv de dbt, que ya tiene duckdb instalado
        return "/opt/airflow/dbt_venv/bin/python /opt/airflow/include/export/export_gold.py"

    dbt = DbtTaskGroup(
        group_id="dbt",
        project_config=ProjectConfig(DBT_PROJECT, install_dbt_deps=False),
        profile_config=ProfileConfig(
            profile_name="energia_clima",
            target_name="dev",
            profiles_yml_filepath=DBT_PROJECT / "profiles.yml",
        ),
        execution_config=ExecutionConfig(dbt_executable_path="/opt/airflow/dbt_venv/bin/dbt"),
        render_config=RenderConfig(test_behavior=TestBehavior.AFTER_EACH),
    )

    dia = dia_objetivo()
    [extraer_ree(dia), extraer_meteo(dia)] >> dbt >> exportar_gold()


energia_clima_pipeline()
