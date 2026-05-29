from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from scripts.create_database import DB_PATH, build_database


st.set_page_config(
    page_title="SQL Slippage Risk Dashboard",
    layout="wide",
)

TECH_TEMPLATE = "plotly_white"
PANEL_BG = "rgba(8, 19, 46, 0.96)"
PAPER_BG = "rgba(8, 19, 46, 0.96)"
GRID_COLOR = "rgba(125, 211, 252, 0.18)"
FONT_COLOR = "#f8fbff"


def apply_institutional_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg: #020617;
            --panel: rgba(255, 255, 255, 0.94);
            --panel-strong: rgba(255, 255, 255, 0.98);
            --border: rgba(37, 99, 235, 0.22);
            --text: #111827;
            --muted: #667085;
            --black: #111111;
            --gold: #b88917;
            --gold-soft: #efe1bd;
            --green: #047857;
            --amber: #b7791f;
            --red: #b42318;
        }

        .stApp {
            color: var(--text);
            background:
                radial-gradient(ellipse at 50% 18%, rgba(56, 189, 248, 0.95) 0%, rgba(37, 99, 235, 0.38) 9%, transparent 31%),
                radial-gradient(ellipse at 50% 52%, rgba(59, 130, 246, 0.78) 0%, rgba(29, 78, 216, 0.28) 11%, transparent 30%),
                repeating-radial-gradient(ellipse at 50% 18%, rgba(96, 165, 250, 0.32) 0 1px, transparent 1px 9px),
                linear-gradient(90deg, transparent 0%, rgba(59, 130, 246, 0.2) 48%, rgba(125, 211, 252, 0.7) 50%, rgba(59, 130, 246, 0.2) 52%, transparent 100%),
                linear-gradient(180deg, #020617 0%, #061331 38%, #020617 100%);
            background-attachment: fixed;
            font-family: "Inter", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
        }

        .stApp::before {
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            z-index: 0;
            background:
                linear-gradient(78deg, transparent 0 44%, rgba(59, 130, 246, 0.38) 44.5%, transparent 45.5% 100%),
                linear-gradient(102deg, transparent 0 52%, rgba(14, 165, 233, 0.3) 52.5%, transparent 53.5% 100%),
                linear-gradient(257deg, transparent 0 47%, rgba(96, 165, 250, 0.2) 47.5%, transparent 48.2% 100%),
                linear-gradient(283deg, transparent 0 56%, rgba(125, 211, 252, 0.22) 56.5%, transparent 57.4% 100%);
            opacity: 0.48;
            mix-blend-mode: screen;
        }

        .stApp::after {
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            z-index: 0;
            background:
                radial-gradient(ellipse at center, transparent 0%, transparent 48%, rgba(2, 6, 23, 0.88) 100%),
                linear-gradient(rgba(125, 211, 252, 0.035) 1px, transparent 1px),
                linear-gradient(90deg, rgba(125, 211, 252, 0.025) 1px, transparent 1px);
            background-size: 100% 100%, 42px 42px, 42px 42px;
        }

        .block-container {
            position: relative;
            z-index: 1;
            padding-top: 2.2rem;
            padding-bottom: 3rem;
            max-width: 1480px;
        }

        [data-testid="stSidebar"] {
            background: rgba(17, 17, 17, 0.98);
            border-right: 1px solid var(--border);
        }

        [data-testid="stSidebar"] * {
            color: #f8f5ed;
        }

        h1 {
            color: #f8fbff;
            font-size: 3.1rem;
            font-weight: 780;
            letter-spacing: 0;
            border-left: 5px solid #38bdf8;
            padding-left: 0.85rem;
            text-shadow: 0 0 24px rgba(59, 130, 246, 0.6);
        }

        [data-testid="stHeading"] h1,
        [data-testid="stHeading"] h2,
        [data-testid="stHeading"] h3,
        div[data-testid="stMarkdownContainer"] h1,
        div[data-testid="stMarkdownContainer"] h2,
        div[data-testid="stMarkdownContainer"] h3 {
            color: #f8fbff !important;
            font-weight: 850 !important;
            text-shadow: 0 0 18px rgba(59, 130, 246, 0.48);
        }

        h2, h3 {
            color: #f8fbff;
            font-size: 1.65rem;
            font-weight: 800;
            letter-spacing: 0;
            text-shadow: 0 0 18px rgba(59, 130, 246, 0.42);
        }

        [data-testid="stCaptionContainer"] {
            color: #bfdbfe;
        }

        [data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.96);
            border: 1px solid rgba(125, 211, 252, 0.28);
            border-radius: 8px;
            padding: 1rem 1.1rem;
            box-shadow: 0 22px 50px rgba(2, 6, 23, 0.22);
            border-top: 3px solid #38bdf8;
        }

        [data-testid="stMetricLabel"] {
            color: var(--muted);
        }

        [data-testid="stMetricValue"] {
            color: var(--black);
            font-weight: 750;
        }

        [data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(255, 255, 255, 0.4);
            border-radius: 8px;
        }

        .stPlotlyChart {
            background: rgba(8, 19, 46, 0.96);
            border: 1px solid rgba(125, 211, 252, 0.28);
            border-radius: 8px;
            padding: 0.7rem;
            box-shadow: 0 22px 50px rgba(2, 6, 23, 0.22);
        }

        [data-testid="stDataFrame"] {
            border: 1px solid rgba(125, 211, 252, 0.28);
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 22px 50px rgba(2, 6, 23, 0.22);
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0.35rem;
            border-bottom: 1px solid var(--border);
        }

        .stTabs [data-baseweb="tab"] {
            color: var(--muted);
            background: rgba(255, 255, 255, 0.72);
            border: 1px solid rgba(17, 24, 39, 0.12);
            border-bottom: 0;
            border-radius: 8px 8px 0 0;
            padding: 0.55rem 0.9rem;
            font-weight: 650;
        }

        .stTabs [aria-selected="true"] {
            color: var(--black);
            background: var(--panel-strong);
            border-color: rgba(184, 137, 23, 0.5);
            box-shadow: inset 0 3px 0 var(--gold);
        }

        .stButton button {
            background: linear-gradient(135deg, #151515 0%, #2a2418 100%);
            color: #ffffff !important;
            border: 1px solid rgba(184, 137, 23, 0.62);
            border-radius: 8px;
            font-weight: 700;
        }

        .stDownloadButton button,
        .stDownloadButton button p {
            color: #ffffff !important;
            font-weight: 800 !important;
        }

        .stButton button:hover {
            background: linear-gradient(135deg, #0f0f0f 0%, #3a2b0f 100%);
            border-color: rgba(184, 137, 23, 0.95);
            color: #ffffff !important;
        }

        .stDownloadButton button:hover,
        .stDownloadButton button:focus,
        .stDownloadButton button:active {
            color: #ffffff !important;
            border-color: rgba(56, 189, 248, 0.9);
        }

        div[data-testid="stDataFrame"] div[role="columnheader"] {
            background: #111111;
            color: #f8f5ed;
        }

        .js-plotly-plot .plotly .main-svg {
            border-radius: 8px;
        }

        .summary-panel {
            background: rgba(8, 19, 46, 0.92);
            border: 1px solid rgba(125, 211, 252, 0.28);
            border-left: 5px solid #38bdf8;
            border-radius: 8px;
            box-shadow: 0 22px 50px rgba(2, 6, 23, 0.22);
            padding: 1.05rem 1.2rem;
            margin: 1rem 0 1.1rem;
        }

        .summary-panel h3 {
            color: #f8fbff;
            margin: 0 0 0.35rem;
            font-size: 1.12rem;
            font-weight: 800;
            text-shadow: 0 0 18px rgba(59, 130, 246, 0.42);
        }

        .summary-panel p {
            color: #dbeafe;
            line-height: 1.55;
            margin: 0;
        }

        .risk-badge {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 0.3rem 0.72rem;
            margin-left: 0.35rem;
            color: #ffffff;
            font-size: 0.82rem;
            font-weight: 800;
            letter-spacing: 0.02em;
        }

        .risk-normal {
            background: #047857;
        }

        .risk-elevated {
            background: #b7791f;
        }

        .risk-critical {
            background: #b42318;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def polish_chart(fig):
    fig.update_layout(
        template=TECH_TEMPLATE,
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=PANEL_BG,
        font={"color": FONT_COLOR, "family": "Inter, Segoe UI, Arial, sans-serif"},
        title={"font": {"size": 18, "color": "#f8fbff"}},
        margin={"l": 76, "r": 32, "t": 70, "b": 80},
        legend={"bgcolor": "rgba(255, 255, 255, 0)", "font": {"color": FONT_COLOR}},
        hoverlabel={"bgcolor": "#111111", "font": {"color": "#ffffff"}},
    )
    fig.update_xaxes(
        gridcolor=GRID_COLOR,
        linecolor="rgba(125, 211, 252, 0.32)",
        tickfont={"color": "#dbeafe", "size": 12},
        title_font={"color": "#f8fbff", "size": 13},
        tickformat=",.2f",
        zeroline=False,
    )
    fig.update_yaxes(
        gridcolor=GRID_COLOR,
        linecolor="rgba(125, 211, 252, 0.32)",
        tickfont={"color": "#dbeafe", "size": 12},
        title_font={"color": "#f8fbff", "size": 13},
        tickformat=",.2f",
        zeroline=False,
    )
    return fig


@st.cache_resource
def ensure_database() -> Path:
    if not DB_PATH.exists():
        build_database()
    return DB_PATH


@st.cache_data
def read_sql(query: str, db_mtime: float) -> pd.DataFrame:
    db_path = ensure_database()
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(query, conn)


def status_badge(value: str) -> str:
    colors = {
        "PASS": "#047857",
        "WATCHLIST": "#b7791f",
        "WARN": "#b7791f",
        "FAIL": "#b42318",
        "CRITICAL: LIMIT BREACH": "#b42318",
        "Keep Preferred": "#047857",
        "Monitor / Review SLA": "#b7791f",
        "Restrict Routing": "#b42318",
    }
    color = colors.get(value, "#334155")
    return f"background-color: {color}; color: white; font-weight: 700; border-radius: 4px"


def styled_table(df: pd.DataFrame, status_columns: list[str] | None = None) -> pd.io.formats.style.Styler:
    integer_columns = {
        "trade_id",
        "user_id",
        "broker_id",
        "sla_latency_ms",
        "execution_latency_ms",
        "trade_count",
        "limit_breach_count",
        "latency_fail_count",
        "max_trades_in_5_minutes",
    }
    numeric_formats = {
        column: "{:,.2f}"
        for column in df.select_dtypes(include="number").columns
        if column not in integer_columns
    }
    styler = df.style.format(numeric_formats)
    for column in status_columns or []:
        if column in df.columns:
            styler = styler.map(status_badge, subset=[column])
    return styler


def ordered_full_sql_view(df: pd.DataFrame) -> pd.DataFrame:
    preferred_columns = [
        "trade_id",
        "executed_at",
        "user_name",
        "desk_segment",
        "country",
        "broker_name",
        "venue_type",
        "broker_region",
        "asset_class",
        "symbol",
        "side",
        "requested_price",
        "executed_price",
        "quantity",
        "usd_conversion_rate",
        "contract_multiplier",
        "adverse_slippage_points",
        "slippage_bps",
        "usd_slippage_loss",
        "usd_exposure_limit",
        "total_usd_exposure",
        "exposure_status",
        "sla_latency_ms",
        "execution_latency_ms",
        "latency_status",
        "slippage_direction",
    ]
    ordered_columns = [column for column in preferred_columns if column in df.columns]
    remaining_columns = [column for column in df.columns if column not in ordered_columns]
    return df[ordered_columns + remaining_columns]


def multiselect_filter(label: str, values: pd.Series) -> list[str]:
    options = sorted(values.dropna().unique().tolist())
    return st.sidebar.multiselect(label, options=options, default=options)


def filter_risk_tape(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.markdown("### Risk Filters")
    selected_brokers = multiselect_filter("Broker", df["broker_name"])
    selected_assets = multiselect_filter("Asset Class", df["asset_class"])
    selected_exposure = multiselect_filter("Exposure Status", df["exposure_status"])
    selected_latency = multiselect_filter("Latency Status", df["latency_status"])

    return df[
        df["broker_name"].isin(selected_brokers)
        & df["asset_class"].isin(selected_assets)
        & df["exposure_status"].isin(selected_exposure)
        & df["latency_status"].isin(selected_latency)
    ].copy()


def build_broker_scorecard(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=[
                "broker_name",
                "asset_class",
                "trade_count",
                "avg_slippage_bps",
                "slippage_variance",
                "total_usd_slippage_loss",
                "total_usd_exposure",
                "limit_breach_count",
                "latency_fail_count",
                "broker_risk_status",
            ]
        )

    grouped = df.groupby(["broker_name", "asset_class"], as_index=False).agg(
        trade_count=("trade_id", "count"),
        avg_slippage_bps=("slippage_bps", "mean"),
        total_usd_slippage_loss=("usd_slippage_loss", "sum"),
        total_usd_exposure=("total_usd_exposure", "sum"),
        limit_breach_count=("exposure_status", lambda series: (series == "CRITICAL: LIMIT BREACH").sum()),
        latency_fail_count=("latency_status", lambda series: (series == "FAIL").sum()),
    )
    variance = (
        df.assign(slippage_bps_squared=df["slippage_bps"] * df["slippage_bps"])
        .groupby(["broker_name", "asset_class"], as_index=False)
        .agg(avg_squared_slippage=("slippage_bps_squared", "mean"))
    )
    grouped = grouped.merge(variance, on=["broker_name", "asset_class"], how="left")
    grouped["slippage_variance"] = grouped["avg_squared_slippage"] - (
        grouped["avg_slippage_bps"] * grouped["avg_slippage_bps"]
    )

    grouped["broker_risk_status"] = "PASS"
    grouped.loc[grouped["slippage_variance"] > 35, "broker_risk_status"] = "WATCHLIST"
    grouped.loc[
        (grouped["limit_breach_count"] > 0)
        | (grouped["latency_fail_count"] > 0)
        | (grouped["slippage_variance"] > 100),
        "broker_risk_status",
    ] = "FAIL"

    numeric_columns = [
        "avg_slippage_bps",
        "slippage_variance",
        "total_usd_slippage_loss",
        "total_usd_exposure",
    ]
    grouped[numeric_columns] = grouped[numeric_columns].round(2)
    return grouped.drop(columns=["avg_squared_slippage"]).sort_values(
        by=["broker_risk_status", "slippage_variance"],
        ascending=[True, False],
    )


def lp_routing_recommendations(broker_df: pd.DataFrame) -> pd.DataFrame:
    if broker_df.empty:
        return pd.DataFrame(
            columns=[
                "broker_name",
                "asset_class",
                "total_usd_slippage_loss",
                "slippage_variance",
                "latency_fail_count",
                "limit_breach_count",
                "routing_action",
            ]
        )

    recommendations = broker_df.copy()
    recommendations["routing_action"] = "Keep Preferred"
    recommendations.loc[
        (recommendations["slippage_variance"] > 35) | (recommendations["latency_fail_count"] > 0),
        "routing_action",
    ] = "Monitor / Review SLA"
    recommendations.loc[
        (recommendations["broker_risk_status"] == "FAIL")
        & (
            (recommendations["total_usd_slippage_loss"] > 5000)
            | (recommendations["slippage_variance"] > 100)
            | (recommendations["latency_fail_count"] > 0)
        ),
        "routing_action",
    ] = "Restrict Routing"

    return recommendations[
        [
            "broker_name",
            "asset_class",
            "total_usd_slippage_loss",
            "slippage_variance",
            "latency_fail_count",
            "limit_breach_count",
            "routing_action",
        ]
    ].sort_values(
        by=["routing_action", "total_usd_slippage_loss", "slippage_variance"],
        ascending=[False, False, False],
    )


def overall_risk_status(limit_breaches: int, latency_fails: int, total_loss: float) -> tuple[str, str]:
    if limit_breaches >= 7 or latency_fails >= 7 or total_loss >= 60000:
        return "CRITICAL", "risk-critical"
    if limit_breaches > 0 or latency_fails > 0 or total_loss >= 25000:
        return "ELEVATED", "risk-elevated"
    return "NORMAL", "risk-normal"


def executive_summary(df: pd.DataFrame, broker_df: pd.DataFrame) -> str:
    if df.empty:
        return "No trades match the selected filters. Adjust the sidebar filters to restore dashboard coverage."

    worst_broker = "No broker"
    if not broker_df.empty:
        worst_broker = broker_df.sort_values("slippage_variance", ascending=False).iloc[0]["broker_name"]

    exposure = df["total_usd_exposure"].sum()
    loss = df["usd_slippage_loss"].sum()
    breach_count = (df["exposure_status"] == "CRITICAL: LIMIT BREACH").sum()
    fail_count = (df["latency_status"] == "FAIL").sum()

    return (
        f"The selected trade set contains ${exposure:,.2f} of USD-equivalent exposure and "
        f"${loss:,.2f} of adverse slippage loss. The system detected {breach_count} limit "
        f"breaches and {fail_count} latency failures. The broker requiring the fastest review "
        f"is {worst_broker}, based on the current slippage variance profile."
    )


apply_institutional_theme()

st.title("Operational Slippage Risk Dashboard")
st.caption("SQL case study: broker execution quality, USD exposure controls, and routing latency surveillance.")

if st.sidebar.button("Rebuild demo database"):
    build_database()
    st.cache_data.clear()
    st.rerun()

db_mtime = ensure_database().stat().st_mtime

risk_tape = read_sql(
    """
    SELECT *
    FROM v_trade_slippage_risk
    ORDER BY executed_at;
    """,
    db_mtime,
)
broker_variance = read_sql(
    """
    SELECT *
    FROM v_broker_slippage_variance
    ORDER BY
        CASE broker_risk_status WHEN 'FAIL' THEN 1 WHEN 'WATCHLIST' THEN 2 ELSE 3 END,
        slippage_variance DESC;
    """,
    db_mtime,
)
velocity = read_sql(
    """
    SELECT *
    FROM v_user_velocity_loops
    ORDER BY
        CASE velocity_status WHEN 'FAIL' THEN 1 WHEN 'WATCHLIST' THEN 2 ELSE 3 END,
        max_trades_in_5_minutes DESC;
    """,
    db_mtime,
)

filtered_risk_tape = filter_risk_tape(risk_tape)
filtered_broker_variance = build_broker_scorecard(filtered_risk_tape)
filtered_lp_recommendations = lp_routing_recommendations(filtered_broker_variance)
filtered_velocity = velocity[
    velocity["symbol"].isin(filtered_risk_tape["symbol"].dropna().unique())
].copy()

total_exposure = filtered_risk_tape["total_usd_exposure"].sum()
total_loss = filtered_risk_tape["usd_slippage_loss"].sum()
client_costly_trades = (filtered_risk_tape["slippage_direction"] == "ADVERSE").sum()
client_beneficial_trades = (filtered_risk_tape["slippage_direction"] == "PRICE IMPROVEMENT").sum()
limit_breaches = (filtered_risk_tape["exposure_status"] == "CRITICAL: LIMIT BREACH").sum()
latency_fails = (filtered_risk_tape["latency_status"] == "FAIL").sum()
risk_status, risk_status_class = overall_risk_status(limit_breaches, latency_fails, total_loss)

st.markdown(
    f"""
    <div class="summary-panel">
        <h3>Executive Risk Summary <span class="risk-badge {risk_status_class}">{risk_status}</span></h3>
        <p>{executive_summary(filtered_risk_tape, filtered_broker_variance)}</p>
    </div>
    """,
    unsafe_allow_html=True,
)

metric_cols = st.columns(4)
metric_cols[0].metric("Total USD Exposure", f"${total_exposure:,.2f}")
metric_cols[1].metric("USD Slippage Loss", f"${total_loss:,.2f}")
metric_cols[2].metric("Client-Costly Trades", f"{client_costly_trades}")
metric_cols[3].metric("Client-Beneficial Trades", f"{client_beneficial_trades}")

control_cols = st.columns(2)
control_cols[0].metric("Limit Breaches", f"{limit_breaches}")
control_cols[1].metric("Latency Fails", f"{latency_fails}")

top_trades = filtered_risk_tape.sort_values("usd_slippage_loss", ascending=False).head(5)[
    [
        "trade_id",
        "user_name",
        "broker_name",
        "symbol",
        "usd_slippage_loss",
        "slippage_bps",
        "total_usd_exposure",
        "exposure_status",
        "latency_status",
    ]
].copy()
top_trades["trade_label"] = "Trade " + top_trades["trade_id"].astype(str)

left, right = st.columns([1.2, 1])
with left:
    if filtered_broker_variance.empty:
        st.info("No broker scorecard data matches the selected filters.")
    else:
        broker_chart = px.bar(
            filtered_broker_variance,
            x="broker_name",
            y="slippage_variance",
            color="broker_risk_status",
            pattern_shape="asset_class",
            title="Slippage Variance by Broker and Asset Class",
            labels={"slippage_variance": "Variance", "broker_name": "Broker"},
            color_discrete_map={"PASS": "#047857", "WATCHLIST": "#b88917", "FAIL": "#b42318"},
            template=TECH_TEMPLATE,
            hover_data=["asset_class", "trade_count", "avg_slippage_bps", "total_usd_slippage_loss"],
        )
        broker_chart.update_layout(
            height=430,
            legend_title_text="Risk Status",
            xaxis_tickangle=-25,
            bargap=0.32,
        )
        broker_chart.update_traces(marker_line_color="#ffffff", marker_line_width=1.2)
        broker_chart = polish_chart(broker_chart)
        st.plotly_chart(broker_chart, use_container_width=True)

with right:
    if top_trades.empty:
        st.info("No worst-trade data matches the selected filters.")
    else:
        worst_trade_chart = px.bar(
            top_trades.sort_values("usd_slippage_loss", ascending=True),
            x="usd_slippage_loss",
            y="trade_label",
            orientation="h",
            color="latency_status",
            text="usd_slippage_loss",
            hover_data=["user_name", "broker_name", "symbol", "slippage_bps", "total_usd_exposure", "exposure_status"],
            title="Top 5 Worst Trades by USD Slippage Loss",
            labels={"usd_slippage_loss": "USD Slippage Loss", "trade_label": "Trade"},
            color_discrete_map={"PASS": "#047857", "WARN": "#b88917", "FAIL": "#b42318"},
            template=TECH_TEMPLATE,
        )
        worst_trade_chart.update_layout(height=430, legend_title_text="Latency")
        worst_trade_chart.update_traces(
            marker_line_color="#ffffff",
            marker_line_width=1.2,
            texttemplate="$%{text:,.2f}",
            textposition="outside",
            cliponaxis=False,
        )
        worst_trade_chart = polish_chart(worst_trade_chart)
        st.plotly_chart(worst_trade_chart, use_container_width=True)

critical = filtered_risk_tape[
    (filtered_risk_tape["exposure_status"] != "PASS") | (filtered_risk_tape["latency_status"] != "PASS")
][
    [
        "trade_id",
        "executed_at",
        "user_name",
        "broker_name",
        "symbol",
        "side",
        "total_usd_exposure",
        "usd_slippage_loss",
        "slippage_bps",
        "exposure_status",
        "latency_status",
    ]
]

st.subheader("Top 5 Worst Trades")
st.dataframe(
    styled_table(top_trades.drop(columns=["trade_label"], errors="ignore"), ["exposure_status", "latency_status"]),
    use_container_width=True,
    hide_index=True,
)

st.subheader("LP Routing Recommendations")
st.caption("Institutional broker view: identify liquidity providers or venues to keep, monitor, or restrict based on slippage loss, variance, and latency failures.")
st.dataframe(
    styled_table(filtered_lp_recommendations, ["routing_action"]),
    use_container_width=True,
    hide_index=True,
)

critical_title, critical_export = st.columns([0.75, 0.25])
with critical_title:
    st.subheader("Critical Risk Tape")

with critical_export:
    st.download_button(
        "Export to Excel",
        data=critical.to_csv(index=False).encode("utf-8"),
        file_name="critical_risk_tape.csv",
        mime="text/csv",
        use_container_width=True,
    )

st.dataframe(
    styled_table(critical, ["exposure_status", "latency_status"]),
    use_container_width=True,
    hide_index=True,
)

tab1, tab2, tab3 = st.tabs(["Broker Scorecard", "Velocity Loops", "Full SQL View"])

with tab1:
    st.dataframe(
        styled_table(filtered_broker_variance, ["broker_risk_status"]),
        use_container_width=True,
        hide_index=True,
    )

with tab2:
    st.dataframe(
        styled_table(filtered_velocity, ["velocity_status"]),
        use_container_width=True,
        hide_index=True,
    )

with tab3:
    st.dataframe(
        styled_table(ordered_full_sql_view(filtered_risk_tape), ["exposure_status", "latency_status"]),
        use_container_width=True,
        hide_index=True,
    )
