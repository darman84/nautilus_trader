from decimal import Decimal
from nautilus_trader.adapters.interactive_brokers.config import DockerizedIBGatewayConfig
from nautilus_trader.adapters.interactive_brokers.config import InteractiveBrokersDataClientConfig
from nautilus_trader.adapters.interactive_brokers.config import InteractiveBrokersExecClientConfig
from nautilus_trader.adapters.interactive_brokers.factories import InteractiveBrokersLiveDataClientFactory
from nautilus_trader.adapters.interactive_brokers.factories import InteractiveBrokersLiveExecClientFactory
from nautilus_trader.config import LiveDataEngineConfig
from nautilus_trader.config import LoggingConfig
from nautilus_trader.config import TradingNodeConfig
from nautilus_trader.live.node import TradingNode
from strategies.iron_condor import IronCondor, IronCondorConfig

# Configure IB Gateway (paper trading)
gateway_config = DockerizedIBGatewayConfig(
    username="your_username",  # Replace with your IB username
    password="your_password",  # Replace with your IB password
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
    account_id="your_account_id",  # Replace with your IB account ID
    dockerized_gateway=gateway_config,
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
    instrument_id="SPX.CBOE",
    bar_type="SPX.CBOE-1-MINUTE-LAST-INTERNAL",
    trade_size="1",
    call_width=10,
    put_width=10,
    otm_distance=20,
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
