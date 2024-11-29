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
import time

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
from nautilus_trader.model.data import BarType
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
        instrument_ids=[instrument_id_str],
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
    )

    # Build the backtest engine
    engine = BacktestEngine(config=config)

    # Add a trading venue (multiple venues possible)
    engine.add_venue(
        venue=NASDAQ,
        oms_type=OmsType.NETTING,
        account_type=AccountType.CASH,
        base_currency=USD,
        starting_balances=[Money(1_000_000, USD)],
    )

    # Load data from catalog
    catalog = ParquetDataCatalog("./catalog")
    instruments = catalog.instruments()
    bars = catalog.bars()

    # Add instruments and data
    for instrument in instruments:
        engine.add_instrument(instrument)
    engine.add_data(bars)

    # Configure your strategy
    config = EMACrossConfig(
        instrument_id=InstrumentId.from_str("AAPL.NASDAQ"),
        bar_type=BarType.from_str("AAPL.NASDAQ-1-HOUR-LAST-EXTERNAL"),
        trade_size=Decimal(100),
        fast_ema_period=10,
        slow_ema_period=20,
    )

    # Instantiate and add your strategy
    strategy = EMACross(config=config)
    engine.add_strategy(strategy=strategy)

    time.sleep(0.1)
    input("Press Enter to continue...")

    # Run the engine (from start to end of data)
    engine.run()

    # View reports
    with pd.option_context(
        "display.max_rows",
        100,
        "display.max_columns",
        None,
        "display.width",
        300,
    ):
        print(engine.trader.generate_account_report(NASDAQ))
        print(engine.trader.generate_order_fills_report())
        print(engine.trader.generate_positions_report())

    # For repeated backtest runs make sure to reset the engine
    engine.reset()

    # Good practice to dispose of the object
    engine.dispose()


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
