import pytest
import dora.tools


@pytest.fixture(autouse=True)
def pin_default_price_source():
    orig = dora.tools.DEFAULT_PRICE_SOURCE
    dora.tools.DEFAULT_PRICE_SOURCE = "magyp_june"
    yield
    dora.tools.DEFAULT_PRICE_SOURCE = orig

