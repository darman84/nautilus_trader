#!/usr/bin/env python3
# -------------------------------------------------------------------------------------------------
#  Copyright (C) 2015-2024 Nautech Systems Pty Ltd. All rights reserved.
#  https://nautechsystems.io
#
#  Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
#  You may not use this file except in compliance with the License.
#  You may obtain a copy of the License at https://www.gnu.org/licenses/lgpl-3.0.en.html
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# -------------------------------------------------------------------------------------------------

import asyncio
import datetime
from decimal import Decimal
import os

import pandas as pd

from nautilus_trader.adapters.interactive_brokers.common import IBContract
from nautilus_trader.adapters.interactive_brokers.config import DockerizedIBGatewayConfig
from nautilus_trader.adapters.interactive_brokers.gateway import DockerizedIBGateway
from nautilus_trader.adapters.interactive_brokers.historic import HistoricInteractiveBrokersClient
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.engine import BacktestEngineConfig
from nautilus_trader.backtest.models import FillModel
from nautilus_trader.backtest.models import LatencyModel
from nautilus_trader.config import DataEngineConfig
from nautilus_trader.config import LoggingConfig
from nautilus_trader.config import LoggingConfig
from nautilus_trader.config import RiskEngineConfig
from nautilus_trader.examples.strategies.ema_cross import EMACross
from nautilus_trader.examples.strategies.ema_cross import EMACrossConfig
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.enums import AccountType
from nautilus_trader.model.enums import OmsType
from nautilus_trader.model.identifiers import InstrumentId, Venue
from nautilus_trader.model.objects import Money
from nautilus_trader.model.identifiers import InstrumentId, StrategyId
from nautilus_trader.model.identifiers import TraderId
from nautilus_trader.persistence.catalog import ParquetDataCatalog


async def download_data(host: str | None = None, port: int | None = None) -> None:
    """Download historical data from Interactive Brokers."""
    # Define the contract we want data for
    contract = IBContract(
        secType="STK",
        symbol="AAPL",
        exchange="SMART",
        primaryExchange="NASDAQ",
    )
    instrument_id_str = "AAPL.NASDAQ"

    # Connect to IB
    client = HistoricInteractiveBrokersClient(host=host, port=port, client_id=5)
    await client.connect()
    await asyncio.sleep(2)  # Give time for connection

    # Request data
    instruments = await client.request_instruments(
        contracts=[contract],
        instrument_ids=[instrument_id_str],
    )

    bars = await client.request_bars(
        bar_specifications=["1-HOUR-LAST"],
        start_date_time=datetime.datetime(2023, 11, 6, 9, 30),
        end_date_time=datetime.datetime(2023, 11, 6, 16, 30),
        tz_name="America/New_York",
        contracts=[contract],
        instrument_ids=[instrument_id],
    )

    # Save data to catalog
    catalog = ParquetDataCatalog("./catalog")
    catalog.write_data(instruments)
    catalog.write_data(bars)


# Define venue
NASDAQ = Venue("NASDAQ")

def run_backtest() -> None:
    """Run backtest using downloaded data."""
    # Configure backtest engine
    config = BacktestEngineConfig(
        trader_id=TraderId("BACKTESTER-001"),
        logging=LoggingConfig(log_level="INFO"),
        risk_engine=RiskEngineConfig(bypass=True),  # No risk checks for backtest
        data_engine=DataEngineConfig(
            validate_data_sequence=True,  # Will make sure DataEngine discards any Bars received out of sequence
        ),
    )

    # Initialize engine
    engine = BacktestEngine(config=config)

    # Load data from catalog
    catalog = ParquetDataCatalog("./catalog")
    instruments = catalog.instruments()
    bars = catalog.bars()

    # Add venue first
    engine.add_venue(
        venue=NASDAQ,
        oms_type=OmsType.NETTING,
        account_type=AccountType.CASH,
        base_currency=USD,
        starting_balances=[Money(1_000_000, USD)],
    )

    # Add data to engine
    for instrument in instruments:
        engine.add_instrument(instrument)
    engine.add_data(bars)

    # Configure strategy
    strategy_config = EMACrossConfig(
        InstrumentId.from_str("AAPL.NASDAQ"),
        bar_type="1-HOUR-LAST",
        trade_size=100,
        fast_ema_period=10,
        slow_ema_period=20,
    )

    # Add strategy to engine
    engine.add_strategy(EMACross(config=strategy_config))

    # Run backtest
    engine.run()

    # Print performance metrics
    portfolio = engine.portfolio
    performance = engine.portfolio.performance

    print("\nBacktest Results:")
    print("-" * 50)
    print(f"Initial Capital: ${portfolio.starting_capital:,.2f}")
    print(f"Final Capital: ${portfolio.capital:,.2f}")
    print(f"Net PnL: ${portfolio.net_pnl:,.2f}")
    print(f"Return: {portfolio.return_pct:.2f}%")
    print(f"Max Drawdown: {performance.drawdown_pct_max:.2f}%")
    print(f"Sharpe Ratio: {performance.sharpe_ratio:.2f}")


if __name__ == "__main__":
    print("Starting data download...")
    # You can use either direct connection or dockerized gateway
    # For direct connection to TWS/Gateway:
    asyncio.run(download_data(host="127.0.0.1", port=7497))
    
    # For dockerized gateway (uncomment these lines and comment out the above):
    # gateway_config = DockerizedIBGatewayConfig(
    #     username=os.environ["TWS_USERNAME"],
    #     password=os.environ["TWS_PASSWORD"],
    #     trading_mode="paper",
    # )
    # gateway = DockerizedIBGateway(config=gateway_config)
    # gateway.start()
    # asyncio.run(download_data(host=gateway.host, port=gateway.port))
    # gateway.stop()
    
    print("Data download complete. Starting backtest...")
    run_backtest()
