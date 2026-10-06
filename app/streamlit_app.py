"""Dashboard: Energía y Clima en España (capa gold exportada a Parquet)."""
from pathlib import Path

import altair as alt
import duckdb
import pandas as pd
import streamlit as st

DATA = Path(__file__).parent / "data"
AZUL, NARANJA, AQUA, GRIS = "#2a78d6", "#eb6834", "#1baf7a", "#a3a29c"
PALETA = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7"]

st.set_page_config(page_title="Energía y Clima en España", page_icon="⚡", layout="wide")


# ---------- Acceso a datos ----------
@st.cache_resource
def conexion() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    for f in sorted(DATA.glob("*.parquet")):
        con.sql(f"create view {f.stem} as select * from read_parquet('{f.as_posix()}')")
    return con


@st.cache_data
def consulta(sql: str) -> pd.DataFrame:
    """Único punto de acceso a datos. Para Streamlit in Snowflake solo cambia esta función."""
    return conexion().cursor().sql(sql).df()


def miles(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


# ---------- Cabecera y filtros ----------
st.title("⚡ Energía y Clima en España")
st.caption("Demanda y generación eléctrica (Red Eléctrica) y meteorología (Open-Meteo) · "
           "Pipeline: Airflow + dbt + DuckDB")

lim = consulta("select min(fecha) as ini, max(fecha) as fin from fct_demanda_clima_diaria")
fecha_min = pd.to_datetime(lim["ini"][0]).date()
fecha_max = pd.to_datetime(lim["fin"][0]).date()

with st.sidebar:
    st.header("Filtros")
    periodo = st.date_input("Periodo", (fecha_min, fecha_max),
                            min_value=fecha_min, max_value=fecha_max, format="DD/MM/YYYY")
    st.caption(f"Datos hasta el {fecha_max:%d/%m/%Y}")
    st.markdown("[Código en GitHub](https://github.com/davidsanchez-data/energia-clima-pipeline)")

if len(periodo) != 2:
    st.info("Selecciona también la fecha final del periodo.")
    st.stop()
ini, fin = periodo

diario = consulta(f"""
    select f.fecha,
           f.demanda_mwh / 1000 as demanda_gwh,
           f.temp_media_c,
           f.generacion_renovable_mwh,
           f.generacion_total_mwh,
           d.nombre_dia,
           d.estacion,
           case when d.es_fin_de_semana then 'Fin de semana' else 'Laborable' end as tipo_dia
    from fct_demanda_clima_diaria f
    join dim_fecha d using (fecha)
    where f.fecha between '{ini}' and '{fin}'
    order by f.fecha
""")

if diario.empty:
    st.warning("No hay datos en el periodo seleccionado.")
    st.stop()

# ---------- KPIs ----------
pico = diario.loc[diario["demanda_gwh"].idxmax()]
pct_ren = diario["generacion_renovable_mwh"].sum() / diario["generacion_total_mwh"].sum() * 100

k1, k2, k3, k4 = st.columns(4)
k1.metric("Demanda media diaria", f"{miles(diario['demanda_gwh'].mean())} GWh")
k2.metric("Cuota renovable", f"{pct_ren:.1f} %")
k3.metric("Máxima demanda", f"{miles(pico['demanda_gwh'])} GWh")
k3.caption(f"{pico['nombre_dia']} {pd.to_datetime(pico['fecha']):%d/%m/%Y}")
k4.metric("Temperatura media", f"{diario['temp_media_c'].mean():.1f} °C")

tab_evol, tab_clima, tab_mix, tab_datos = st.tabs(
    ["📈 Evolución", "🌡️ Demanda y clima", "🔋 Mix de generación", "📋 Datos"])

# ---------- Evolución ----------
with tab_evol:
    diario["media_7d"] = diario["demanda_gwh"].rolling(7, min_periods=1).mean()
    base = alt.Chart(diario).encode(x=alt.X("fecha:T", title=None))
    diaria = base.mark_line(color=GRIS, strokeWidth=1, opacity=0.7).encode(
        y=alt.Y("demanda_gwh:Q", title="GWh/día", scale=alt.Scale(zero=False)),
        tooltip=[alt.Tooltip("fecha:T", title="Fecha", format="%d/%m/%Y"),
                 alt.Tooltip("nombre_dia:N", title="Día"),
                 alt.Tooltip("demanda_gwh:Q", title="Demanda (GWh)", format=",.0f")])
    media = base.mark_line(color=AZUL, strokeWidth=2).encode(y="media_7d:Q")
    st.altair_chart(diaria + media)
    st.caption("Gris: demanda diaria · Azul: media móvil de 7 días. "
               "Los dientes de sierra son los fines de semana; los valles aislados, festivos.")

# ---------- Demanda y clima ----------
with tab_clima:
    con_clima = diario.dropna(subset=["temp_media_c"])
    color = alt.Color("tipo_dia:N", title=None,
                      scale=alt.Scale(domain=["Laborable", "Fin de semana"], range=[AZUL, NARANJA]),
                      legend=alt.Legend(orient="top"))
    puntos = alt.Chart(con_clima).mark_circle(size=60, opacity=0.6).encode(
        x=alt.X("temp_media_c:Q", title="Temperatura media nacional (°C)"),
        y=alt.Y("demanda_gwh:Q", title="Demanda (GWh/día)", scale=alt.Scale(zero=False)),
        color=color,
        tooltip=[alt.Tooltip("fecha:T", title="Fecha", format="%d/%m/%Y"),
                 alt.Tooltip("nombre_dia:N", title="Día"),
                 alt.Tooltip("temp_media_c:Q", title="Temp. (°C)", format=".1f"),
                 alt.Tooltip("demanda_gwh:Q", title="Demanda (GWh)", format=",.0f")])
    tendencia = (alt.Chart(con_clima)
                 .transform_loess("temp_media_c", "demanda_gwh", groupby=["tipo_dia"])
                 .mark_line(strokeWidth=2)
                 .encode(x="temp_media_c:Q", y="demanda_gwh:Q", color=color))
    st.altair_chart(puntos + tendencia)
    st.caption("La curva en «U» muestra que la demanda sube tanto con el frío (calefacción) "
               "como con el calor (refrigeración). Los fines de semana se desplaza hacia abajo "
               "por la menor actividad industrial y comercial.")

# ---------- Mix de generación ----------
with tab_mix:
    mix = consulta(f"""
        select date_trunc('week', g.fecha) as semana, t.tecnologia,
               sum(g.generacion_mwh) / 1000 as gwh
        from fct_generacion_diaria g
        join dim_tecnologia t using (tecnologia_id)
        where g.fecha between '{ini}' and '{fin}'
        group by all
    """)
    top = mix.groupby("tecnologia")["gwh"].sum().nlargest(7).index.tolist()
    orden = top + ["Resto"]
    mix["tecnologia"] = mix["tecnologia"].where(mix["tecnologia"].isin(top), "Resto")
    mix = mix.groupby(["semana", "tecnologia"], as_index=False)["gwh"].sum()
    mix["orden"] = mix["tecnologia"].map({t: i for i, t in enumerate(orden)})

    area = alt.Chart(mix).mark_area().encode(
        x=alt.X("semana:T", title=None),
        y=alt.Y("gwh:Q", stack=True, title="GWh/semana"),
        color=alt.Color("tecnologia:N", title=None, sort=orden,
                        scale=alt.Scale(domain=orden, range=PALETA[:len(top)] + [GRIS])),
        order=alt.Order("orden:Q"),
        tooltip=[alt.Tooltip("semana:T", title="Semana", format="%d/%m/%Y"),
                 alt.Tooltip("tecnologia:N", title="Tecnología"),
                 alt.Tooltip("gwh:Q", title="GWh", format=",.0f")])
    st.subheader("Generación semanal por tecnología")
    st.altair_chart(area)

    mensual = consulta(f"""
        select date_trunc('month', fecha) as mes,
               sum(generacion_renovable_mwh) / sum(generacion_total_mwh) * 100 as pct_renovable
        from fct_demanda_clima_diaria
        where fecha between '{ini}' and '{fin}'
        group by all order by mes
    """)
    linea = alt.Chart(mensual).mark_line(color=AQUA, strokeWidth=2, point=alt.OverlayMarkDef(size=60)).encode(
        x=alt.X("mes:T", title=None, axis=alt.Axis(format="%b %Y")),
        y=alt.Y("pct_renovable:Q", title="% renovable", scale=alt.Scale(domain=[0, 100])),
        tooltip=[alt.Tooltip("mes:T", title="Mes", format="%m/%Y"),
                 alt.Tooltip("pct_renovable:Q", title="% renovable", format=".1f")])
    st.subheader("Cuota renovable mensual")
    st.altair_chart(linea)

# ---------- Datos ----------
with tab_datos:
    st.dataframe(diario.drop(columns=["media_7d"], errors="ignore"), hide_index=True)
    st.download_button("Descargar CSV", diario.to_csv(index=False).encode("utf-8"),
                       file_name="energia_clima_diario.csv", mime="text/csv")
