#!/usr/bin/env python3

from decimal import Decimal
import pandas as pd
import time

from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.engine import BacktestEngineConfig
from nautilus_trader.config import LoggingConfig
from nautilus_trader.examples.strategies.talib_strategy import TALibStrategy
from nautilus_trader.examples.strategies.talib_strategy import TALibStrategyConfig
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.enums import AccountType
from nautilus_trader.model.enums import OmsType
from nautilus_trader.model.identifiers import InstrumentId, Venue
from nautilus_trader.model.objects import Money
from nautilus_trader.model.data import BarType
from nautilus_trader.model.identifiers import TraderId
from nautilus_trader.persistence.catalog import ParquetDataCatalog

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

    # Add a trading venue
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
    config = TALibStrategyConfig(
        instrument_id=InstrumentId.from_str("AAPL.NASDAQ"),
        bar_type=BarType.from_str("AAPL.NASDAQ-1-HOUR-LAST-EXTERNAL"),
        trade_size=Decimal(100),
    )

    # Instantiate and add your strategy
    strategy = TALibStrategy(config=config)
    engine.add_strategy(strategy=strategy)

    time.sleep(0.1)

    # Run the engine
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

    # Reset and dispose
    engine.reset()
    engine.dispose()

if __name__ == "__main__":
    print("Starting backtest...")
    run_backtest()
    print("Backtest complete.")
