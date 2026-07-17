
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(
    page_title="Intake Load Status Dashboard",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Intake Load Status Dashboard")
st.caption("Metrics are calculated only for records with status = COMPLETED")

DEFAULT_FILE = "merged_loadstatus_records.csv"

uploaded_file = st.sidebar.file_uploader("Upload intake load status CSV", type=["csv"])

@st.cache_data
def load_data(file):
    return pd.read_csv(file)

if uploaded_file is not None:
    df = load_data(uploaded_file)
else:
    try:
        df = load_data(DEFAULT_FILE)
    except FileNotFoundError:
        st.warning("Please upload the CSV file or keep merged_loadstatus_records.csv in the same folder as this app.")
        st.stop()

required_cols = {"source_table", "status", "processed_row_count", "start_timestamp", "updated_ts"}
missing_cols = required_cols - set(df.columns)

if missing_cols:
    st.error(f"Missing required columns: {missing_cols}")
    st.stop()

# Clean and prepare data
df["status"] = df["status"].astype(str).str.upper().str.strip()
df["processed_row_count"] = pd.to_numeric(df["processed_row_count"], errors="coerce")
df["start_timestamp"] = pd.to_datetime(df["start_timestamp"], errors="coerce", utc=True)
df["updated_ts"] = pd.to_datetime(df["updated_ts"], errors="coerce", utc=True)

completed_df = df[df["status"] == "COMPLETED"].copy()

completed_df = completed_df.dropna(
    subset=["processed_row_count", "start_timestamp", "updated_ts"]
)

completed_df["duration_minutes"] = (
    completed_df["updated_ts"] - completed_df["start_timestamp"]
).dt.total_seconds() / 60

completed_df["duration_hours"] = completed_df["duration_minutes"] / 60

completed_df["institution"] = completed_df["source_table"].str.replace(
    "_intake_loadstatus",
    "",
    regex=False
)

# Optional filters
st.sidebar.header("Filters")

if "table_source" in completed_df.columns:
    table_sources = sorted(completed_df["table_source"].dropna().unique())
    selected_sources = st.sidebar.multiselect(
        "Table Source",
        table_sources,
        default=table_sources
    )
    completed_df = completed_df[completed_df["table_source"].isin(selected_sources)]

if "table_type" in completed_df.columns:
    table_types = sorted(completed_df["table_type"].dropna().unique())
    selected_types = st.sidebar.multiselect(
        "Table Type",
        table_types,
        default=table_types
    )
    completed_df = completed_df[completed_df["table_type"].isin(selected_types)]

if completed_df.empty:
    st.warning("No COMPLETED records available after applying filters.")
    st.stop()

# Calculations
def metric_summary(series):
    return {
        "25th Percentile": series.quantile(0.25),
        "Median": series.quantile(0.50),
        "75th Percentile": series.quantile(0.75),
        "90th Percentile": series.quantile(0.90),
        "Max": series.max()
    }

duration_summary = metric_summary(completed_df["duration_minutes"])
record_summary = metric_summary(completed_df["processed_row_count"])

st.subheader("Overall Summary")

col1, col2, col3, col4 = st.columns(4)

col1.metric("Total Rows", f"{len(df):,}")
col2.metric("Completed Rows", f"{len(completed_df):,}")
col3.metric("Median Duration", f"{duration_summary['Median']:.2f} min")
col4.metric("Median Records Written", f"{record_summary['Median']:,.0f}")

st.divider()

st.subheader("Requested Metrics")

left, right = st.columns(2)

with left:
    st.markdown("#### Intake Job Duration to Write to Edify")

    duration_table = pd.DataFrame({
        "Metric": list(duration_summary.keys()),
        "Minutes": [round(v, 2) for v in duration_summary.values()],
        "Hours": [round(v / 60, 2) for v in duration_summary.values()]
    })

    st.dataframe(
        duration_table,
        use_container_width=True,
        hide_index=True
    )

with right:
    st.markdown("#### Records Written in Intake")

    record_table = pd.DataFrame({
        "Metric": list(record_summary.keys()),
        "Records": [f"{v:,.0f}" for v in record_summary.values()]
    })

    st.dataframe(
        record_table,
        use_container_width=True,
        hide_index=True
    )

st.divider()

st.subheader("Visual Analysis")

viz1, viz2 = st.columns(2)

with viz1:
    fig_duration = px.box(
        completed_df,
        y="duration_minutes",
        points="all",
        hover_data=["institution", "processed_row_count"],
        title="Distribution of Intake Job Duration"
    )

    fig_duration.update_layout(
        yaxis_title="Duration in Minutes"
    )

    st.plotly_chart(
        fig_duration,
        use_container_width=True
    )

with viz2:
    fig_records = px.box(
        completed_df,
        y="processed_row_count",
        points="all",
        hover_data=["institution", "duration_minutes"],
        title="Distribution of Records Written"
    )

    fig_records.update_layout(
        yaxis_title="Processed Row Count"
    )

    st.plotly_chart(
        fig_records,
        use_container_width=True
    )

st.subheader("Duration vs Records Written")

fig_scatter = px.scatter(
    completed_df,
    x="processed_row_count",
    y="duration_minutes",
    hover_name="institution",
    color="table_source" if "table_source" in completed_df.columns else None,
    size="processed_row_count",
    title="Job Duration Compared with Records Written"
)

fig_scatter.update_layout(
    xaxis_title="Processed Row Count",
    yaxis_title="Duration in Minutes"
)

st.plotly_chart(
    fig_scatter,
    use_container_width=True
)

st.subheader("Completed Intake Job Details")

display_cols = [
    "institution",
    "source_table",
    "table_type",
    "table_source",
    "status",
    "processed_row_count",
    "start_timestamp",
    "updated_ts",
    "duration_minutes",
    "duration_hours"
]

display_cols = [c for c in display_cols if c in completed_df.columns]

show_df = completed_df[display_cols].sort_values(
    "duration_minutes",
    ascending=False
).copy()

show_df["duration_minutes"] = show_df["duration_minutes"].round(2)
show_df["duration_hours"] = show_df["duration_hours"].round(2)

st.dataframe(
    show_df,
    use_container_width=True,
    hide_index=True
)

csv = show_df.to_csv(index=False).encode("utf-8")

st.download_button(
    label="Download Completed Records with Duration",
    data=csv,
    file_name="completed_intake_duration_metrics.csv",
    mime="text/csv"
)
