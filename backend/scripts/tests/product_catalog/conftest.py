def pytest_configure(config):
    config.addinivalue_line(
        "filterwarnings",
        "ignore:'asyncio.get_event_loop_policy' is deprecated:DeprecationWarning:pytest_asyncio.plugin",
    )
