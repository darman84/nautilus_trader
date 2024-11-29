import asyncio
from decimal import Decimal
from nautilus_trader.model.identifiers import Symbol, Venue
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import LiveDataEngineConfig
from nautilus_trader.config import LoggingConfig
from nautilus_trader.config import TradingNodeConfig
from nautilus_trader.examples.strategies.iron_condor import IronCondor
from nautilus_trader.examples.strategies.iron_condor import IronCondorConfig
from nautilus_trader.live.node import TradingNode

# Configure the data client
data_client_config = InteractiveBrokersDataClientConfig(
    host="127.0.0.1",  # Local TWS/Gateway
    port=7497,         # Default TWS port
    handle_revised_bars=False,
    use_regular_trading_hours=True,
)

# Configure the execution client
exec_client_config = InteractiveBrokersExecClientConfig(
    host="127.0.0.1",  # Local TWS/Gateway
    port=7497,         # Default TWS port
    account_id="your_account_id",  # Replace with your IB paper account ID
)

# Configure the trading node
config = TradingNodeConfig(
    trader_id="IRON-CONDOR-001",
    logging=LoggingConfig(log_level="INFO"),
    data_clients={"IB": data_client_config},
    exec_clients={"IB": exec_client_config},
    data_engine=LiveDataEngineConfig(
        validate_data_sequence=True,
    ),
)

# Create and configure the strategy
strategy_config = IronCondorConfig(
    instrument_id="SPX.CBOE",           # S&P 500 index
    bar_type="SPX.CBOE-1-MINUTE-LAST-INTERNAL",
    trade_size="1",                     # Number of contracts per leg
    call_width=10,                      # Width between call strikes
    put_width=10,                       # Width between put strikes
    otm_distance=20,                    # Distance OTM for short options
)

# Initialize the trading node
node = TradingNode(config=config)

# Add the client factories
node.add_data_client_factory("IB", InteractiveBrokersLiveDataClientFactory)
node.add_exec_client_factory("IB", InteractiveBrokersLiveExecClientFactory)

# Add the strategy
node.add_strategy(IronCondor(config=strategy_config))

# Build and run
node.build()

if __name__ == "__main__":
    try:
        node.run()
    finally:
        node.dispose()
