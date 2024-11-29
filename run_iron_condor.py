from decimal import Decimal

from nautilus_trader.adapters.interactive_brokers.config import DockerizedIBGatewayConfig
from nautilus_trader.adapters.interactive_brokers.config import InteractiveBrokersDataClientConfig
from nautilus_trader.adapters.interactive_brokers.config import InteractiveBrokersExecClientConfig
from nautilus_trader.adapters.interactive_brokers.factories import InteractiveBrokersLiveDataClientFactory
from nautilus_trader.adapters.interactive_brokers.factories import InteractiveBrokersLiveExecClientFactory
from nautilus_trader.config import LiveDataEngineConfig
from nautilus_trader.config import LoggingConfig
from nautilus_trader.config import TradingNodeConfig
from nautilus_trader.core.message import Event
from nautilus_trader.indicators.macd import MovingAverageConvergenceDivergence
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.enums import PositionSide
from nautilus_trader.model.enums import PriceType
from nautilus_trader.model.events import PositionOpened
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.objects import Quantity
from nautilus_trader.model.position import Position
from nautilus_trader.model.tick import QuoteTick
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.trading.strategy import StrategyConfig
from nautilus_trader.live.node import TradingNode


class MACDConfig(StrategyConfig):
    instrument_id: str = "SPY.IB"  # SPY ETF on Interactive Brokers
    fast_period: int = 12
    slow_period: int = 26
    trade_size: int = 100  # Number of shares
    entry_threshold: float = 0.00010


class MACDStrategy(Strategy):
    def __init__(self, config: MACDConfig):
        super().__init__(config=config)
        # Our "trading signal"
        self.macd = MovingAverageConvergenceDivergence(
            fast_period=config.fast_period, slow_period=config.slow_period, price_type=PriceType.MID
        )
        # We copy some config values onto the class to make them easier to reference later on
        self.entry_threshold = config.entry_threshold
        self.instrument_id = config.instrument_id
        self.trade_size = Quantity.from_int(config.trade_size)
        self.entry_threshold = config.entry_threshold

        # Convenience
        self.position: Position | None = None

    def on_start(self):
        self.subscribe_quote_ticks(instrument_id=self.instrument_id)

    def on_stop(self):
        self.close_all_positions(self.instrument_id)
        self.unsubscribe_quote_ticks(instrument_id=self.instrument_id)

    def on_quote_tick(self, tick: QuoteTick):
        # You can register indicators to receive quote tick updates automatically,
        # here we manually update the indicator to demonstrate the flexibility available.
        self.macd.handle_quote_tick(tick)

        if not self.macd.initialized:
            return  # Wait for indicator to warm up

        # self._log.info(f"{self.macd.value=}:%5d")
        self.check_for_entry()
        self.check_for_exit()

    def on_event(self, event: Event):
        if isinstance(event, PositionOpened):
            self.position = self.cache.position(event.position_id)

    def check_for_entry(self):
        # If MACD line is above our entry threshold, we should be LONG
        if self.macd.value > self.entry_threshold:
            if self.position and self.position.side == PositionSide.LONG:
                return  # Already LONG

            order = self.order_factory.market(
                instrument_id=self.instrument_id,
                order_side=OrderSide.BUY,
                quantity=self.trade_size,
            )
            self.submit_order(order)
        # If MACD line is below our entry threshold, we should be SHORT
        elif self.macd.value < -self.entry_threshold:
            if self.position and self.position.side == PositionSide.SHORT:
                return  # Already SHORT

            order = self.order_factory.market(
                instrument_id=self.instrument_id,
                order_side=OrderSide.SELL,
                quantity=self.trade_size,
            )
            self.submit_order(order)

    def check_for_exit(self):
        # If MACD line is above zero then exit if we are SHORT
        if self.macd.value >= 0.0:
            if self.position and self.position.side == PositionSide.SHORT:
                self.close_position(self.position)
        # If MACD line is below zero then exit if we are LONG
        else:
            if self.position and self.position.side == PositionSide.LONG:
                self.close_position(self.position)

    def on_dispose(self):
        pass  # Do nothing else


if __name__ == "__main__":
    # Configure IB Gateway (paper trading)
    gateway_config = DockerizedIBGatewayConfig(
        username="your_username",  # Your IB username
        password="your_password",  # Your IB password
        trading_mode="paper",      # Use paper trading
    )

    # Configure the data client
    data_client_config = InteractiveBrokersDataClientConfig(
        ibg_port=4002,
        handle_revised_bars=False,
        use_regular_trading_hours=True,
        dockerized_gateway=gateway_config,
    )

    # Configure the execution client
    exec_client_config = InteractiveBrokersExecClientConfig(
        ibg_port=4002,
        account_id="your_account_id",  # Your IB account ID
        dockerized_gateway=gateway_config,
    )

    # Configure the trading node
    config = TradingNodeConfig(
        trader_id="MACD-001",
        logging=LoggingConfig(log_level="INFO"),
        data_clients={"IB": data_client_config},
        exec_clients={"IB": exec_client_config},
        data_engine=LiveDataEngineConfig(
            validate_data_sequence=True,
        ),
    )

    # Create and configure the strategy
    strategy_config = MACDConfig()

    # Initialize the trading node
    node = TradingNode(config=config)

    # Add the client factories
    node.add_data_client_factory("IB", InteractiveBrokersLiveDataClientFactory)
    node.add_exec_client_factory("IB", InteractiveBrokersLiveExecClientFactory)

    # Add the strategy
    node.add_strategy(MACDStrategy(config=strategy_config))

    # Build and run
    node.build()

    try:
        node.run()
    finally:
        node.dispose()
