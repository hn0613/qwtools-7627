import plotly.graph_objects as go
import streamlit as st
import yaml

from frontend.components.config_loader import get_default_config_loader
from frontend.components.save_config import render_save_config
from frontend.st_utils import get_backend_api_client, initialize_st_page

# Initialize the Streamlit page
initialize_st_page(title="XEMM Multiple Levels", icon="⚡️")

# Load config (supports edit/fork mode)
get_default_config_loader("xemm_multiple_levels")

# Read defaults from session state (populated by config_loader)
cfg = st.session_state.get("config_xemm_multiple_levels", {})

# Page content
st.text("This tool will let you create a config for XEMM Controller and upload it to the BackendAPI.")
st.write("---")
c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 1])

with c1:
    maker_connector = st.text_input("Maker Connector", value=cfg.get("maker_connector", "kucoin"))
    maker_trading_pair = st.text_input("Maker Trading Pair", value=cfg.get("maker_trading_pair", "LBR-USDT"))
with c2:
    taker_connector = st.text_input("Taker Connector", value=cfg.get("taker_connector", "okx"))
    taker_trading_pair = st.text_input("Taker Trading Pair", value=cfg.get("taker_trading_pair", "LBR-USDT"))
with c3:
    # Stored as decimal (e.g. 0.002), UI shows percentage (e.g. 0.2%)
    min_prof_display = cfg["min_profitability"] * 100 if "min_profitability" in cfg else 0.2
    max_prof_display = cfg["max_profitability"] * 100 if "max_profitability" in cfg else 1.0
    min_profitability = st.number_input("Min Profitability (%)", value=min_prof_display, step=0.01) / 100
    max_profitability = st.number_input("Max Profitability (%)", value=max_prof_display, step=0.01) / 100
with c4:
    default_buy_levels = cfg.get("buy_levels_targets_amount", [[0.003, 10]])
    buy_maker_levels = st.number_input("Buy Maker Levels", value=len(default_buy_levels), step=1)
    buy_targets_amounts = []
    c41, c42 = st.columns([1, 1])
    for i in range(buy_maker_levels):
        level_default = default_buy_levels[i] if i < len(default_buy_levels) else [0.003, 10]
        # Stored as decimal, UI shows percentage
        prof_display = level_default[0] * 100 if "buy_levels_targets_amount" in cfg else level_default[0]
        with c41:
            target_profitability = st.number_input(f"Target Profitability {i + 1} B% ", value=prof_display, step=0.01)
        with c42:
            amount = st.number_input(f"Amount {i + 1}B Quote", value=level_default[1], step=1)
        buy_targets_amounts.append([target_profitability / 100, amount])
with c5:
    default_sell_levels = cfg.get("sell_levels_targets_amount", [[0.003, 10]])
    sell_maker_levels = st.number_input("Sell Maker Levels", value=len(default_sell_levels), step=1)
    sell_targets_amounts = []
    c51, c52 = st.columns([1, 1])
    for i in range(sell_maker_levels):
        level_default = default_sell_levels[i] if i < len(default_sell_levels) else [0.003, 10]
        prof_display = level_default[0] * 100 if "sell_levels_targets_amount" in cfg else level_default[0]
        with c51:
            target_profitability = st.number_input(f"Target Profitability {i + 1}S %", value=prof_display, step=0.001)
        with c52:
            amount = st.number_input(f"Amount {i + 1} S Quote", value=level_default[1], step=1)
        sell_targets_amounts.append([target_profitability / 100, amount])


def create_order_graph(order_type, targets, min_profit, max_profit):
    # Create a figure
    fig = go.Figure()

    # Convert profit targets to percentage for x-axis and prepare data for bar chart
    x_values = [t[0] * 100 for t in targets]  # Convert to percentage
    y_values = [t[1] for t in targets]
    x_labels = [f"{x:.2f}%" for x in x_values]  # Format x labels as strings with percentage

    # Add bar plot for visualization of targets
    fig.add_trace(go.Bar(
        x=x_labels,
        y=y_values,
        width=0.01,
        name=f'{order_type.capitalize()} Targets',
        marker=dict(color='gold')
    ))

    # Convert min and max profitability to percentages for reference lines
    min_profit_percent = min_profit * 100
    max_profit_percent = max_profit * 100

    # Add vertical lines for min and max profitability
    fig.add_shape(type="line",
                  x0=min_profit_percent, y0=0, x1=min_profit_percent, y1=max(y_values, default=10),
                  line=dict(color="red", width=2),
                  name='Min Profitability')
    fig.add_shape(type="line",
                  x0=max_profit_percent, y0=0, x1=max_profit_percent, y1=max(y_values, default=10),
                  line=dict(color="red", width=2),
                  name='Max Profitability')

    # Update layouts with x-axis starting at 0
    fig.update_layout(
        title=f"{order_type.capitalize()} Order Distribution with Profitability Targets",
        xaxis=dict(
            title="Profitability (%)",
            range=[0, max(max(x_values + [min_profit_percent, max_profit_percent]) + 0.1, 1)]
            # Adjust range to include a buffer
        ),
        yaxis=dict(
            title="Order Amount"
        ),
        height=400,
        width=600
    )

    return fig


# Use the function for both buy and sell orders
buy_order_fig = create_order_graph('buy', buy_targets_amounts, min_profitability, max_profitability)
sell_order_fig = create_order_graph('sell', sell_targets_amounts, min_profitability, max_profitability)

# Display the Plotly graphs in Streamlit
st.plotly_chart(buy_order_fig, use_container_width=True)
st.plotly_chart(sell_order_fig, use_container_width=True)

# Build config dict
config = {
    "controller_name": "xemm_multiple_levels",
    "controller_type": "generic",
    "maker_connector": maker_connector,
    "maker_trading_pair": maker_trading_pair,
    "taker_connector": taker_connector,
    "taker_trading_pair": taker_trading_pair,
    "min_profitability": min_profitability,
    "max_profitability": max_profitability,
    "buy_levels_targets_amount": buy_targets_amounts,
    "sell_levels_targets_amount": sell_targets_amounts
}

# Merge into controller-specific session state
st.session_state["config_xemm_multiple_levels"].update(config)

# YAML download (kept as supplementary option)
yaml_config = yaml.dump(config, default_flow_style=False)
st.download_button(
    label="Download YAML",
    data=yaml_config,
    file_name=f'{st.session_state["config_xemm_multiple_levels"].get("id", "xemm_config").lower()}.yml',
    mime='text/yaml'
)

# Render standard save/upload component
render_save_config(
    st.session_state["config_xemm_multiple_levels"]["id"],
    st.session_state["config_xemm_multiple_levels"]
)
