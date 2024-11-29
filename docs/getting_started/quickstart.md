# Quickstart

This quickstart guide demonstrates how to implement and run an Iron Condor options trading strategy using NautilusTrader with Interactive Brokers integration.

## Installation

First, install NautilusTrader with Interactive Brokers support:

```bash
pip install -U "nautilus_trader[ib]"
```

## Strategy Implementation

The Iron Condor strategy is a neutral options strategy that profits from low volatility. It consists of:
- A short call spread (bear call spread)
- A short put spread (bull put spread)

Here's how to run the strategy:

```python
from decimal import Decimal
from nautilus_trader.adapters.interactive_brokers.config import DockerizedIBGatewayConfig
from nautilus_trader.adapters.interactive_brokers.config import InteractiveBrokersDataClientConfig
from nautilus_trader.adapters.interactive_brokers.config import InteractiveBrokersExecClientConfig
from nautilus_trader.adapters.interactive_brokers.factories import InteractiveBrokersLiveDataClientFactory
from nautilus_trader.adapters.interactive_brokers.factories import InteractiveBrokersLiveExecClientFactory
from nautilus_trader.config import LiveDataEngineConfig
from nautilus_trader.config import LoggingConfig
from nautilus_trader.config import TradingNodeConfig
from nautilus_trader.examples.strategies.iron_condor import IronCondor
from nautilus_trader.examples.strategies.iron_condor import IronCondorConfig
from nautilus_trader.live.node import TradingNode

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
```

## Strategy Details

The Iron Condor strategy:

1. Monitors the underlying instrument (SPX in this example)
2. When entry conditions are met:
   - Sells an OTM put spread (short put + long put)
   - Sells an OTM call spread (short call + long call)
3. Manages the position:
   - Takes profit at 50% of max potential profit
   - Stops out at 200% of max potential profit
   - Adjusts positions if needed

## Configuration Parameters

- `instrument_id`: The underlying instrument to trade
- `bar_type`: The type of price bars to use
- `trade_size`: Number of contracts per leg
- `call_width`: Strike price difference for call spread
- `put_width`: Strike price difference for put spread
- `otm_distance`: How far OTM to place the short options

## Next Steps

1. Review the [Interactive Brokers Integration](/integrations/ib.md) guide for detailed setup instructions
2. Explore the [Strategy Development](/concepts/strategies.md) guide to understand strategy implementation
3. Learn about [Risk Management](/concepts/risk.md) to protect your trading capital

Remember to:
- Always test with paper trading first
- Start with small position sizes
- Monitor your positions regularly
- Understand the risks of options trading
