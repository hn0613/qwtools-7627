import streamlit as st

from frontend.components.config_defaults import (
    CANDLES_CONNECTOR, CANDLES_TRADING_PAIR, CONNECTOR_NAME, COOLDOWN_TIME,
    INTERVAL, LEVERAGE, MAX_EXECUTORS_PER_SIDE, POSITION_MODE, TOTAL_AMOUNT_QUOTE,
    TRADING_PAIR,
)
from frontend.components.config_loader import get_controller_config


def get_directional_trading_general_inputs(controller_name: str = None):
    with st.expander("General Settings", expanded=True):
        c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
        if controller_name:
            default_config = get_controller_config(controller_name)
        else:
            default_config = st.session_state.get("default_config", {})
        connector_name = default_config.get("connector_name", CONNECTOR_NAME)
        trading_pair = default_config.get("trading_pair", TRADING_PAIR)
        leverage = default_config.get("leverage", LEVERAGE)
        total_amount_quote = default_config.get("total_amount_quote", TOTAL_AMOUNT_QUOTE)
        max_executors_per_side = default_config.get("max_executors_per_side", MAX_EXECUTORS_PER_SIDE)
        cooldown_time = default_config.get("cooldown_time", COOLDOWN_TIME) / 60
        position_mode = 0 if default_config.get("position_mode", POSITION_MODE) == "HEDGE" else 1
        candles_connector_name = default_config.get("candles_connector_name", CANDLES_CONNECTOR)
        candles_trading_pair = default_config.get("candles_trading_pair", CANDLES_TRADING_PAIR)
        interval = default_config.get("interval", INTERVAL)
        intervals = ["1m", "3m", "5m", "15m", "1h", "4h", "1d", "1s"]
        interval_index = intervals.index(interval)

        with c1:
            connector_name = st.text_input("Connector", value=connector_name,
                                           help="Enter the name of the exchange to trade on (e.g., binance_perpetual).")
            candles_connector_name = st.text_input("Candles Connector", value=candles_connector_name,
                                                   help="Enter the name of the exchange to get candles from"
                                                        " (e.g., binance_perpetual).")
        with c2:
            trading_pair = st.text_input("Trading Pair", value=trading_pair,
                                         help="Enter the trading pair to trade on (e.g., WLD-USDT).")
            candles_trading_pair = st.text_input("Candles Trading Pair", value=candles_trading_pair,
                                                 help="Enter the trading pair to get candles for (e.g., WLD-USDT).")
        with c3:
            leverage = st.number_input("Leverage", value=leverage,
                                       min_value=1,
                                       help="Set the leverage to use for trading (e.g., 20 for 20x leverage)."
                                            "Set it to 1 for spot trading. Value must be greater than 0.")
            interval = st.selectbox("Candles Interval", ("1m", "3m", "5m", "15m", "1h", "4h", "1d"),
                                    index=interval_index,
                                    help="Enter the interval for candles (e.g., 1m).")
        with c4:
            total_amount_quote = st.number_input("Total amount of quote", value=total_amount_quote,
                                                 help="Enter the total amount in quote asset to use for trading (e.g., 1000).")
        with c5:
            max_executors_per_side = st.number_input("Max Executors Per Side", value=max_executors_per_side,
                                                     help="Enter the maximum number of executors per side (e.g., 5).")
        with c6:
            cooldown_time = st.number_input("Cooldown Time (minutes)", value=cooldown_time,
                                            help="Time between accepting a new signal in minutes (e.g., 60).") * 60
        with c7:
            position_mode = st.selectbox("Position Mode", ("HEDGE", "ONEWAY"), index=position_mode,
                                         help="Enter the position mode (HEDGE/ONEWAY).")
    return connector_name, trading_pair, leverage, total_amount_quote, max_executors_per_side, cooldown_time, \
        position_mode, candles_connector_name, candles_trading_pair, interval
