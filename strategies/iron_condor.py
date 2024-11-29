from decimal import Decimal
from typing import Optional

from nautilus_trader.config import ConfigurationError
from nautilus_trader.core.data import Data
from nautilus_trader.core.message import Event
from nautilus_trader.model.data.bar import Bar
from nautilus_trader.model.data.bar import BarType
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.orderbook import OrderBook
from nautilus_trader.model.orders import MarketOrder
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.config import StrategyConfig

class IronCondorConfig(StrategyConfig):
    instrument_id: str
    bar_type: str
    trade_size: str
    call_width: int
    put_width: int
    otm_distance: int

class IronCondor(Strategy):
    def __init__(self, config: IronCondorConfig):
        super().__init__(config)
        
        # Configuration
        self.instrument_id = InstrumentId.from_str(config.instrument_id)
        self.bar_type = BarType.from_str(config.bar_type)
        self.trade_size = Decimal(config.trade_size)
        self.call_width = config.call_width
        self.put_width = config.put_width
        self.otm_distance = config.otm_distance
        
        # Internal state
        self.instrument: Optional[Instrument] = None
        self.position_open = False
        
    def on_start(self):
        """Called when the strategy starts."""
        # Register the data
        self.subscribe_bars(self.bar_type)
        
        # Get the instrument
        self.instrument = self.cache.instrument(self.instrument_id)
        if self.instrument is None:
            raise ConfigurationError(f"Instrument {self.instrument_id} not found in cache")
            
    def on_bar(self, bar: Bar):
        """
        Called when a new bar is received.
        Implements the Iron Condor entry logic.
        """
        if self.position_open:
            self._check_exit_conditions(bar)
            return
            
        # Entry logic
        if self._entry_conditions_met(bar):
            self._enter_iron_condor(bar)
            
    def _entry_conditions_met(self, bar: Bar) -> bool:
        """
        Check if conditions are right to enter an Iron Condor.
        Implement your custom entry conditions here.
        """
        # Example condition: Enter when price is within certain range
        # You should implement more sophisticated conditions
        return True  # Simplified for example
        
    def _enter_iron_condor(self, bar: Bar):
        """
        Execute the Iron Condor entry orders.
        """
        current_price = bar.close
        
        # Calculate strike prices
        short_call_strike = current_price + self.otm_distance
        long_call_strike = short_call_strike + self.call_width
        short_put_strike = current_price - self.otm_distance
        long_put_strike = short_put_strike - self.put_width
        
        # Submit the orders
        # Sell call spread
        self.submit_order(
            MarketOrder(
                instrument_id=self.instrument_id,
                order_side=OrderSide.SELL,
                quantity=self.trade_size,
            )
        )
        
        # Buy protective call
        self.submit_order(
            MarketOrder(
                instrument_id=self.instrument_id,
                order_side=OrderSide.BUY,
                quantity=self.trade_size,
            )
        )
        
        # Sell put spread
        self.submit_order(
            MarketOrder(
                instrument_id=self.instrument_id,
                order_side=OrderSide.SELL,
                quantity=self.trade_size,
            )
        )
        
        # Buy protective put
        self.submit_order(
            MarketOrder(
                instrument_id=self.instrument_id,
                order_side=OrderSide.BUY,
                quantity=self.trade_size,
            )
        )
        
        self.position_open = True
        
    def _check_exit_conditions(self, bar: Bar):
        """
        Check if we should exit the Iron Condor position.
        Implement your custom exit conditions here.
        """
        # Example exit conditions:
        # - Take profit at 50% of max potential profit
        # - Stop loss at 200% of max potential profit
        pass
