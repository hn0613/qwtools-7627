"""
Centralized default configuration values for all strategy config pages.

This module is the single source of truth for default values used across
shared components and strategy-specific user_inputs. Replacing the scattered
hardcoded defaults that previously appeared in 10+ files.

Usage:
    from frontend.components.config_defaults import CONNECTOR_NAME, STOP_LOSS
    value = config.get("connector_name", CONNECTOR_NAME)
"""

# ── Connection / General ─────────────────────────────────────────────
CONNECTOR_NAME = "kucoin"
TRADING_PAIR = "WLD-USDT"
LEVERAGE = 20
TOTAL_AMOUNT_QUOTE = 1000
POSITION_MODE = "HEDGE"
COOLDOWN_TIME = 60 * 60              # seconds (displayed as minutes)
EXECUTOR_REFRESH_TIME = 60 * 60      # seconds (displayed as minutes)
MAX_EXECUTORS_PER_SIDE = 5

# ── Candles ──────────────────────────────────────────────────────────
CANDLES_CONNECTOR = "kucoin"
CANDLES_TRADING_PAIR = "WLD-USDT"
INTERVAL = "3m"

# ── Risk Management ──────────────────────────────────────────────────
STOP_LOSS = 0.05                     # 5%
TAKE_PROFIT = 0.02                   # 2%
TIME_LIMIT = 60 * 12 * 60            # 12 hours in seconds
TRAILING_STOP_ACTIVATION_PRICE = 0.018   # 1.8%
TRAILING_STOP_TRAILING_DELTA = 0.002     # 0.2%
TAKE_PROFIT_ORDER_TYPE = 2           # OrderType.MARKET value

# ── Executor Distribution ────────────────────────────────────────────
BUY_SPREADS = [0.01, 0.02]
SELL_SPREADS = [0.01, 0.02]
BUY_AMOUNTS_PCT = [0.2, 0.8]
SELL_AMOUNTS_PCT = [0.2, 0.8]
# When use_custom_spread_units=True, spreads are stored as integers (1, 2)
# and divided by 100 at read time. These are the raw integer defaults:
CUSTOM_SPREAD_BUY_DEFAULTS = [1, 2]
CUSTOM_SPREAD_SELL_DEFAULTS = [1, 2]

# ── DCA Distribution ─────────────────────────────────────────────────
DCA_SPREADS = [0.01, 0.02, 0.03]
DCA_AMOUNTS = [0.2, 0.5, 0.3]
# DCA has its own risk management defaults (different from general risk mgmt)
DCA_STOP_LOSS = 0.02                 # 2%
DCA_TAKE_PROFIT = 0.01               # 1%
DCA_TIME_LIMIT = 60 * 6 * 60         # 6 hours in seconds

# ── Bollinger Bands ──────────────────────────────────────────────────
BB_LENGTH = 100
BB_STD = 2.0
BB_LONG_THRESHOLD = 0.0
BB_SHORT_THRESHOLD = 1.0

# ── MACD ─────────────────────────────────────────────────────────────
MACD_FAST = 21
MACD_SLOW = 42
MACD_SIGNAL = 9

# ── SuperTrend ───────────────────────────────────────────────────────
SUPERTREND_LENGTH = 20
SUPERTREND_MULTIPLIER = 3.0
SUPERTREND_PERCENTAGE_THRESHOLD = 0.5

# ── NATR ─────────────────────────────────────────────────────────────
NATR_LENGTH = 14

# ── PMM Rebalance ────────────────────────────────────────────────────
POSITION_REBALANCE_THRESHOLD_PCT = 0.05   # 5%
SKIP_REBALANCE = False
