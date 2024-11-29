def test_instrument_id_format():
    # Test that the code uses InstrumentId.from_str() for instrument_id
    with open('/workspace/examples/backtest/ib_download_and_backtest.py', 'r') as f:
        code = f.read()
    
    # Check that we're using InstrumentId.from_str() in the strategy config
    assert 'instrument_id=InstrumentId.from_str("AAPL.NASDAQ")' in code, \
        "Strategy config should use InstrumentId.from_str() for instrument_id"
