#!/usr/bin/env python3

import asyncio
import datetime
import os

from nautilus_trader.adapters.interactive_brokers.common import IBContract
from nautilus_trader.adapters.interactive_brokers.config import DockerizedIBGatewayConfig
from nautilus_trader.adapters.interactive_brokers.gateway import DockerizedIBGateway
from nautilus_trader.adapters.interactive_brokers.historic import HistoricInteractiveBrokersClient
from nautilus_trader.persistence.catalog import ParquetDataCatalog

async def download_data(host: str | None = None, port: int | None = None) -> None:
    """Download historical data from Interactive Brokers."""
    # Define the contract we want data for
    contract = IBContract(
        secType="STK",
        symbol="AAPL",
        exchange="SMART",
        primaryExchange="NASDAQ",
        build_options_chain=False,
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
        start_date_time=datetime.datetime(2023, 6, 1, 9, 30),
        end_date_time=datetime.datetime(2023, 11, 6, 16, 30),
        tz_name="America/New_York",
        contracts=[contract],
        instrument_ids=[instrument_id_str],
    )

    # Save data to catalog
    catalog = ParquetDataCatalog("./catalog")
    catalog.write_data(instruments)
    catalog.write_data(bars)
    print(catalog.instruments())
    print(catalog.bars())


if __name__ == "__main__":
    print("Starting data download...")
    # You can use either direct connection or dockerized gateway
    # For direct connection to TWS/Gateway:
    asyncio.run(download_data(host="192.168.87.254", port=7497))
    
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
    
    print("Data download complete.")
