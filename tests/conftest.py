import os
os.environ.setdefault('DORA_OFFLINE', '1')
import pytest
import dora.tools


@pytest.fixture(autouse=True)
def pin_default_price_source():
    orig = dora.tools.DEFAULT_PRICE_SOURCE
    dora.tools.DEFAULT_PRICE_SOURCE = "magyp_june"
    yield
    dora.tools.DEFAULT_PRICE_SOURCE = orig


@pytest.fixture(autouse=True)
def enforce_dora_offline(request, monkeypatch):
    """Enforce DORA_OFFLINE=1 for all tests,
    except the ones that test the feeds themselves with fakes.
    """
    feed_fake_tests = {
        "test_cbot_symbols_built_for_corn_from_oct_2026",
        "test_mocked_contract_response_and_usd_conversion",
        "test_partial_fetch_does_not_overwrite_good_file",
        "test_network_error_keeps_last_file",
        "test_fresh_file_skips_fetch",
    }
    if request.node.name in feed_fake_tests:
        monkeypatch.delenv("DORA_OFFLINE", raising=False)
        return
    monkeypatch.setenv("DORA_OFFLINE", "1")


try:
    import formulas

    _orig_formulas_load = formulas.ExcelModel.load

    def _load_without_opensolver(self, filename):
        book, context = self.add_book(filename)
        sheets = [ws for ws in book.worksheets if ws.title != "__OpenSolver__"]
        self.pushes(*sheets, context=context)
        return self

    formulas.ExcelModel.load = _load_without_opensolver
except ImportError:
    pass
