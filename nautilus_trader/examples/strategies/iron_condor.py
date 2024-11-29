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
        """
        Initialize a new instance of the IronCondor class.

        Parameters
        ----------
        config : IronCondorConfig
            The configuration for the strategy.
        """
        super().__init__(config)

        # Configuration
        self.instrument_id = InstrumentId.from_str(config.instrument_id)
        self.bar_type = config.bar_type
        self.trade_size = Decimal(config.trade_size)
        self.call_width = config.call_width
        self.put_width = config.put_width
        self.otm_distance = config.otm_distance

        # Initialize state
        self.instrument: Optional[Instrument] = None
        self.option_chain = None  # Will hold option chain data
        self.is_position_opened = False
        self.entry_price = Decimal("0")
        self.max_profit = Decimal("0")

    def on_start(self) -> None:
        """
        Actions to be performed on strategy start.

        - Initializes instruments
        - Subscribes to market data
        - Sets up option chain subscriptions
        """
        # Get underlying instrument
        self.instrument = self.cache.instrument(self.instrument_id)
        
        # Subscribe to bar data
        self.subscribe_bars(self.bar_type)
        
        # Configure and subscribe to IBKR option chain
        config = InteractiveBrokersInstrumentProviderConfig(
            build_options_chain=True,
            min_expiry_days=0,
            max_expiry_days=60,  # Look ahead 60 days for options
            load_contracts=[
                IBContract(
                    secType="IND",  # For index options
                    symbol=self.instrument_id.symbol.value,
                    exchange="SMART",
                    currency="USD",
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
        """
        Check for iron condor entry opportunities.

        Parameters
        ----------
        bar : Bar
            The update bar for analysis.
        """
        if self.is_position_opened:
            return  # Already in a position
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
        """
        Check for exit conditions.

        Parameters
        ----------
        bar : Bar
            The update bar for analysis.
        """
        if not self.is_position_opened:
            return  # No position to exit

        if not self.portfolio.is_flat(self.instrument_id):
            position = self.portfolio.get_position(self.instrument_id)
            
            # Calculate total P&L
            unrealized_pnl = position.unrealized_pnl
            
            # Exit conditions
            exit_position = False
            
            # Profit target (50% of max profit)
            if unrealized_pnl >= self.max_profit * Decimal("0.5"):
                self.log.info(f"Profit target reached: {unrealized_pnl}")
                exit_position = True
                
            # Stop loss (200% of max profit)
            elif unrealized_pnl <= -self.max_profit * Decimal("2.0"):
                self.log.warning(f"Stop loss hit: {unrealized_pnl}")
                exit_position = True
                
            if exit_position:
                self.close_all_positions()
                self.is_position_opened = False

    def on_stop(self) -> None:
        """Clean up on strategy stop."""
        self.cancel_all_orders()
        self.close_all_positions()
        self.unsubscribe_bars(self.bar_type)

    def on_reset(self) -> None:
        """
        Reset the strategy state.
        """
        self.option_chain = None
        self.is_position_opened = False
        self.entry_price = Decimal("0")
        self.max_profit = Decimal("0")

    # Helper methods
    def calculate_strike(self, price: Decimal) -> Decimal:
        """Calculate nearest valid strike price."""
        # Round to nearest IBKR strike interval
        strike_interval = Decimal("0.5")  # Standard IBKR strike intervals
        return round(price / strike_interval) * strike_interval

    def get_call_option_id(self, strike: Decimal) -> InstrumentId:
        """
        Get instrument ID for call option at given strike using IBKR format.
        
        The format follows IBKR's standard option symbol format:
        {symbol}{expiry}{C|P}{strike}.{exchange}
        """
        symbol = self.instrument_id.symbol.value
        expiry = self._get_next_monthly_expiry()
        strike_str = f"{float(strike):08.3f}"  # Format strike price with padding
        return InstrumentId.from_str(f"{symbol}{expiry}C{strike_str}.SMART")

    def get_put_option_id(self, strike: Decimal) -> InstrumentId:
        """
        Get instrument ID for put option at given strike using IBKR format.
        
        The format follows IBKR's standard option symbol format:
        {symbol}{expiry}{C|P}{strike}.{exchange}
        """
        symbol = self.instrument_id.symbol.value
        expiry = self._get_next_monthly_expiry()
        strike_str = f"{float(strike):08.3f}"  # Format strike price with padding
        return InstrumentId.from_str(f"{symbol}{expiry}P{strike_str}.SMART")

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
