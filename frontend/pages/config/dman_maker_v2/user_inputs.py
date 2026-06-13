import streamlit as st

from frontend.components.config_loader import get_controller_config
from frontend.components.executors_distribution import get_executors_distribution_inputs
from frontend.components.market_making_general_inputs import get_market_making_general_inputs


def user_inputs(controller_name: str = "dman_maker_v2"):
    default_config = get_controller_config(controller_name)
    connector_name, trading_pair, leverage, total_amount_quote, position_mode, cooldown_time,\
        executor_refresh_time, _, _, _ = get_market_making_general_inputs(controller_name=controller_name)
    buy_spread_distributions, sell_spread_distributions, buy_order_amounts_pct, \
        sell_order_amounts_pct = get_executors_distribution_inputs(controller_name=controller_name)
    with st.expander("Custom D-Man Maker V2 Settings"):
        c1, c2 = st.columns(2)
        with c1:
            top_executor_refresh_time = st.number_input(
                "Top Refresh Time (minutes)",
                value=default_config.get("top_executor_refresh_time", 3600) / 60
            ) * 60
        with c2:
            activation_bounds_list = default_config.get("executor_activation_bounds", [0.001])
            activation_bounds_default = activation_bounds_list[0] if activation_bounds_list else 0.001
            executor_activation_bounds = st.number_input(
                "Activation Bounds (%)",
                value=activation_bounds_default * 100
            ) / 100
    # Create the config
    config = {
        "controller_name": "dman_maker_v2",
        "controller_type": "market_making",
        "manual_kill_switch": False,
        "candles_config": [],
        "connector_name": connector_name,
        "trading_pair": trading_pair,
        "total_amount_quote": total_amount_quote,
        "buy_spreads": buy_spread_distributions,
        "sell_spreads": sell_spread_distributions,
        "buy_amounts_pct": buy_order_amounts_pct,
        "sell_amounts_pct": sell_order_amounts_pct,
        "executor_refresh_time": executor_refresh_time,
        "cooldown_time": cooldown_time,
        "leverage": leverage,
        "position_mode": position_mode,
        "top_executor_refresh_time": top_executor_refresh_time,
        "executor_activation_bounds": [executor_activation_bounds]
    }

    return config
