import os
from datetime import date

import pandas as pd
import streamlit as st
from google.cloud import bigquery


DEFAULT_PROJECT_ID = os.getenv("BIGQUERY_PROJECT_ID", "")
DEFAULT_DATASET_ID = os.getenv("BIGQUERY_DATASET_ID", "dbt_iso_ne")


def build_default_table_name(project_id: str, dataset_id: str, table_id: str) -> str:
    if not project_id:
        return ""
    return f"{project_id}.{dataset_id}.{table_id}"


DEFAULT_DAILY_SUMMARY_TABLE = os.getenv("STREAMLIT_DAILY_SUMMARY_TABLE") or build_default_table_name(
    DEFAULT_PROJECT_ID,
    DEFAULT_DATASET_ID,
    "mrt_daily_lmp_summary_by_location",
)
DEFAULT_HOURLY_MART_TABLE = os.getenv("STREAMLIT_HOURLY_MART_TABLE") or build_default_table_name(
    DEFAULT_PROJECT_ID,
    DEFAULT_DATASET_ID,
    "mrt_hourly_lmp_by_location",
)


@st.cache_resource(show_spinner=False)
def get_bigquery_client(project_id: str) -> bigquery.Client:
    return bigquery.Client(project=project_id)


@st.cache_data(ttl=300, show_spinner=False)
def load_market_dates(project_id: str, table_name: str) -> list[date]:
    client = get_bigquery_client(project_id)
    query = f"""
        SELECT DISTINCT market_date
        FROM `{table_name}`
        ORDER BY market_date DESC
    """
    dataframe = client.query(query).to_dataframe()
    if dataframe.empty:
        return []
    return dataframe["market_date"].tolist()


@st.cache_data(ttl=300, show_spinner=False)
def load_daily_summary(project_id: str, table_name: str, market_date: date) -> pd.DataFrame:
    client = get_bigquery_client(project_id)
    query = f"""
        SELECT
          market_date,
          location_name,
          avg_lmp_total_day,
          peak_hourly_lmp_total,
          peak_window_start,
          peak_window_end,
          hours_included,
          source_rows_included
        FROM `{table_name}`
        WHERE market_date = @market_date
        ORDER BY peak_hourly_lmp_total DESC, location_name ASC
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("market_date", "DATE", market_date.isoformat())
        ]
    )
    return client.query(query, job_config=job_config).to_dataframe()


@st.cache_data(ttl=300, show_spinner=False)
def load_hourly_location_series(
    project_id: str,
    table_name: str,
    market_date: date,
    location_name: str,
) -> pd.DataFrame:
    client = get_bigquery_client(project_id)
    query = f"""
        SELECT
          window_start,
          window_end,
          avg_lmp_total,
          max_lmp_total,
          row_count
        FROM `{table_name}`
        WHERE DATE(DATETIME(window_start, 'America/New_York')) = @market_date
          AND location_name = @location_name
        ORDER BY window_start ASC
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("market_date", "DATE", market_date.isoformat()),
            bigquery.ScalarQueryParameter("location_name", "STRING", location_name),
        ]
    )
    return client.query(query, job_config=job_config).to_dataframe()


def render_summary_metrics(dataframe: pd.DataFrame) -> None:
    top_row = dataframe.iloc[0]
    locations_count = int(dataframe["location_name"].nunique())
    mean_daily_lmp = float(dataframe["avg_lmp_total_day"].mean())

    metric_columns = st.columns(3)
    metric_columns[0].metric("Locations", f"{locations_count:,}")
    metric_columns[1].metric("Average Daily LMP", f"{mean_daily_lmp:.2f}")
    metric_columns[2].metric(
        "Highest Peak Hour",
        f"{top_row['peak_hourly_lmp_total']:.2f}",
        delta=top_row["location_name"],
    )


def main() -> None:
    st.set_page_config(page_title="GridPulse Analytics", layout="wide")

    st.title("GridPulse Analytics")
    st.caption(
        "Streaming-first ISO-NE electricity market analytics backed by "
        "dbt_iso_ne.mrt_daily_lmp_summary_by_location."
    )

    with st.sidebar:
        st.header("Configuration")
        project_id = st.text_input("BigQuery project", value=DEFAULT_PROJECT_ID)
        table_name = st.text_input(
            "Daily summary table",
            value=DEFAULT_DAILY_SUMMARY_TABLE,
        )
        hourly_table_name = st.text_input(
            "Hourly mart table",
            value=DEFAULT_HOURLY_MART_TABLE,
        )

    if not project_id or not table_name or not hourly_table_name:
        st.info(
            "Set BIGQUERY_PROJECT_ID or enter the BigQuery project and mart table names in the "
            "sidebar before querying the dashboard."
        )
        st.stop()

    try:
        market_dates = load_market_dates(project_id, table_name)
    except Exception as exc:
        st.error(
            "Unable to query BigQuery. Set GOOGLE_APPLICATION_CREDENTIALS or another "
            f"valid Google auth path before running the dashboard.\n\nDetails: {exc}"
        )
        st.stop()

    if not market_dates:
        st.warning("No market dates were returned from the configured table.")
        st.stop()

    selected_market_date = st.selectbox("Market date", market_dates, index=0)
    top_n = st.slider("Top rows to display", min_value=10, max_value=100, value=25, step=5)

    summary_dataframe = load_daily_summary(project_id, table_name, selected_market_date)
    if summary_dataframe.empty:
        st.warning("The selected market date returned no rows.")
        st.stop()

    render_summary_metrics(summary_dataframe)

    st.subheader("Tile 1: Categorical Distribution")
    st.caption("Top locations ranked by average daily LMP for the selected market date.")
    categorical_chart = (
        summary_dataframe[["location_name", "avg_lmp_total_day"]]
        .sort_values(by="avg_lmp_total_day", ascending=False)
        .head(top_n)
        .set_index("location_name")
    )
    st.bar_chart(categorical_chart)

    location_options = summary_dataframe["location_name"].sort_values().tolist()
    default_location = summary_dataframe.iloc[0]["location_name"]
    selected_location = st.selectbox(
        "Location for hourly trend",
        location_options,
        index=location_options.index(default_location),
    )

    hourly_series = load_hourly_location_series(
        project_id,
        hourly_table_name,
        selected_market_date,
        selected_location,
    )

    st.subheader("Tile 2: Temporal Distribution")
    st.caption(
        "Hourly average LMP across the selected ISO-NE market day for one location."
    )
    if hourly_series.empty:
        st.warning("No hourly rows were returned for the selected market date and location.")
    else:
        hourly_chart = hourly_series[["window_start", "avg_lmp_total"]].set_index("window_start")
        st.line_chart(hourly_chart)

    left_column, right_column = st.columns(2)

    with left_column:
        st.subheader("Highest Peak Hourly LMP")
        st.dataframe(
            summary_dataframe[
                [
                    "location_name",
                    "peak_hourly_lmp_total",
                    "peak_window_start",
                    "peak_window_end",
                    "hours_included",
                ]
            ].head(top_n),
            hide_index=True,
            use_container_width=True,
        )

    with right_column:
        st.subheader("Highest Average Daily LMP")
        st.dataframe(
            summary_dataframe[
                [
                    "location_name",
                    "avg_lmp_total_day",
                    "source_rows_included",
                    "hours_included",
                ]
            ]
            .sort_values(by="avg_lmp_total_day", ascending=False)
            .head(top_n),
            hide_index=True,
            use_container_width=True,
        )

    st.subheader("Underlying Daily Summary Rows")
    st.dataframe(summary_dataframe.head(top_n), hide_index=True, use_container_width=True)

    if not hourly_series.empty:
        st.subheader("Underlying Hourly Trend Rows")
        st.dataframe(hourly_series, hide_index=True, use_container_width=True)


if __name__ == "__main__":
    main()