"""Personal Financial Statement — a Streamlit dashboard for account snapshot CSVs.

Run with:  streamlit run dashboard.py

The CSV needs these columns: account_name, account_type, account_institution, value, date.
Each date is treated as a full snapshot of every account on that day. Debts are negative values.
"""

import glob
import os
import re
from datetime import timedelta
from html import escape

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

APP_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Your defaults — change these so the sidebar opens with your own numbers.
# ---------------------------------------------------------------------------
DEFAULT_DATA_FILE = "brendan_data.csv"
DEFAULT_MONTHLY_EXPENSES = 4000
DEFAULT_EMERGENCY_TARGET_MONTHS = 6
DEFAULT_GOAL_ACCOUNT = "home"
DEFAULT_GOAL_TARGET = 0  # 0 = no target set
DEFAULT_RETIREMENT_RETURN = 5.0  # percent a year, for retirement projections

DAYS_PER_MONTH = 30.44

# ---------------------------------------------------------------------------
# Visual system
# ---------------------------------------------------------------------------
INK = "#16213a"
INK_2 = "#4a5468"
MUTED = "#8a91a0"
GRID = "#e6e9ef"
BASELINE = "#c5cad4"
NAVY = "#1f3a68"
SURFACE = "#ffffff"

GOOD = "#0ca30c"
WARNING = "#fab219"
CRITICAL = "#d03b3b"
GOOD_TEXT = "#006300"

TYPE_ORDER = ["retirement", "investments", "savings", "real estate", "other assets", "debt"]
TYPE_LABELS = {
    "retirement": "Retirement",
    "investments": "Taxable investments",
    "savings": "Cash savings",
    "real estate": "Real estate",
    "other assets": "Other assets",
    "debt": "Debt",
}
TYPE_COLORS = {
    "retirement": "#2a78d6",
    "investments": "#eb6834",
    "savings": "#1baf7a",
    "real estate": "#eda100",
    "other assets": "#6250d6",
    "debt": "#e34948",
}
OTHER_COLOR = "#898781"

FONT_STACK = "'IBM Plex Sans', -apple-system, 'Segoe UI', sans-serif"

st.set_page_config(
    page_title="Personal Financial Statement",
    page_icon="📒",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,500;8..60,600&display=swap');

html, body, [class*="css"], .stMarkdown, .stTabs, button, input, select, textarea {{
    font-family: {FONT_STACK};
}}
.block-container {{ padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1280px; }}
header[data-testid="stHeader"] {{ background: transparent; }}
footer {{ visibility: hidden; }}

/* Masthead */
.masthead {{
    background: {NAVY};
    color: #ffffff;
    border-radius: 6px;
    padding: 1.6rem 2rem 1.4rem;
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 2rem;
    flex-wrap: wrap;
    border-bottom: 4px solid #c9a227;
}}
.masthead h1 {{
    font-family: 'Source Serif 4', Georgia, serif;
    font-weight: 600;
    font-size: 2.1rem;
    line-height: 1.15;
    margin: 0;
    padding: 0;
    color: #ffffff;
    letter-spacing: -0.01em;
}}
.masthead .sub {{ color: #c8d2e6; font-size: 0.95rem; margin-top: 0.35rem; }}
.masthead .asof {{ text-align: right; font-size: 0.9rem; color: #c8d2e6; line-height: 1.5; }}
.masthead .asof strong {{ display: block; color: #ffffff; font-size: 1.15rem; font-weight: 600; }}

/* Section headings */
.section {{ margin: 1.8rem 0 0.6rem; }}
.section h3 {{
    font-family: 'Source Serif 4', Georgia, serif;
    font-weight: 600; font-size: 1.35rem; color: {INK};
    margin: 0; padding: 0;
}}
.section p {{ color: {INK_2}; font-size: 0.92rem; margin: 0.2rem 0 0; max-width: 72ch; }}

/* KPI strip */
.kpis {{
    display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
    background: {SURFACE}; border: 1px solid {GRID}; border-radius: 6px;
    margin-top: 1rem;
}}
.kpi {{ padding: 1.1rem 1.3rem; border-left: 1px solid {GRID}; }}
.kpi:first-child {{ border-left: none; }}
.kpi .label {{ color: {INK_2}; font-size: 0.88rem; }}
.kpi .value {{ color: {INK}; font-size: clamp(1.25rem, 2.1vw, 1.85rem); font-weight: 600; margin-top: 0.15rem; letter-spacing: -0.01em; white-space: nowrap; }}
.kpi .delta {{ font-size: 0.86rem; margin-top: 0.2rem; color: {INK_2}; }}
.kpi .delta.up {{ color: {GOOD_TEXT}; }}
.kpi .delta.down {{ color: {CRITICAL}; }}
@media (max-width: 900px) {{
    .kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .kpi:nth-child(3) {{ border-left: none; }}
    .kpi:nth-child(n+3) {{ border-top: 1px solid {GRID}; }}
}}

/* Panels */
.stPlotlyChart {{
    background: {SURFACE}; border: 1px solid {GRID}; border-radius: 6px; padding: 0.6rem 0.6rem 0.2rem;
}}
.panel {{ background: {SURFACE}; border: 1px solid {GRID}; border-radius: 6px; padding: 0.4rem 1.2rem; }}

/* Health check */
.check {{ display: grid; grid-template-columns: 1.6rem 1fr auto; gap: 0.75rem; align-items: start;
         padding: 0.85rem 0; border-top: 1px solid {GRID}; }}
.check:first-child {{ border-top: none; }}
.check .icon {{ width: 1.45rem; height: 1.45rem; border-radius: 50%; color: #fff; font-weight: 700;
               font-size: 0.8rem; display: flex; align-items: center; justify-content: center; margin-top: 0.1rem; }}
.check .title {{ font-weight: 600; color: {INK}; font-size: 0.97rem; }}
.check .detail {{ color: {INK_2}; font-size: 0.88rem; margin-top: 0.15rem; }}
.check .figure {{ font-weight: 600; color: {INK}; font-size: 1.05rem; text-align: right; white-space: nowrap; }}
.check .status {{ font-size: 0.8rem; color: {INK_2}; text-align: right; }}

/* Tiers / goal */
.tiers {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.8rem; }}
.tier {{ background: {SURFACE}; border: 1px solid {GRID}; border-radius: 6px; padding: 1rem 1.2rem; border-top-width: 4px; }}
.tier .name {{ font-weight: 600; color: {INK}; }}
.tier .amt {{ font-size: 1.5rem; font-weight: 600; color: {INK}; margin-top: 0.3rem; }}
.tier .note {{ color: {INK_2}; font-size: 0.86rem; margin-top: 0.2rem; }}
@media (max-width: 900px) {{ .tiers {{ grid-template-columns: 1fr; }} }}

.bar-track {{ background: {GRID}; border-radius: 4px; height: 10px; overflow: hidden; margin: 0.5rem 0 0.3rem; }}
.bar-fill {{ background: {TYPE_COLORS['savings']}; height: 100%; border-radius: 4px; }}

/* Statement table */
table.stmt {{ width: 100%; border-collapse: collapse; background: {SURFACE}; font-size: 0.92rem;
             border: 1px solid {GRID}; border-radius: 6px; }}
table.stmt th {{ text-align: left; color: {INK_2}; font-weight: 500; padding: 0.7rem 0.9rem;
                border-bottom: 1px solid {BASELINE}; background: #f8f9fb; }}
table.stmt td {{ padding: 0.6rem 0.9rem; border-bottom: 1px solid {GRID}; color: {INK}; }}
table.stmt td.num, table.stmt th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
table.stmt tr.total td {{ font-weight: 600; border-top: 1px solid {BASELINE}; border-bottom: none; }}
table.stmt .swatch {{ display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 0.5rem; }}
table.stmt .pos {{ color: {GOOD_TEXT}; }}
table.stmt .neg {{ color: {CRITICAL}; }}
.table-wrap {{ overflow-x: auto; }}

.footnote {{ color: {MUTED}; font-size: 0.82rem; margin-top: 0.5rem; }}

.stTabs [data-baseweb="tab-list"] {{ gap: 1.6rem; border-bottom: 1px solid {BASELINE}; margin-top: 1.4rem; }}
.stTabs [data-baseweb="tab"] {{ font-size: 1rem; font-weight: 500; padding-left: 0; padding-right: 0; }}
section[data-testid="stSidebar"] h2 {{ font-family: 'Source Serif 4', Georgia, serif; font-size: 1.2rem; }}
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def money(x, cents=False):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    fmt = f"{abs(x):,.2f}" if cents else f"{abs(x):,.0f}"
    return f"−${fmt}" if x < 0 else f"${fmt}"


def signed_money(x):
    if abs(x) < 0.5:
        return "$0"
    return f"+{money(x)}" if x > 0 else money(x)


def pct(x, signed=False, digits=1):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    s = f"{x * 100:+.{digits}f}%" if signed else f"{x * 100:.{digits}f}%"
    return s.replace("-", "−")


def fmt_date(d):
    return pd.Timestamp(d).strftime("%b %-d, %Y")


ACRONYMS = {"ira": "IRA", "401k": "401(k)", "403b": "403(b)", "cd": "CD", "hsa": "HSA", "529": "529"}


def pretty(name):
    """Display name for an account: 'roth ira' -> 'Roth IRA'."""
    return " ".join(ACRONYMS.get(w.lower(), w if w.isupper() else w.capitalize()) for w in str(name).split())


def type_label(t):
    return TYPE_LABELS.get(t, t.title())


def type_color(t):
    return TYPE_COLORS.get(t, OTHER_COLOR)


def section(title, blurb=None):
    body = f"<p>{blurb}</p>" if blurb else ""
    st.markdown(f'<div class="section"><h3>{title}</h3>{body}</div>', unsafe_allow_html=True)


def style_fig(fig, height=380, money_axis=True):
    fig.update_layout(
        template="plotly_white",
        height=height,
        font=dict(family=FONT_STACK, size=13, color=INK_2),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        margin=dict(l=8, r=16, t=36, b=8),
        hoverlabel=dict(bgcolor=SURFACE, bordercolor=BASELINE, font=dict(family=FONT_STACK, size=13, color=INK)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title_text="", font=dict(color=INK_2)),
    )
    fig.update_xaxes(showgrid=False, linecolor=BASELINE, ticks="outside", tickcolor=BASELINE, tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=BASELINE, zerolinewidth=1, tickfont=dict(color=MUTED))
    if money_axis:
        fig.update_yaxes(tickprefix="$", tickformat="~s")
    return fig


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
@st.cache_data
def load_data(source, mtime=None):  # mtime busts the cache when the file changes
    df = pd.read_csv(source)
    df = df.loc[:, [c for c in df.columns if not str(c).startswith("Unnamed")]]
    df.columns = [c.strip().lower() for c in df.columns]
    for col in ["account_name", "account_type", "account_institution"]:
        df[col] = df[col].astype(str).str.strip()
    df["account_type"] = df["account_type"].str.lower()
    df["value"] = pd.to_numeric(df["value"].astype(str).str.replace(r"[$,]", "", regex=True), errors="coerce")
    # pandas 2 guesses one date format from the first row; "mixed" lets each row use its own (7/1/2025, 2024-01-01).
    mixed = {"format": "mixed"} if int(pd.__version__.split(".")[0]) >= 2 else {}
    df["date"] = pd.to_datetime(df["date"], errors="coerce", **mixed)
    df = df.dropna(subset=["date", "value", "account_name"])
    return df.sort_values(["date", "account_name"]).reset_index(drop=True)


def build_frames(df):
    """Snapshot tables used everywhere: per account, per type, and totals."""
    wide = df.pivot_table(index="date", columns="account_name", values="value", aggfunc="sum").sort_index()
    by_type = df.pivot_table(index="date", columns="account_type", values="value", aggfunc="sum").fillna(0).sort_index()
    totals = pd.DataFrame(
        {
            "assets": df[df["value"] > 0].groupby("date")["value"].sum(),
            "debts": -df[df["value"] < 0].groupby("date")["value"].sum(),
        }
    ).fillna(0)
    totals["net_worth"] = totals["assets"] - totals["debts"]
    totals = totals.sort_index()
    return wide, by_type, totals


def linear_trend(dates, values):
    """Least-squares slope per month and intercept. Needs at least 2 points."""
    if len(values) < 2:
        return None
    idx = pd.DatetimeIndex(dates)
    days = np.asarray((idx - idx.min()).days, dtype=float)
    if days.max() == 0:
        return None
    slope, intercept = np.polyfit(days, np.asarray(values, dtype=float), 1)
    return slope * DAYS_PER_MONTH, intercept, idx.min()


def account_meta(df):
    last = df.sort_values("date").groupby("account_name").last()
    return last[["account_type", "account_institution"]]


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
def bar_width_ms(dates):
    """Bar width that suits the spacing of statements: 60% of the typical gap, at least 14 days."""
    gaps = pd.Series(pd.DatetimeIndex(dates)).diff().dt.days.dropna()
    days = max(14, 0.6 * gaps.median()) if len(gaps) else 14
    return 1000 * 60 * 60 * 24 * days


def balance_sheet_chart(by_type, totals):
    """Stacked bars per snapshot: assets above zero by type, debt below, net worth line on top."""
    fig = go.Figure()
    types = [t for t in TYPE_ORDER if t in by_type.columns] + [t for t in by_type.columns if t not in TYPE_ORDER]
    bar_width = bar_width_ms(by_type.index)
    for t in types:
        fig.add_trace(
            go.Bar(
                x=by_type.index,
                y=by_type[t],
                name=type_label(t),
                marker=dict(color=type_color(t), line=dict(color=SURFACE, width=1.5)),
                width=bar_width,
                hovertemplate="%{y:$,.0f}",
            )
        )
    fig.add_trace(
        go.Scatter(
            x=totals.index,
            y=totals["net_worth"],
            name="Net worth",
            mode="lines+markers",
            line=dict(color=INK, width=2),
            marker=dict(size=8, color=INK, line=dict(color=SURFACE, width=2)),
            hovertemplate="<b>%{y:$,.0f}</b>",
        )
    )
    fig.update_layout(barmode="relative", hovermode="x unified", bargap=0)
    return style_fig(fig, height=420)


def change_waterfall(wide, totals):
    """Where the change in net worth came from, account by account."""
    start, end = wide.iloc[0].fillna(0), wide.iloc[-1].fillna(0)
    change = (end - start).sort_values(ascending=False)
    change = change[change.abs() >= 1]
    x = ["Start"] + [pretty(a) for a in change.index] + ["Now"]
    y = [totals["net_worth"].iloc[0]] + list(change.values) + [0]
    measure = ["absolute"] + ["relative"] * len(change) + ["total"]
    fig = go.Figure(
        go.Waterfall(
            x=x, y=y, measure=measure,
            increasing=dict(marker=dict(color=TYPE_COLORS["retirement"])),
            decreasing=dict(marker=dict(color=CRITICAL)),
            totals=dict(marker=dict(color=NAVY)),
            connector=dict(line=dict(color=BASELINE, width=1)),
            text=[money(totals["net_worth"].iloc[0])] + [signed_money(v) for v in change.values] + [money(totals["net_worth"].iloc[-1])],
            textposition="outside",
            textfont=dict(color=INK, size=12),
            hovertemplate="%{x}: %{text}<extra></extra>",
        )
    )
    fig.update_layout(showlegend=False)
    fig = style_fig(fig, height=420)
    lo = min(0, totals["net_worth"].min())
    hi = max(np.cumsum(y[:-1]).max(), totals["net_worth"].iloc[-1])
    fig.update_yaxes(range=[lo, hi * 1.12])
    return fig


def account_multiples(df, meta):
    # Only accounts open on the latest statement; closed ones still appear in the performance table.
    accounts = df[df["date"] == df["date"].max()].sort_values("value", ascending=False)["account_name"].tolist()
    cols = 3
    rows = int(np.ceil(len(accounts) / cols))
    titles = []
    for a in accounts:
        s = df[df["account_name"] == a].sort_values("date")
        first, last = s["value"].iloc[0], s["value"].iloc[-1]
        if len(s) > 1 and first != 0:
            ch = (abs(last) - abs(first)) / abs(first)
            word = "balance" if last < 0 else ""
            titles.append(f"<b>{pretty(a)}</b>  <span style='color:{MUTED}'>{money(last)}  ({pct(ch, signed=True)} {word})</span>")
        else:
            titles.append(f"<b>{pretty(a)}</b>  <span style='color:{MUTED}'>{money(last)}  (one snapshot)</span>")
    fig = make_subplots(rows=rows, cols=cols, subplot_titles=titles, vertical_spacing=min(0.16, 0.32 / rows), horizontal_spacing=0.06)
    for i, a in enumerate(accounts):
        s = df[df["account_name"] == a].sort_values("date")
        t = meta.loc[a, "account_type"]
        color = type_color(t)
        fig.add_trace(
            go.Scatter(
                x=s["date"], y=s["value"].abs() if t == "debt" else s["value"],
                mode="lines+markers", line=dict(color=color, width=2),
                marker=dict(size=7, color=color, line=dict(color=SURFACE, width=1.5)),
                name=pretty(a), showlegend=False,
                hovertemplate="%{x|%b %-d, %Y}<br><b>%{y:$,.0f}</b><extra>" + escape(pretty(a)) + "</extra>",
            ),
            row=i // cols + 1, col=i % cols + 1,
        )
    for ann in fig.layout.annotations:
        ann.font = dict(size=13, color=INK)
        ann.xanchor = "left"
        ann.x = ann.x - (1 / cols) / 2 + 0.01
    fig = style_fig(fig, height=270 * rows)
    fig.update_layout(margin=dict(t=48))
    return fig


def net_worth_projection(totals, months=12):
    trend = linear_trend(totals.index, totals["net_worth"])
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=totals.index, y=totals["net_worth"], name="Recorded", mode="lines+markers",
            line=dict(color=NAVY, width=2), marker=dict(size=8, color=NAVY, line=dict(color=SURFACE, width=2)),
            hovertemplate="%{x|%b %-d, %Y}<br><b>%{y:$,.0f}</b><extra>Recorded</extra>",
        )
    )
    if trend:
        per_month, intercept, t0 = trend
        last_date = totals.index[-1]
        future = pd.date_range(last_date, last_date + pd.DateOffset(months=months), periods=months + 1)
        start_val = totals["net_worth"].iloc[-1]
        proj = start_val + per_month * ((future - last_date).days / DAYS_PER_MONTH)
        fig.add_trace(
            go.Scatter(
                x=future, y=proj, name="If the current pace holds", mode="lines",
                line=dict(color=NAVY, width=2, dash="dot"),
                hovertemplate="%{x|%b %Y}<br><b>%{y:$,.0f}</b><extra>Trend</extra>",
            )
        )
        fig.add_annotation(
            x=future[-1], y=proj[-1], text=f"<b>{money(proj[-1])}</b>", showarrow=False, yshift=16,
            font=dict(color=INK, size=13),
        )
    fig.update_layout(hovermode="x unified")
    return style_fig(fig, height=360)


def allocation_over_time(by_type):
    assets = by_type[[c for c in by_type.columns if c != "debt"]].clip(lower=0)
    share = assets.div(assets.sum(axis=1), axis=0)
    types = [t for t in TYPE_ORDER if t in share.columns] + [t for t in share.columns if t not in TYPE_ORDER]
    fig = go.Figure()
    for t in types:
        fig.add_trace(
            go.Bar(
                x=share.index, y=share[t], name=type_label(t),
                marker=dict(color=type_color(t), line=dict(color=SURFACE, width=1.5)),
                width=bar_width_ms(share.index),
                customdata=assets[t], hovertemplate="%{y:.0%}  (%{customdata:$,.0f})",
            )
        )
    fig.update_layout(barmode="stack", hovermode="x unified", legend_traceorder="normal")
    fig = style_fig(fig, height=360, money_axis=False)
    fig.update_yaxes(tickformat=".0%", range=[0, 1])
    return fig


def current_mix_bar(latest_by_type):
    assets = latest_by_type[[c for c in latest_by_type.index if c != "debt"]].clip(lower=0)
    types = [t for t in TYPE_ORDER if t in assets.index] + [t for t in assets.index if t not in TYPE_ORDER]
    total = assets.sum()
    fig = go.Figure()
    for t in types:
        v = assets[t]
        fig.add_trace(
            go.Bar(
                y=[""], x=[v / total], orientation="h", name=type_label(t),
                marker=dict(color=type_color(t), line=dict(color=SURFACE, width=2)),
                text=f"{type_label(t)}  {v / total:.0%}" if v / total > 0.12 else "",
                textposition="inside", insidetextanchor="start", textfont=dict(color="#ffffff", size=13),
                hovertemplate=f"{type_label(t)}: {money(v)} ({v / total:.0%})<extra></extra>",
            )
        )
    fig.update_layout(barmode="stack", showlegend=True, legend_traceorder="normal")
    fig = style_fig(fig, height=150, money_axis=False)
    fig.update_xaxes(visible=False, range=[0, 1])
    fig.update_yaxes(visible=False)
    fig.update_layout(margin=dict(l=8, r=8, t=36, b=8))
    return fig


def debt_chart(df, debt_accounts):
    fig = go.Figure()
    for a in debt_accounts:
        s = df[df["account_name"] == a].sort_values("date")
        bal = s["value"].abs()
        fig.add_trace(
            go.Scatter(
                x=s["date"], y=bal, name=f"{pretty(a)} balance", mode="lines+markers",
                line=dict(color=TYPE_COLORS["debt"], width=2),
                marker=dict(size=8, color=TYPE_COLORS["debt"], line=dict(color=SURFACE, width=2)),
                hovertemplate="%{x|%b %-d, %Y}<br><b>%{y:$,.0f}</b><extra></extra>",
            )
        )
        trend = linear_trend(s["date"], bal)
        if trend and trend[0] < 0:
            per_month, intercept, t0 = trend
            last = s["date"].iloc[-1]
            # Same rule as the health check: today's balance divided by the average monthly paydown.
            payoff = last + timedelta(days=float(bal.iloc[-1] / -per_month * DAYS_PER_MONTH))
            xs = pd.date_range(last, payoff, periods=30)
            ys = np.maximum(bal.iloc[-1] + per_month * ((xs - last).days / DAYS_PER_MONTH), 0)
            fig.add_trace(
                go.Scatter(
                    x=xs, y=ys, name="Projected at current pace", mode="lines",
                    line=dict(color=TYPE_COLORS["debt"], width=2, dash="dot"),
                    hovertemplate="%{x|%b %Y}<br>%{y:$,.0f}<extra>Projected</extra>",
                )
            )
            fig.add_annotation(
                x=payoff, y=0, text=f"<b>Paid off ≈ {payoff.strftime('%b %Y')}</b>", showarrow=True,
                arrowhead=0, arrowcolor=BASELINE, ax=0, ay=-40, font=dict(color=INK, size=13),
            )
    fig.update_layout(hovermode="x unified")
    fig = style_fig(fig, height=380)
    fig.update_yaxes(rangemode="tozero")
    return fig


def debt_ratio_chart(totals):
    ratio = totals["debts"] / totals["assets"].replace(0, np.nan)
    fig = go.Figure(
        go.Scatter(
            x=totals.index, y=ratio, mode="lines+markers", name="Debt-to-assets",
            line=dict(color=NAVY, width=2), marker=dict(size=8, color=NAVY, line=dict(color=SURFACE, width=2)),
            hovertemplate="%{x|%b %-d, %Y}<br><b>%{y:.1%}</b><extra></extra>",
        )
    )
    fig.add_hline(y=0.2, line=dict(color=MUTED, width=1, dash="dash"),
                  annotation_text="20% guideline", annotation_position="top left",
                  annotation_font=dict(color=MUTED, size=12))
    fig = style_fig(fig, height=380, money_axis=False)
    fig.update_yaxes(tickformat=".0%", rangemode="tozero")
    fig.update_layout(showlegend=False)
    return fig


# ---------------------------------------------------------------------------
# HTML blocks
# ---------------------------------------------------------------------------
def kpi(label, value, delta=None, direction=None):
    d = f'<div class="delta {direction or ""}">{delta}</div>' if delta else ""
    return f'<div class="kpi"><div class="label">{label}</div><div class="value">{value}</div>{d}</div>'


STATUS = {
    "good": (GOOD, "✓", "On track"),
    "warning": (WARNING, "!", "Watch"),
    "critical": (CRITICAL, "✕", "Needs attention"),
}


def check_row(status, title, detail, figure):
    color, icon, label = STATUS[status]
    return (
        f'<div class="check"><div class="icon" style="background:{color}">{icon}</div>'
        f'<div><div class="title">{title}</div><div class="detail">{detail}</div></div>'
        f'<div><div class="figure">{figure}</div><div class="status">{label}</div></div></div>'
    )


def statement_table(rows, columns, total=None):
    head = "".join(f'<th class="{c[1]}">{c[0]}</th>' for c in columns)
    body = ""
    for r in rows:
        body += "<tr>" + "".join(f'<td class="{c[1]}">{r[i]}</td>' for i, c in enumerate(columns)) + "</tr>"
    if total:
        body += '<tr class="total">' + "".join(f'<td class="{c[1]}">{total[i]}</td>' for i, c in enumerate(columns)) + "</tr>"
    return f'<div class="table-wrap"><table class="stmt"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def colored(x, text=None, invert=False):
    text = text if text is not None else signed_money(x)
    good = x < 0 if invert else x > 0
    cls = "pos" if good and abs(x) >= 0.5 else ("neg" if abs(x) >= 0.5 else "")
    return f'<span class="{cls}">{text}</span>'


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Real estate
# ---------------------------------------------------------------------------
HOME_LOAN_WORDS = ("mort", "equity", "heloc")
GENERIC_WORDS = {"estate", "property", "mortgage", "mort", "loan", "home", "house", "line", "credit"}
SERIES_ORDER = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]


def key_tokens(name):
    """Distinctive words in an account name, cut to 5 letters so 'Pawleys' matches 'Pawley'."""
    words = re.findall(r"[a-z]+", str(name).lower())
    return {w[:5] for w in words if len(w) >= 4 and w not in GENERIC_WORDS}


def link_home_loans(df):
    """Match each debt to the property it is secured by, using shared words in the names.

    Returns {loan: property or None}. Debts that look like home loans but match no property map to None;
    debts that are not home loans (cards, car and student loans) are left out."""
    props = sorted(df.loc[df["account_type"] == "real estate", "account_name"].unique())
    links = {}
    for loan in sorted(df.loc[df["account_type"] == "debt", "account_name"].unique()):
        match = next((p for p in props if key_tokens(loan) & key_tokens(p)), None)
        if match or any(w in loan.lower() for w in HOME_LOAN_WORDS):
            links[loan] = match
    return props, links


def equity_chart(value, owed):
    equity = value - owed
    width = bar_width_ms(value.index)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=equity.index, y=equity, name="Equity (yours)", width=width,
        marker=dict(color=TYPE_COLORS["real estate"], line=dict(color=SURFACE, width=1.5)),
        hovertemplate="%{y:$,.0f}",
    ))
    fig.add_trace(go.Bar(
        x=owed.index, y=owed, name="Owed on home loans", width=width,
        marker=dict(color=TYPE_COLORS["debt"], line=dict(color=SURFACE, width=1.5)),
        hovertemplate="%{y:$,.0f}",
    ))
    fig.add_trace(go.Scatter(
        x=value.index, y=value, name="Property value", mode="lines",
        line=dict(color=INK, width=2), hovertemplate="<b>%{y:$,.0f}</b>",
    ))
    fig.update_layout(barmode="stack", hovermode="x unified", bargap=0)
    return style_fig(fig, height=400)


def property_values_chart(wide, props):
    fig = go.Figure()
    for i, p in enumerate(props):
        s = wide[p].dropna()
        s = s[s > 0]
        color = SERIES_ORDER[i % len(SERIES_ORDER)]
        fig.add_trace(go.Scatter(
            x=s.index, y=s, name=pretty(p), mode="lines+markers",
            line=dict(color=color, width=2), marker=dict(size=7, color=color, line=dict(color=SURFACE, width=1.5)),
            hovertemplate="%{x|%b %Y}<br><b>%{y:$,.0f}</b><extra>" + escape(pretty(p)) + "</extra>",
        ))
    fig.update_layout(hovermode="closest")
    return style_fig(fig, height=400)


def render_real_estate(df, wide, totals, latest, latest_date):
    props, links = link_home_loans(df)
    filled = wide.fillna(0)
    value = filled[props].sum(axis=1)
    owed = -filled[[l for l in links if l in filled.columns]].sum(axis=1) if links else value * 0
    owned = [p for p in props if p in set(latest["account_name"])]
    value_now, owed_now = value.iloc[-1], owed.iloc[-1]
    equity_now = value_now - owed_now
    nw_now = totals["net_worth"].iloc[-1]
    ltv = owed_now / value_now if value_now else np.nan
    first_i = value[value > 0].index.min()
    share_then = (value - owed).loc[first_i] / totals["net_worth"].loc[first_i] if first_i is not None else np.nan

    tiles = [
        kpi("Property value", money(value_now), f"{len(owned)} properties owned"),
        kpi("Owed on home loans", money(owed_now), f"{pct(ltv)} of property value (loan-to-value)"),
        kpi("Home equity", money(equity_now), f"{signed_money(equity_now - (value - owed).iloc[0])} since {value.index[0].year}",
            "up" if equity_now >= (value - owed).iloc[0] else "down"),
        kpi("Share of net worth", pct(equity_now / nw_now) if nw_now else "—",
            f"was {pct(share_then)} in {first_i.year}" if first_i is not None else None),
    ]
    st.markdown(f'<div class="kpis">{"".join(tiles)}</div>', unsafe_allow_html=True)

    c1, c2 = st.columns([1.3, 1], gap="large")
    with c1:
        section("Equity built over time", "Each bar is total property value, split into what you own outright and what is still owed.")
        st.plotly_chart(equity_chart(value, owed), config={"displayModeBar": False})
    with c2:
        section("Value of each property", "Recorded values, including properties since sold.")
        st.plotly_chart(property_values_chart(wide, props), config={"displayModeBar": False})

    section("Property detail", "Loans are matched to a property by the words in their names. Growth per year compares the first and last recorded values.")
    rows = []
    for p in sorted(props, key=lambda p: (p not in owned, -wide[p].fillna(0).iloc[-1])):
        s = wide[p].dropna()
        s = s[s > 0]
        loans = [l for l, prop in links.items() if prop == p]
        is_owned = p in owned
        val = s.iloc[-1]
        loan_now = (-sum(filled[l].iloc[-1] for l in loans) + 0.0) if is_owned else 0.0  # + 0.0 avoids "-0.0%"
        days = (s.index[-1] - s.index[0]).days
        growth = (val / s.iloc[0]) ** (365 / days) - 1 if days >= 365 and s.iloc[0] > 0 else np.nan
        payoff = "—"
        for l in loans:
            ls = -wide[l].dropna()
            ls = ls[ls > 0]
            if is_owned and len(ls) >= 2 and ls.index[-1] == latest_date:
                t = linear_trend(ls.index[-5:], ls.iloc[-5:])
                if t and t[0] < 0:
                    payoff = (latest_date + timedelta(days=ls.iloc[-1] / -t[0] * DAYS_PER_MONTH)).strftime("%b %Y")
        rows.append([
            f'<span class="swatch" style="background:{TYPE_COLORS["real estate"]}"></span>{escape(pretty(p))}',
            "Owned" if is_owned else f"Sold or removed after {s.index[-1].year}",
            f"{money(s.iloc[0])} in {s.index[0].year}",
            money(val) + ("" if is_owned else f' <span style="color:{MUTED}">({s.index[-1].year})</span>'),
            pct(growth, signed=True),
            ", ".join(escape(pretty(l)) for l in loans) or "—",
            money(loan_now) if is_owned else "—",
            money(val - loan_now) if is_owned else "—",
            pct(loan_now / val) if is_owned else "—",
            payoff,
        ])
    unlinked = [l for l, prop in links.items() if prop is None and filled[l].iloc[-1] < 0]
    if unlinked:
        amt = -sum(filled[l].iloc[-1] for l in unlinked)
        rows.append([
            "Other home loans", "Not matched to a property", "—", "—", "—",
            ", ".join(escape(pretty(l)) for l in unlinked), money(amt), money(-amt), "—", "—",
        ])
    st.markdown(statement_table(rows, [
        ("Property", ""), ("Status", ""), ("First recorded", "num"), ("Latest value", "num"), ("Growth per year", "num"),
        ("Linked loans", ""), ("Owed", "num"), ("Equity", "num"), ("Loan-to-value", "num"), ("Loan paid off ≈", "num"),
    ]), unsafe_allow_html=True)
    st.markdown(
        '<div class="footnote">Property values are the estimates recorded in your statements, not appraisals. '
        "Payoff dates extend the paydown pace of each loan's last five statements.</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Retirement income
# ---------------------------------------------------------------------------
PLAN_CATEGORIES = ["withdrawal", "pension", "guaranteed income", "social security", "salary"]
PLAN_LABELS = {
    "withdrawal": "Retirement withdrawals", "pension": "Pension", "guaranteed income": "Pension & Social Security",
    "social security": "Social Security", "salary": "Salary",
}
PLAN_COLORS = {
    "withdrawal": "#2a78d6", "pension": "#eb6834", "guaranteed income": "#eb6834",
    "social security": "#1baf7a", "salary": "#eda100",
}
GUIDELINE_RATE = 0.04


@st.cache_data
def load_plan(path, mtime=None):  # mtime busts the cache when the file changes
    plan = pd.read_csv(path)
    plan.columns = [c.strip().lower() for c in plan.columns]
    plan["category"] = plan["category"].astype(str).str.strip().str.lower()
    plan["year"] = pd.to_numeric(plan["year"], errors="coerce").astype("Int64")
    plan["amount"] = pd.to_numeric(plan["amount"], errors="coerce")
    return plan.dropna(subset=["year", "amount"])


def year_end_balance(series, year):
    s = series[series.index <= pd.Timestamp(year, 12, 31)]
    return s.iloc[-1] if len(s) else np.nan


def retirement_model(ret, plan, latest_date, annual_return, horizon=20):
    """Year-by-year withdrawals, guaranteed income and a savings projection.

    The latest statement is treated as the balance at the end of its year, so this year's withdrawals
    are assumed to be already reflected in it. Withdrawals after the last plan year stay flat."""
    cur = latest_date.year
    by_cat = plan.pivot_table(index="year", columns="category", values="amount", aggfunc="sum").fillna(0) if len(plan) else pd.DataFrame()
    by_cat.index = by_cat.index.astype(int)
    withdrawals = by_cat.get("withdrawal", pd.Series(dtype=float))
    plan_years = [y for y in by_cat.index if y >= cur]
    last_w = withdrawals.loc[max(withdrawals.index)] if len(withdrawals) else 0.0
    end_year = max([cur + horizon] + plan_years)

    def project(rate):
        bal, out = ret.iloc[-1], {cur: ret.iloc[-1]}
        for y in range(cur + 1, end_year + 1):
            w = withdrawals.get(y, last_w if y > max(withdrawals.index, default=cur) else 0.0)
            bal = max(bal * (1 + rate) - w, 0.0)
            out[y] = bal
        return pd.Series(out)

    proj = project(annual_return)
    start_balance = {}
    for y in sorted(set(by_cat.index) | set(range(cur, end_year + 1))):
        start_balance[y] = year_end_balance(ret, y - 1) if y - 1 <= cur else proj.get(y - 1, np.nan)
    return dict(
        cur=cur, by_cat=by_cat, withdrawals=withdrawals, last_w=last_w, proj=proj,
        proj_low=project(annual_return - 0.02), proj_high=project(annual_return + 0.02),
        start_balance=pd.Series(start_balance),
    )


def income_chart(by_cat, annual_spend, cur):
    fig = go.Figure()
    years = list(by_cat.index)
    for c in [c for c in PLAN_CATEGORIES if c in by_cat.columns]:
        fig.add_trace(go.Bar(
            x=years, y=by_cat[c], name=PLAN_LABELS[c],
            marker=dict(color=PLAN_COLORS[c], line=dict(color=SURFACE, width=1.5)),
            hovertemplate="%{y:$,.0f}",
        ))
    if annual_spend:
        fig.add_trace(go.Scatter(
            x=[years[0] - 0.45, years[-1] + 0.45], y=[annual_spend] * 2, name="Budgeted spending", mode="lines",
            line=dict(color=INK, width=2, dash="dash"), hovertemplate="%{y:$,.0f}",
        ))
    if years[0] <= cur:
        fig.add_vline(x=cur + 0.5, line=dict(color=BASELINE, width=1),
                      annotation_text="Planned", annotation_position="top right", annotation_font=dict(color=MUTED, size=12))
    fig.update_layout(barmode="stack", hovermode="x unified", bargap=0.35)
    fig = style_fig(fig, height=400)
    fig.update_xaxes(tickmode="linear", dtick=1, tickformat="d")
    return fig


def withdrawal_rate_chart(withdrawals, start_balance, cur):
    years = [y for y in withdrawals.index if withdrawals[y] > 0]
    rates = [withdrawals[y] / start_balance.get(y, np.nan) for y in years]
    fig = go.Figure(go.Bar(
        x=years, y=rates, marker=dict(color=[TYPE_COLORS["retirement"] if y <= cur else "#86b6ef" for y in years],
                                      line=dict(color=SURFACE, width=1.5)),
        text=[pct(r) for r in rates], textposition="outside", textfont=dict(color=INK, size=12),
        customdata=[withdrawals[y] for y in years],
        hovertemplate="%{x}: %{y:.1%} of savings (%{customdata:$,.0f})<extra></extra>",
    ))
    fig.add_hline(y=GUIDELINE_RATE, line=dict(color=MUTED, width=1, dash="dash"))
    fig = style_fig(fig, height=400, money_axis=False)
    fig.update_yaxes(tickformat=".0%", rangemode="tozero")
    fig.update_xaxes(tickmode="linear", dtick=1, tickformat="d")
    fig.update_layout(showlegend=False, bargap=0.35)
    return fig


def savings_outlook_chart(ret, m, annual_return):
    fig = go.Figure()
    hist = ret[ret > 0]
    fig.add_trace(go.Scatter(
        x=hist.index, y=hist, name="Recorded", mode="lines+markers",
        line=dict(color=TYPE_COLORS["retirement"], width=2),
        marker=dict(size=6, color=TYPE_COLORS["retirement"], line=dict(color=SURFACE, width=1.5)),
        hovertemplate="%{x|%b %Y}<br><b>%{y:$,.0f}</b><extra>Recorded</extra>",
    ))
    start = hist.index[-1]

    def xs(series):
        return [start] + [pd.Timestamp(y, 12, 31) for y in series.index[1:]]

    for series, name, dash, width in [
        (m["proj_high"], f"At {annual_return + 0.02:.1%} a year", "dot", 1.5),
        (m["proj"], f"At {annual_return:.1%} a year", "dash", 2.5),
        (m["proj_low"], f"At {annual_return - 0.02:.1%} a year", "dot", 1.5),
    ]:
        fig.add_trace(go.Scatter(
            x=xs(series), y=series.values, name=name, mode="lines",
            line=dict(color=TYPE_COLORS["retirement"] if width > 2 else MUTED, width=width, dash=dash),
            hovertemplate="%{x|%Y}<br>%{y:$,.0f}<extra>" + name + "</extra>",
        ))
    end = m["proj"]
    fig.add_annotation(x=pd.Timestamp(end.index[-1], 12, 31), y=end.iloc[-1], text=f"<b>{money(end.iloc[-1])}</b>",
                       showarrow=False, yshift=14, font=dict(color=INK, size=13))
    fig.update_layout(hovermode="x unified")
    fig = style_fig(fig, height=420)
    fig.update_yaxes(rangemode="tozero")
    return fig


def render_retirement(by_type, latest_date, plan, plan_name, cfg):
    if "retirement" not in by_type.columns or by_type["retirement"].iloc[-1] <= 0:
        st.info("No retirement accounts on the latest statement.")
        return
    ret = by_type["retirement"]
    bal = ret.iloc[-1]
    annual_spend = cfg["expenses"] * 12
    r = cfg["ret_return"]
    m = retirement_model(ret, plan, latest_date, r)
    cur, by_cat, withdrawals = m["cur"], m["by_cat"], m["withdrawals"]
    w_cur = withdrawals.get(cur, 0.0)
    guaranteed = by_cat[[c for c in ["pension", "social security", "guaranteed income"] if c in by_cat.columns]].sum(axis=1) if len(by_cat) else pd.Series(dtype=float)
    g_cur = guaranteed.get(cur, 0.0)
    start_cur = m["start_balance"].get(cur, np.nan)
    rate_cur = w_cur / start_cur if w_cur and start_cur else np.nan
    proj = m["proj"]
    ten = cur + 10

    tiles = [
        kpi("Retirement savings", money(bal), f"4% guideline: {money(bal * GUIDELINE_RATE)} a year"),
        kpi(f"Withdrawals in {cur}", money(w_cur),
            f"{pct(rate_cur)} of savings at the start of the year" if w_cur else "None planned this year"),
        kpi(f"Pension & Social Security in {cur}", money(g_cur),
            f"Covers {g_cur / annual_spend:.0%} of budgeted spending" if annual_spend else None),
        kpi(f"Projected savings in {ten}", money(proj.get(ten, np.nan)), f"At {r:.1%} a year, after planned withdrawals"),
    ]
    st.markdown(f'<div class="kpis">{"".join(tiles)}</div>', unsafe_allow_html=True)

    # Plain-language findings --------------------------------------------------
    findings = []
    if w_cur:
        status = "good" if rate_cur <= GUIDELINE_RATE else "warning" if rate_cur <= 0.05 else "critical"
        findings.append(check_row(
            status, f"Withdrawal rate in {cur}",
            f"{money(w_cur)} taken from {money(start_cur)} in savings. A 4% starting rate is a common rule of thumb for savings lasting 30 years.",
            pct(rate_cur)))
    if annual_spend and (w_cur or g_cur):
        need = max(annual_spend - g_cur, 0)
        extra = w_cur - need
        findings.append(check_row(
            "good" if extra >= 0 else "warning", "Spending gap",
            f"Budgeted spending of {money(annual_spend)} minus {money(g_cur)} in pension and Social Security leaves {money(need)} to draw from savings. "
            + (f"Planned withdrawals are {money(extra)} more than that." if extra >= 0 else f"Planned withdrawals fall {money(-extra)} short."),
            signed_money(extra)))
    depleted = proj[proj <= 0]
    if len(depleted):
        findings.append(check_row(
            "critical", "Savings outlook", f"At {r:.1%} a year and the planned withdrawals, savings run out around {depleted.index[0]}.",
            str(depleted.index[0])))
    else:
        below = proj[proj < bal]
        detail = (f"At {r:.1%} a year, savings stay above today's {money(bal)} through {proj.index[-1]}."
                  if not len(below) else
                  f"At {r:.1%} a year, savings drift below today's {money(bal)} from {below.index[0]} but last past {proj.index[-1]}.")
        findings.append(check_row("good" if not len(below) else "warning", "Savings outlook", detail, money(proj.iloc[-1])))
    past = withdrawals[withdrawals.index <= cur]
    if len(past):
        y0 = int(past.index.min())
        bal0 = year_end_balance(ret, y0 - 1)
        if not np.isnan(bal0):
            findings.append(check_row(
                "good" if bal >= bal0 else "warning", "Withdrawals so far",
                f"{money(past.sum())} withdrawn since {y0}, while retirement savings went from {money(bal0)} to {money(bal)}.",
                signed_money(bal - bal0)))

    c1, c2 = st.columns([1.4, 1], gap="large")
    with c1:
        section("Savings outlook", "Recorded retirement savings, then projected after planned withdrawals. Dotted lines show returns 2 points higher and lower.")
        st.plotly_chart(savings_outlook_chart(ret, m, r), config={"displayModeBar": False})
    with c2:
        section("What this shows", "Based on your plan and the latest statement.")
        st.markdown(f'<div class="panel">{"".join(findings)}</div>', unsafe_allow_html=True)

    if len(by_cat) and (len(withdrawals) or len(guaranteed)):
        c1, c2 = st.columns([1.4, 1], gap="large")
        with c1:
            section("Where the money comes from each year", "Income and withdrawals by year against your budgeted spending.")
            st.plotly_chart(income_chart(by_cat, annual_spend, cur), config={"displayModeBar": False})
        with c2:
            section("Withdrawal rate by year", "Withdrawals as a share of retirement savings at the start of each year. Lighter bars are planned; the dashed line is the 4% guideline.")
            if len(withdrawals[withdrawals > 0]):
                st.plotly_chart(withdrawal_rate_chart(withdrawals, m["start_balance"], cur), config={"displayModeBar": False})

        section("Year by year")
        rows = []
        for y in by_cat.index:
            row = by_cat.loc[y]
            total = sum(row.get(c, 0) for c in PLAN_CATEGORIES)
            w = row.get("withdrawal", 0)
            sb = m["start_balance"].get(y, np.nan)
            rows.append([
                str(y) + ("" if y <= cur else f' <span style="color:{MUTED}">planned</span>'),
                money(row.get("salary", 0)), money(row.get("pension", 0) + row.get("guaranteed income", 0)),
                money(row.get("social security", 0)), money(w), money(total),
                colored(total - annual_spend) if annual_spend else "—",
                pct(w / sb) if w and sb else "—",
            ])
        st.markdown(statement_table(rows, [
            ("Year", ""), ("Salary", "num"), ("Pension", "num"), ("Social Security", "num"), ("Withdrawals", "num"),
            ("Total", "num"), ("vs. budget", "num"), ("Withdrawal rate", "num"),
        ]), unsafe_allow_html=True)

    source = f"from {escape(plan_name)}" if plan_name else "from the sidebar"
    st.markdown(
        f'<div class="footnote">Income and withdrawals come {source}. Budgeted spending uses the monthly expenses in the sidebar, held flat. '
        "Projections assume a steady return with no inflation, taxes or new contributions, and treat the latest statement as the "
        "year-end balance. They are estimates, not financial advice.</div>",
        unsafe_allow_html=True,
    )


def sidebar():
    with st.sidebar:
        st.markdown("## Data")
        csvs = sorted(os.path.basename(p) for p in glob.glob(os.path.join(APP_DIR, "*.csv")) if not p.endswith("_plan.csv"))
        source, source_name = None, None
        if csvs:
            idx = csvs.index(DEFAULT_DATA_FILE) if DEFAULT_DATA_FILE in csvs else 0
            choice = st.selectbox("Statement file", csvs, index=idx, help="CSV files found next to dashboard.py")
            path = os.path.join(APP_DIR, choice)
            source, source_name, mtime = path, choice, os.path.getmtime(path)
        uploaded = st.file_uploader("Or upload a CSV", type=["csv"])
        if uploaded is not None:
            source, source_name, mtime = uploaded, uploaded.name, None
        if source is None:
            return None
        df = load_data(source, mtime=mtime) if uploaded is None else load_data(uploaded)

        # Optional retirement plan: '<statement file>_plan.csv' next to it (year, category, source, amount).
        plan, plan_name = None, None
        plan_upload = st.file_uploader(
            "Retirement plan CSV (optional)", type=["csv"],
            help="Columns: year, category, source, amount. Categories: salary, pension, social security, withdrawal, spending.",
        )
        if plan_upload is not None:
            plan, plan_name = load_plan(plan_upload), plan_upload.name
        elif uploaded is None:
            plan_path = os.path.splitext(source)[0] + "_plan.csv"
            if os.path.exists(plan_path):
                plan, plan_name = load_plan(plan_path, mtime=os.path.getmtime(plan_path)), os.path.basename(plan_path)
                st.caption(f"Retirement plan: {plan_name}")
        default_expenses = DEFAULT_MONTHLY_EXPENSES
        if plan is not None and (plan["category"] == "spending").any():
            spend = plan[plan["category"] == "spending"].sort_values("year")["amount"].iloc[-1]
            default_expenses = int(round(spend / 12, -2))

        st.markdown("## Period")
        dates = sorted(df["date"].dt.date.unique())
        start, end = st.select_slider(
            "Snapshots to include",
            options=dates,
            value=(dates[0], dates[-1]),
            format_func=lambda d: pd.Timestamp(d).strftime("%b %Y"),
        ) if len(dates) > 1 else (dates[0], dates[0])
        df = df[(df["date"].dt.date >= start) & (df["date"].dt.date <= end)]

        st.markdown("## Your numbers")
        expenses = st.number_input(
            "Monthly living expenses", min_value=0, value=default_expenses, step=100,
            help="Used to measure emergency-fund coverage. Rent, food, bills, insurance, loan payments.",
        )
        ef_target = st.slider("Emergency fund target (months)", 1, 12, DEFAULT_EMERGENCY_TARGET_MONTHS)
        latest = df[df["date"] == df["date"].max()]
        asset_accounts = sorted(latest[latest["value"] > 0]["account_name"].unique())
        ef_default = [a for a in asset_accounts if "emergency" in a.lower()] or sorted(
            latest[latest["account_type"] == "savings"]["account_name"].unique()
        )
        ef_accounts = st.multiselect("Accounts that count as emergency savings", asset_accounts, default=ef_default)

        goal_options = ["None"] + asset_accounts
        goal_idx = goal_options.index(DEFAULT_GOAL_ACCOUNT) if DEFAULT_GOAL_ACCOUNT in goal_options else 0
        goal_account = st.selectbox("Savings goal account", goal_options, index=goal_idx)
        goal_target = 0
        if goal_account != "None":
            goal_target = st.number_input("Goal target", min_value=0, value=DEFAULT_GOAL_TARGET, step=1000)

        st.markdown("## Retirement")
        ret_return = st.slider(
            "Expected yearly return", 0.0, 10.0, DEFAULT_RETIREMENT_RETURN, 0.5, format="%.1f%%",
            help="Used to project retirement savings. Long-run averages for a balanced portfolio are often quoted at 4-6%.",
        ) / 100
        if plan is None:
            withdrawal = st.number_input("Planned yearly withdrawals", min_value=0, value=0, step=1000)
            guaranteed = st.number_input("Yearly pension + Social Security", min_value=0, value=0, step=1000)
            year = int(df["date"].max().year)
            plan = pd.DataFrame(
                [(year, "withdrawal", "Planned withdrawals", withdrawal),
                 (year, "guaranteed income", "Pension & Social Security", guaranteed)],
                columns=["year", "category", "source", "amount"],
            )
            plan = plan[plan["amount"] > 0]
        else:
            plan = plan[plan["category"] != "spending"]

    return dict(
        df=df, source_name=source_name, expenses=expenses, ef_target=ef_target,
        ef_accounts=ef_accounts, goal_account=goal_account, goal_target=goal_target,
        plan=plan, plan_name=plan_name, ret_return=ret_return,
    )


def empty_state():
    st.markdown(
        '<div class="masthead"><div><h1>Personal Financial Statement</h1>'
        '<div class="sub">Add a CSV of account balances to build your statement.</div></div></div>',
        unsafe_allow_html=True,
    )
    section("Expected format", "One row per account per snapshot date. Enter debts as negative values.")
    st.dataframe(
        pd.DataFrame(
            {
                "account_name": ["emergency fund", "brokerage account", "student loans"],
                "account_type": ["savings", "investments", "debt"],
                "account_institution": ["Bank A", "Broker B", "Lender C"],
                "value": [5000, 15000, -25000],
                "date": ["2024-01-01", "2024-01-01", "2024-01-01"],
            }
        ),
        width="stretch",
    )


def main():
    cfg = sidebar()
    if cfg is None or cfg["df"].empty:
        empty_state()
        return

    df = cfg["df"]
    wide, by_type, totals = build_frames(df)
    meta = account_meta(df)
    latest_date = totals.index[-1]
    latest = df[df["date"] == latest_date]
    latest_by_type = by_type.iloc[-1]
    n_snap = len(totals)

    nw = totals["net_worth"].iloc[-1]
    assets = totals["assets"].iloc[-1]
    debts = totals["debts"].iloc[-1]
    prev = totals.iloc[-2] if n_snap > 1 else None
    first = totals.iloc[0]
    span_days = (latest_date - totals.index[0]).days
    nw_trend = linear_trend(totals.index, totals["net_worth"])
    nw_per_month = nw_trend[0] if nw_trend else 0.0

    ef_balance = latest[latest["account_name"].isin(cfg["ef_accounts"])]["value"].sum()
    ef_months = ef_balance / cfg["expenses"] if cfg["expenses"] else np.nan
    debt_ratio = debts / assets if assets else np.nan

    # Masthead ---------------------------------------------------------------
    institutions = latest["account_institution"].nunique()
    st.markdown(
        f"""
<div class="masthead">
  <div>
    <h1>Personal Financial Statement</h1>
    <div class="sub">{len(latest)} accounts across {institutions} institutions, {n_snap} statements on file ({escape(cfg['source_name'])})</div>
  </div>
  <div class="asof">Statement date<strong>{fmt_date(latest_date)}</strong>Covering {fmt_date(totals.index[0])} onward</div>
</div>
""",
        unsafe_allow_html=True,
    )

    # KPI strip --------------------------------------------------------------
    since = f"since {pd.Timestamp(prev.name).strftime('%b %-d')}" if prev is not None else ""
    nw_delta = nw - prev["net_worth"] if prev is not None else 0
    asset_delta = assets - prev["assets"] if prev is not None else 0
    debt_delta = debts - prev["debts"] if prev is not None else 0
    tiles = [
        kpi("Net worth", money(nw), f"{signed_money(nw_delta)} {since}", "up" if nw_delta > 0 else "down" if nw_delta < 0 else None),
        kpi("Total assets", money(assets), f"{signed_money(asset_delta)} {since}", "up" if asset_delta > 0 else "down" if asset_delta < 0 else None),
        kpi("Total debt", money(debts), f"{signed_money(debt_delta)} {since}", "up" if debt_delta < 0 else "down" if debt_delta > 0 else None),
        kpi("Net worth pace", f"{signed_money(nw_per_month)}/mo",
            f"Trend across {n_snap} statements" if nw_trend else "Needs two or more statements"),
    ]
    st.markdown(f'<div class="kpis">{"".join(tiles)}</div>', unsafe_allow_html=True)

    has_real_estate = (df["account_type"] == "real estate").any()
    tab_names = ["Overview", "Growth", "Allocation"] + (["Real estate"] if has_real_estate else []) + ["Retirement", "Debt", "Records"]
    tabs = dict(zip(tab_names, st.tabs(tab_names)))
    tab_overview, tab_growth, tab_alloc, tab_debt, tab_records = (
        tabs[n] for n in ["Overview", "Growth", "Allocation", "Debt", "Records"]
    )
    if has_real_estate:
        with tabs["Real estate"]:
            render_real_estate(df, wide, totals, latest, latest_date)
    with tabs["Retirement"]:
        render_retirement(by_type, latest_date, cfg["plan"], cfg["plan_name"], cfg)

    # Overview ---------------------------------------------------------------
    with tab_overview:
        left, right = st.columns([1.55, 1], gap="large")
        with left:
            section("Balance sheet over time", "Assets stack above zero by type, debt sits below, and the line is net worth.")
            st.plotly_chart(balance_sheet_chart(by_type, totals), config={"displayModeBar": False})
        with right:
            section("Health check", "Common rules of thumb applied to your latest statement.")
            checks = []

            if cfg["expenses"] and cfg["ef_accounts"]:
                status = "good" if ef_months >= cfg["ef_target"] else "warning" if ef_months >= 3 else "critical"
                checks.append(check_row(
                    status, "Emergency fund",
                    f"{money(ef_balance)} covers {ef_months:.1f} months of {money(cfg['expenses'])} expenses. Target is {cfg['ef_target']} months.",
                    f"{ef_months:.1f} mo",
                ))

            status = "good" if debt_ratio < 0.2 else "warning" if debt_ratio < 0.4 else "critical"
            checks.append(check_row(
                status, "Debt-to-assets",
                f"You owe {money(debts)} against {money(assets)} in assets. Under 20% is a common target.",
                pct(debt_ratio),
            ))

            if n_snap >= 2:
                recent = totals["net_worth"].iloc[-min(3, n_snap)]
                recent_ch = nw - recent
                recent_from = totals.index[-min(3, n_snap)]
                status = "good" if recent_ch > 0 else "warning"
                checks.append(check_row(
                    status, "Net worth direction",
                    f"{signed_money(recent_ch)} since {fmt_date(recent_from)}; {signed_money(nw - first['net_worth'])} since {fmt_date(first.name)}.",
                    signed_money(recent_ch),
                ))

            debt_accounts = sorted(latest[latest["value"] < 0]["account_name"].unique())
            if debts > 0:
                dt = linear_trend(totals.index, totals["debts"])
                if dt and dt[0] < -1:
                    months_left = debts / -dt[0]
                    payoff = latest_date + timedelta(days=months_left * DAYS_PER_MONTH)
                    checks.append(check_row(
                        "good", "Debt payoff pace",
                        f"Paying down about {money(-dt[0])} a month. At this pace you are debt-free around {payoff.strftime('%B %Y')}.",
                        payoff.strftime("%b %Y"),
                    ))
                else:
                    checks.append(check_row(
                        "warning", "Debt payoff pace",
                        "Debt is not trending down across these statements.", "Flat",
                    ))
            else:
                checks.append(check_row("good", "Debt", "No debt on the latest statement.", "$0"))

            accessible = sum(latest_by_type.get(t, 0) for t in ["savings", "investments"])
            if cfg["expenses"]:
                acc_months = accessible / cfg["expenses"]
                status = "good" if acc_months >= 12 else "warning"
                checks.append(check_row(
                    status, "Accessible money",
                    f"{money(accessible)} sits outside retirement accounts, about {acc_months:.0f} months of expenses you could reach before retirement age.",
                    f"{accessible / assets:.0%} of assets",
                ))

            if "retirement" in by_type.columns and len(cfg["plan"]):
                m = retirement_model(by_type["retirement"], cfg["plan"], latest_date, cfg["ret_return"])
                w_cur, start = m["withdrawals"].get(m["cur"], 0.0), m["start_balance"].get(m["cur"], np.nan)
                if w_cur and start:
                    rate = w_cur / start
                    status = "good" if rate <= GUIDELINE_RATE else "warning" if rate <= 0.05 else "critical"
                    checks.append(check_row(
                        status, "Retirement withdrawal rate",
                        f"{money(w_cur)} planned for {m['cur']} from {money(start)} in retirement savings. 4% or less is a common guideline.",
                        pct(rate),
                    ))

            st.markdown(f'<div class="panel">{"".join(checks)}</div>', unsafe_allow_html=True)

            if cfg["goal_account"] != "None":
                goal_bal = latest[latest["account_name"] == cfg["goal_account"]]["value"].sum()
                section(f"Goal: {escape(pretty(cfg['goal_account']))}")
                if cfg["goal_target"] > 0:
                    progress = min(goal_bal / cfg["goal_target"], 1)
                    s = df[df["account_name"] == cfg["goal_account"]].sort_values("date")
                    gt = linear_trend(s["date"], s["value"])
                    eta = ""
                    if gt and gt[0] > 0 and goal_bal < cfg["goal_target"]:
                        months = (cfg["goal_target"] - goal_bal) / gt[0]
                        eta = f" Saving about {money(gt[0])} a month, you reach it around {(latest_date + timedelta(days=months * DAYS_PER_MONTH)).strftime('%B %Y')}."
                    st.markdown(
                        f'<div class="panel" style="padding:1rem 1.2rem"><b>{money(goal_bal)}</b> of {money(cfg["goal_target"])} ({progress:.0%})'
                        f'<div class="bar-track"><div class="bar-fill" style="width:{progress * 100:.1f}%"></div></div>'
                        f'<div class="detail" style="color:{INK_2};font-size:0.88rem">{eta.strip() or "Goal reached." if progress >= 1 else eta.strip()}</div></div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f'<div class="panel" style="padding:1rem 1.2rem">{money(goal_bal)} saved. Set a goal target in the sidebar to track progress and an estimated finish date.</div>',
                        unsafe_allow_html=True,
                    )

    # Growth -----------------------------------------------------------------
    with tab_growth:
        if n_snap < 2:
            st.info("Growth needs at least two statements in the selected period.")
        else:
            c1, c2 = st.columns(2, gap="large")
            with c1:
                section(
                    "What moved your net worth",
                    f"Change in each account from {fmt_date(totals.index[0])} to {fmt_date(latest_date)}. Debt paid down counts as a gain.",
                )
                st.plotly_chart(change_waterfall(wide, totals), config={"displayModeBar": False})
            with c2:
                section("Twelve-month outlook", "A straight-line extension of your trend so far. Not a forecast of market returns.")
                st.plotly_chart(net_worth_projection(totals), config={"displayModeBar": False})

            section("Account performance", "Changes include your own contributions as well as market growth.")
            rows = []
            for a in wide.columns:
                s = wide[a].dropna()
                opened_later = s.index[0] > wide.index[0]
                start_v = 0.0 if opened_later else s.iloc[0]
                end_v = wide[a].iloc[-1] if not np.isnan(wide[a].iloc[-1]) else 0
                ch = end_v - start_v
                days = (s.index[-1] - s.index[0]).days
                if np.isnan(wide[a].iloc[-1]):
                    pct_s, ann_s = "closed", "—"
                elif opened_later:
                    pct_s, ann_s = "new", "—"
                elif start_v > 0 and len(s) > 1:
                    pct_s = pct(ch / start_v, signed=True)
                    ann_s = pct((end_v / start_v) ** (365 / days) - 1, signed=True) if days >= 90 else "—"
                elif start_v < 0 and len(s) > 1:
                    pct_s = pct((abs(end_v) - abs(start_v)) / abs(start_v), signed=True) + " owed"
                    ann_s = "—"
                else:
                    pct_s, ann_s = "—", "—"
                t = meta.loc[a, "account_type"]
                rows.append((
                    ch,
                    [
                        f'<span class="swatch" style="background:{type_color(t)}"></span>{escape(pretty(a))}',
                        escape(meta.loc[a, "account_institution"]),
                        type_label(t),
                        money(start_v, cents=True) + (f'<br><span style="color:{MUTED};font-size:0.8rem">opened {s.index[0].strftime("%b %Y")}</span>' if opened_later else ""),
                        money(end_v, cents=True),
                        colored(ch),
                        pct_s,
                        ann_s,
                    ],
                ))
            rows = [r for _, r in sorted(rows, key=lambda x: -x[0])]
            total_ch = nw - first["net_worth"]
            total_ann = (
                pct((nw / first["net_worth"]) ** (365 / span_days) - 1, signed=True)
                if first["net_worth"] > 0 and nw > 0 and span_days >= 90 else "—"
            )
            st.markdown(
                statement_table(
                    rows,
                    [("Account", ""), ("Institution", ""), ("Type", ""), ("Start", "num"), ("Current", "num"),
                     ("Change", "num"), ("Change %", "num"), ("Annualized", "num")],
                    total=["Net worth", "", "", money(first["net_worth"], cents=True), money(nw, cents=True),
                           colored(total_ch), pct(total_ch / first["net_worth"], signed=True) if first["net_worth"] > 0 else "—", total_ann],
                ),
                unsafe_allow_html=True,
            )

            section("Each open account on its own scale", "Debt is shown as the balance owed, so falling is good.")
            st.plotly_chart(account_multiples(df, meta), config={"displayModeBar": False})

    # Allocation -------------------------------------------------------------
    with tab_alloc:
        section("Where your assets sit today", "Grouped by how quickly you could use the money.")
        tiers = [
            ("savings", "Available now", "Cash in savings accounts."),
            ("investments", "Available within days", "Taxable investments. Selling may trigger capital gains tax."),
            ("retirement", "Set aside for retirement", "401(k) and IRA money. Early withdrawals usually carry taxes and penalties."),
        ]
        html = ""
        for t, name, note in tiers:
            v = latest_by_type.get(t, 0)
            html += (
                f'<div class="tier" style="border-top-color:{type_color(t)}"><div class="name">{name}</div>'
                f'<div class="amt">{money(v)}</div><div class="note">{v / assets:.0%} of assets. {note}</div></div>'
            )
        st.markdown(f'<div class="tiers">{html}</div>', unsafe_allow_html=True)
        st.plotly_chart(current_mix_bar(latest_by_type), config={"displayModeBar": False})

        c1, c2 = st.columns([1.4, 1], gap="large")
        with c1:
            section("Mix over time", "Share of total assets held in each type at every statement.")
            st.plotly_chart(allocation_over_time(by_type), config={"displayModeBar": False})
        with c2:
            section("By institution", "Concentration of assets with each provider.")
            inst = latest[latest["value"] > 0].groupby("account_institution")["value"].sum().sort_values()
            fig = go.Figure(
                go.Bar(
                    y=inst.index, x=inst.values, orientation="h",
                    marker=dict(color=NAVY, line=dict(color=SURFACE, width=2)),
                    text=[f"{money(v)}  ({v / inst.sum():.0%})" for v in inst.values],
                    textposition="outside", textfont=dict(color=INK, size=12),
                    hovertemplate="%{y}: %{x:$,.0f}<extra></extra>",
                )
            )
            fig = style_fig(fig, height=360, money_axis=False)
            fig.update_xaxes(visible=False, range=[0, inst.max() * 1.7])
            fig.update_yaxes(showgrid=False, tickfont=dict(color=INK, size=13))
            st.plotly_chart(fig, config={"displayModeBar": False})

    # Debt -------------------------------------------------------------------
    with tab_debt:
        debt_names = sorted(df[df["value"] < 0]["account_name"].unique())
        if not debt_names:
            st.success("No debt recorded in the selected period.")
        else:
            first_debt = totals["debts"].iloc[0]
            paid = first_debt - debts
            dt = linear_trend(totals.index, totals["debts"])
            tiles = [
                kpi("Owed today", money(debts)),
                kpi("Paid down in period", money(paid), pct(paid / first_debt) + " of the starting balance" if first_debt else None, "up" if paid > 0 else None),
                kpi("Average paydown", f"{money(-dt[0])}/mo" if dt else "—", "Trend across statements"),
                kpi("Debt-to-assets", pct(debt_ratio), f"was {pct(first_debt / first['assets'])} at start" if first["assets"] else None,
                    "up" if debt_ratio < first_debt / first["assets"] else "down"),
            ]
            st.markdown(f'<div class="kpis">{"".join(tiles)}</div>', unsafe_allow_html=True)
            c1, c2 = st.columns([1.4, 1], gap="large")
            with c1:
                section("Balance and payoff path", "Dotted line extends your average paydown to zero.")
                st.plotly_chart(debt_chart(df, debt_names), config={"displayModeBar": False})
            with c2:
                section("Debt relative to assets", "Falls when you pay debt down or your assets grow.")
                st.plotly_chart(debt_ratio_chart(totals), config={"displayModeBar": False})

    # Records ----------------------------------------------------------------
    with tab_records:
        section(f"Accounts as of {fmt_date(latest_date)}")
        rows = []
        for _, r in latest.sort_values("value", ascending=False).iterrows():
            rows.append([
                f'<span class="swatch" style="background:{type_color(r["account_type"])}"></span>{escape(pretty(r["account_name"]))}',
                escape(r["account_institution"]),
                type_label(r["account_type"]),
                money(r["value"], cents=True),
                f"{r['value'] / assets:.1%}" if r["value"] > 0 else "—",
            ])
        st.markdown(
            statement_table(
                rows,
                [("Account", ""), ("Institution", ""), ("Type", ""), ("Balance", "num"), ("Share of assets", "num")],
                total=["Net worth", "", "", money(nw, cents=True), ""],
            ),
            unsafe_allow_html=True,
        )

        section("Statement history", "Net worth at every snapshot in the selected period.")
        hist = totals.copy()
        hist["change"] = hist["net_worth"].diff()
        rows = [
            [fmt_date(d), money(r["assets"], cents=True), money(-r["debts"], cents=True), money(r["net_worth"], cents=True),
             colored(r["change"]) if not np.isnan(r["change"]) else "—"]
            for d, r in hist.iloc[::-1].iterrows()
        ]
        st.markdown(
            statement_table(rows, [("Date", ""), ("Assets", "num"), ("Debt", "num"), ("Net worth", "num"), ("Change", "num")]),
            unsafe_allow_html=True,
        )

        section("Raw data")
        raw = df[["date", "account_name", "account_type", "account_institution", "value"]].sort_values(["date", "account_name"], ascending=[False, True])
        st.dataframe(raw, width="stretch", height=320)
        st.download_button(
            "Download filtered data as CSV",
            raw.to_csv(index=False).encode(),
            file_name=f"financial_statement_{latest_date.strftime('%Y-%m-%d')}.csv",
            mime="text/csv",
        )

    st.markdown(
        '<div class="footnote">Figures come from the balances you record. Projections extend past trends in a straight line and '
        "do not account for market changes. Rules of thumb are general guidelines, not personal financial advice.</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
