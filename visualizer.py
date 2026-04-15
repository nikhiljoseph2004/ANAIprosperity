import glob

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Order Book Visualiser", layout="wide")
st.title("Order Book Visualiser")


@st.cache_data
def load_data() -> pd.DataFrame:
    files = sorted(glob.glob("round_1/data/prices_round_1_day_*.csv"))
    return (
        pd.concat([pd.read_csv(f, sep=";") for f in files], ignore_index=True)
        .sort_values(["day", "timestamp", "product"])
        .reset_index(drop=True)
    )


df = load_data()

# ── Sidebar controls ──────────────────────────────────────────────────────────
st.sidebar.header("Controls")

product = st.sidebar.selectbox("Product", sorted(df["product"].unique()))
day = st.sidebar.selectbox("Day", sorted(df["day"].unique()))

filtered = (
    df[(df["day"] == day) & (df["product"] == product)]
    .reset_index(drop=True)
)
timestamps = filtered["timestamp"].tolist()

ts_idx = st.sidebar.slider("Timestamp", 0, len(timestamps) - 1, 0)
timestamp = timestamps[ts_idx]
st.sidebar.caption(f"t = {timestamp:,}")

row = filtered.iloc[ts_idx]


# ── Helpers ───────────────────────────────────────────────────────────────────
def get_levels(row: pd.Series, side: str) -> list[tuple[float, float]]:
    """Return [(price, volume), ...] for available levels, sorted by price."""
    levels = [
        (row[f"{side}_price_{i}"], row[f"{side}_volume_{i}"])
        for i in (1, 2, 3)
        if pd.notna(row[f"{side}_price_{i}"]) and pd.notna(row[f"{side}_volume_{i}"])
    ]
    return sorted(levels, key=lambda x: x[0])


bids = get_levels(row, "bid")   # ascending price (best bid is last)
asks = get_levels(row, "ask")   # ascending price (best ask is first)


# ── Order book diverging bar chart ────────────────────────────────────────────
fig_ob = go.Figure()

if bids:
    bid_prices, bid_vols = zip(*bids)
    fig_ob.add_trace(go.Bar(
        x=[-v for v in bid_vols],
        y=list(bid_prices),
        orientation="h",
        name="Bid",
        marker_color="rgba(38, 166, 154, 0.85)",
        hovertemplate="Price: %{y}<br>Volume: %{customdata}<extra>Bid</extra>",
        customdata=list(bid_vols),
    ))

if asks:
    ask_prices, ask_vols = zip(*asks)
    fig_ob.add_trace(go.Bar(
        x=list(ask_vols),
        y=list(ask_prices),
        orientation="h",
        name="Ask",
        marker_color="rgba(239, 83, 80, 0.85)",
        hovertemplate="Price: %{y}<br>Volume: %{x}<extra>Ask</extra>",
    ))

if pd.notna(row["mid_price"]):
    fig_ob.add_hline(
        y=row["mid_price"],
        line_dash="dot",
        line_color="gold",
        annotation_text=f"Mid: {row['mid_price']:.1f}",
        annotation_font_color="gold",
    )

fig_ob.update_layout(
    title=f"Order Book  —  {product}  |  Day {day}  |  t = {timestamp:,}",
    xaxis=dict(
        title="← Bid Volume    |    Ask Volume →",
        zeroline=True,
        zerolinecolor="white",
        zerolinewidth=2,
    ),
    yaxis_title="Price",
    barmode="overlay",
    height=420,
    template="plotly_dark",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)


# ── Mid-price time series ─────────────────────────────────────────────────────
fig_mid = go.Figure()
fig_mid.add_trace(go.Scatter(
    x=filtered["timestamp"],
    y=filtered["mid_price"],
    mode="lines",
    name="Mid Price",
    line=dict(color="royalblue", width=1.5),
))
fig_mid.add_vline(
    x=timestamp,
    line_dash="dash",
    line_color="orange",
    annotation_text=f"t={timestamp:,}",
    annotation_font_color="orange",
)
fig_mid.update_layout(
    title="Mid Price over Time",
    xaxis_title="Timestamp",
    yaxis_title="Price",
    height=290,
    template="plotly_dark",
)


# ── PnL time series ───────────────────────────────────────────────────────────
fig_pnl = go.Figure()
fig_pnl.add_trace(go.Scatter(
    x=filtered["timestamp"],
    y=filtered["profit_and_loss"],
    mode="lines",
    name="PnL",
    line=dict(color="mediumpurple", width=1.5),
    fill="tozeroy",
    fillcolor="rgba(147, 112, 219, 0.2)",
))
fig_pnl.add_vline(
    x=timestamp,
    line_dash="dash",
    line_color="orange",
    annotation_text=f"t={timestamp:,}",
    annotation_font_color="orange",
)
fig_pnl.update_layout(
    title="Profit & Loss over Time",
    xaxis_title="Timestamp",
    yaxis_title="PnL",
    height=290,
    template="plotly_dark",
)


# ── Bid / Ask price levels time series ───────────────────────────────────────
# Compute tight y-axis range from all visible price columns + 20% padding
_price_cols = [
    "bid_price_1", "bid_price_2", "bid_price_3",
    "ask_price_1", "ask_price_2", "ask_price_3",
    "mid_price",
]
_all_prices = filtered[_price_cols].stack()
_p_min, _p_max = _all_prices.min(), _all_prices.max()
_pad = max((_p_max - _p_min) * 0.2, 1)   # at least ±1 tick even if spread is 0
_y_range = [_p_min - _pad, _p_max + _pad]

fig_levels = go.Figure()

# Spread fill: area between best ask and best bid
fig_levels.add_trace(go.Scatter(
    x=pd.concat([filtered["timestamp"], filtered["timestamp"].iloc[::-1]]).tolist(),
    y=pd.concat([filtered["ask_price_1"], filtered["bid_price_1"].iloc[::-1]]).tolist(),
    fill="toself",
    fillcolor="rgba(255, 255, 255, 0.06)",
    line=dict(width=0),
    hoverinfo="skip",
    showlegend=False,
    name="Spread fill",
))

# Bid levels: price_1 = best (highest), price_3 = outermost (lowest)
bid_styles = [
    ("bid_price_1", "rgba(38, 166, 154, 1.0)",   "Bid L1"),
    ("bid_price_2", "rgba(38, 166, 154, 0.55)",  "Bid L2"),
    ("bid_price_3", "rgba(38, 166, 154, 0.25)",  "Bid L3"),
]
for col, color, label in bid_styles:
    fig_levels.add_trace(go.Scatter(
        x=filtered["timestamp"],
        y=filtered[col],
        mode="lines",
        name=label,
        line=dict(color=color, width=1),
        connectgaps=False,
    ))

# Ask levels: price_1 = best (lowest), price_3 = outermost (highest)
ask_styles = [
    ("ask_price_1", "rgba(239, 83, 80, 1.0)",   "Ask L1"),
    ("ask_price_2", "rgba(239, 83, 80, 0.55)",  "Ask L2"),
    ("ask_price_3", "rgba(239, 83, 80, 0.25)",  "Ask L3"),
]
for col, color, label in ask_styles:
    fig_levels.add_trace(go.Scatter(
        x=filtered["timestamp"],
        y=filtered[col],
        mode="lines",
        name=label,
        line=dict(color=color, width=1),
        connectgaps=False,
    ))

# Mid price
fig_levels.add_trace(go.Scatter(
    x=filtered["timestamp"],
    y=filtered["mid_price"],
    mode="lines",
    name="Mid",
    line=dict(color="gold", width=1.5, dash="dot"),
    connectgaps=False,
))

fig_levels.add_vline(
    x=timestamp,
    line_dash="dash",
    line_color="orange",
    annotation_text=f"t={timestamp:,}",
    annotation_font_color="orange",
)
fig_levels.update_layout(
    title=f"Bid / Ask Price Levels over Time  —  {product}  |  Day {day}",
    xaxis_title="Timestamp",
    yaxis=dict(title="Price", range=_y_range),
    height=380,
    template="plotly_dark",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    hovermode="x unified",
)


# ── Layout ────────────────────────────────────────────────────────────────────
col_ob, col_charts = st.columns([1, 1])

with col_ob:
    st.plotly_chart(fig_ob, use_container_width=True)

    spread = (asks[0][0] - bids[-1][0]) if bids and asks else None
    m1, m2, m3 = st.columns(3)
    m1.metric("Mid Price", f"{row['mid_price']:.1f}" if pd.notna(row["mid_price"]) else "—")
    m2.metric("Spread", f"{spread:.1f}" if spread is not None else "—")
    m3.metric("PnL", f"{row['profit_and_loss']:.1f}" if pd.notna(row["profit_and_loss"]) else "—")

with col_charts:
    st.plotly_chart(fig_mid, use_container_width=True)
    st.plotly_chart(fig_pnl, use_container_width=True)

st.plotly_chart(fig_levels, use_container_width=True)
