import streamlit as st
from hummingbot.connector.connector_base import OrderType

from frontend.components.config_defaults import (
    STOP_LOSS, TAKE_PROFIT, TAKE_PROFIT_ORDER_TYPE, TIME_LIMIT,
    TRAILING_STOP_ACTIVATION_PRICE, TRAILING_STOP_TRAILING_DELTA,
)
from frontend.components.config_loader import get_controller_config


def get_risk_management_inputs(controller_name: str = None):
    if controller_name:
        default_config = get_controller_config(controller_name)
    else:
        default_config = st.session_state.get("default_config", {})
    sl = default_config.get("stop_loss", STOP_LOSS) * 100
    tp = default_config.get("take_profit", TAKE_PROFIT) * 100
    time_limit = default_config.get("time_limit", TIME_LIMIT) // 60
    ts_ap = default_config.get("trailing_stop", {}).get("activation_price", TRAILING_STOP_ACTIVATION_PRICE) * 100
    ts_delta = default_config.get("trailing_stop", {}).get("trailing_delta", TRAILING_STOP_TRAILING_DELTA) * 100
    take_profit_order_type = OrderType(default_config.get("take_profit_order_type", TAKE_PROFIT_ORDER_TYPE))
    order_types = [OrderType.LIMIT, OrderType.MARKET]
    order_type_index = order_types.index(take_profit_order_type)
    with st.expander("Risk Management", expanded=True):
        c1, c2, c3, c4, c5, c6 = st.columns(6)

        with c1:
            sl = st.number_input("Stop Loss (%)", min_value=0.0, max_value=100.0, value=sl, step=0.1,
                                 help="Enter the stop loss as a percentage (e.g., 2.0 for 2%).") / 100
        with c2:
            tp = st.number_input("Take Profit (%)", min_value=0.0, max_value=100.0, value=tp, step=0.1,
                                 help="Enter the take profit as a percentage (e.g., 3.0 for 3%).") / 100
        with c3:
            time_limit = st.number_input("Time Limit (minutes)", min_value=0, value=time_limit,
                                         help="Enter the time limit in minutes (e.g., 360 for 6 hours).") * 60
        with c4:
            ts_ap = st.number_input("Trailing Stop Act. Price (%)", min_value=0.0, max_value=100.0, value=ts_ap,
                                    step=0.1,
                                    help="Enter the tr  ailing stop activation price as a percentage (e.g., 1.0 for 1%).") / 100
        with c5:
            ts_delta = st.number_input("Trailing Stop Delta (%)", min_value=0.0, max_value=100.0, value=ts_delta,
                                       step=0.1,
                                       help="Enter the trailing stop delta as a percentage (e.g., 0.3 for 0.3%).") / 100
        with c6:
            take_profit_order_type = st.selectbox("Take Profit Order Type", (OrderType.LIMIT, OrderType.MARKET),
                                                  index=order_type_index,
                                                  help="Enter the order type for taking profit (LIMIT/MARKET).")
    return sl, tp, time_limit, ts_ap, ts_delta, take_profit_order_type
