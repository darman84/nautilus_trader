from decimal import Decimal
from typing import Optional

from nautilus_trader.adapters.interactive_brokers.common import IBContract
from nautilus_trader.adapters.interactive_brokers.config import InteractiveBrokersInstrumentProviderConfig
from nautilus_trader.adapters.interactive_brokers.providers import InteractiveBrokersInstrumentProvider
from nautilus_trader.config import StrategyConfig
from nautilus_trader.core.data import Data
from nautilus_trader.model.data.bar import Bar
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.objects import Price
from nautilus_trader.model.orders import MarketOrder
from nautilus_trader.trading.strategy import Strategy


class IronCondorConfig(StrategyConfig, frozen=True):
    """
    Configuration for IronCondor strategy.
    """
    instrument_id: str  # The underlying instrument ID
    bar_type: str  # The bar type for market data
    trade_size: str  # Position size for each leg
    call_width: int = 10  # Width between call strikes
    put_width: int = 10  # Width between put strikes
    otm_distance: int = 20  # Distance OTM for short options


class IronCondor(Strategy):
    """
    A basic iron condor options strategy.
    
    Opens a position when entry conditions are met:
    - Sells an OTM put and call spread
    - Buys further OTM put and call for protection
    
    Manages the position:
    - Closes at profit target or stop loss
    - Adjusts positions if needed
    """

    def __init__(self, config: IronCondorConfig) -> None:
        super().__init__(config)

        # Configuration
        self.instrument_id = InstrumentId.from_str(config.instrument_id)
        self.bar_type = config.bar_type
        self.trade_size = Decimal(config.trade_size)
        self.call_width = config.call_width
        self.put_width = config.put_width
        self.otm_distance = config.otm_distance

        self.instrument: Optional[Instrument] = None
        self.option_chain = None  # Will hold option chain data

    def on_start(self) -> None:
        """Initialize strategy and subscribe to data."""
        # Get underlying instrument
        self.instrument = self.cache.instrument(self.instrument_id)
        
        # Subscribe to bar data
        self.subscribe_bars(self.bar_type)
        
        # Configure and subscribe to IBKR option chain
        config = InteractiveBrokersInstrumentProviderConfig(
            build_options_chain=True,
            load_contracts=[
                IBContract(
                    secType="OPT",
                    symbol=self.instrument_id.symbol.value,
                    exchange="SMART",
                    build_options_chain=True,
                ),
            ],
        )
        self.ib_provider = InteractiveBrokersInstrumentProvider(
            client=self.client,
            logger=self.logger,
            config=config,
        )
        self.option_chain = self.ib_provider.option_chain(self.instrument_id)

    def on_bar(self, bar: Bar) -> None:
        """
        Process bar updates and check for entry/exit conditions.
        """
        if not self.option_chain:
            return  # Wait for option chain data
            
        if self.portfolio.is_flat(self.instrument_id):
            self.check_entry_signals(bar)
        else:
            self.check_exit_signals(bar)

    def check_entry_signals(self, bar: Bar) -> None:
        """Check for iron condor entry opportunities."""
        # Get current price
        current_price = bar.close
        
        # Calculate strike prices
        short_put_strike = self.calculate_strike(current_price - self.otm_distance)
        long_put_strike = short_put_strike - self.put_width
        short_call_strike = self.calculate_strike(current_price + self.otm_distance)
        long_call_strike = short_call_strike + self.call_width
        
        # Place orders for all four legs
        self.sell_put_spread(short_put_strike, long_put_strike)
        self.sell_call_spread(short_call_strike, long_call_strike)

    def sell_put_spread(self, short_strike: Decimal, long_strike: Decimal) -> None:
        """Place orders for put spread leg."""
        # Sell put at higher strike
        short_put = self.order_factory.market(
            instrument_id=self.get_put_option_id(short_strike),
            order_side=OrderSide.SELL,
            quantity=self.trade_size,
        )
        self.submit_order(short_put)
        
        # Buy put at lower strike
        long_put = self.order_factory.market(
            instrument_id=self.get_put_option_id(long_strike),
            order_side=OrderSide.BUY,
            quantity=self.trade_size,
        )
        self.submit_order(long_put)

    def sell_call_spread(self, short_strike: Decimal, long_strike: Decimal) -> None:
        """Place orders for call spread leg."""
        # Sell call at lower strike
        short_call = self.order_factory.market(
            instrument_id=self.get_call_option_id(short_strike),
            order_side=OrderSide.SELL,
            quantity=self.trade_size,
        )
        self.submit_order(short_call)
        
        # Buy call at higher strike
        long_call = self.order_factory.market(
            instrument_id=self.get_call_option_id(long_strike),
            order_side=OrderSide.BUY,
            quantity=self.trade_size,
        )
        self.submit_order(long_call)

    def check_exit_signals(self, bar: Bar) -> None:
        """Check for exit conditions."""
        if not self.portfolio.is_flat(self.instrument_id):
            position = self.portfolio.get_position(self.instrument_id)
            
            # Calculate total P&L
            unrealized_pnl = position.unrealized_pnl
            
            # Exit at 50% max profit or 200% max loss
            if unrealized_pnl >= self.max_profit * Decimal("0.5"):
                self.close_all_positions()
            elif unrealized_pnl <= -self.max_profit * Decimal("2.0"):
                self.close_all_positions()

    def on_stop(self) -> None:
        """Clean up on strategy stop."""
        self.cancel_all_orders()
        self.close_all_positions()
        self.unsubscribe_bars(self.bar_type)

    def on_reset(self) -> None:
        """Reset strategy state."""
        self.option_chain = None

    # Helper methods
    def calculate_strike(self, price: Decimal) -> Decimal:
        """Calculate nearest valid strike price."""
        # Round to nearest IBKR strike interval
        strike_interval = Decimal("0.5")  # Standard IBKR strike intervals
        return round(price / strike_interval) * strike_interval

    def get_call_option_id(self, strike: Decimal) -> InstrumentId:
        """Get instrument ID for call option at given strike."""
        # IBKR option symbol format
        symbol = self.instrument_id.symbol.value
        expiry = self._get_next_monthly_expiry()
        return InstrumentId.from_str(f"{symbol}_{expiry}_C_{strike}_SMART")

    def get_put_option_id(self, strike: Decimal) -> InstrumentId:
        """Get instrument ID for put option at given strike."""
        # IBKR option symbol format
        symbol = self.instrument_id.symbol.value
        expiry = self._get_next_monthly_expiry()
        return InstrumentId.from_str(f"{symbol}_{expiry}_P_{strike}_SMART")

    def _get_next_monthly_expiry(self) -> str:
        """Get the next monthly expiration date."""
        # Get the next monthly expiry from the option chain
        if not self.option_chain:
            return ""
        
        # Sort expiries and get next monthly
        expiries = sorted(self.option_chain.expiries)
        for expiry in expiries:
            if expiry > self.clock.utc_now():
                return expiry.strftime("%Y%m%d")
        return ""
