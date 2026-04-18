# tests/test_startup_coordinator.py
from unittest.mock import MagicMock, patch
import pytest
from src.orchestrator.startup_coordinator import StartupCoordinator, AlignedState


def _mock_api(balance=1000.0, positions=None):
    api = MagicMock()
    # get_futures_account_balance() returns {"USDT": float, ...}
    api.get_futures_account_balance.return_value = {"USDT": balance}
    api.get_futures_positions.return_value = positions or []
    return api


def test_fresh_start_returns_exchange_balance():
    """No saved state → use exchange balance, no alignment needed."""
    api = _mock_api(balance=500.0)
    coord = StartupCoordinator(api=api, state_path="/nonexistent/state.json")
    result = coord.prepare()
    assert result.balance == 500.0
    assert result.positions == {}
    assert result.aligned is True


def test_saved_state_with_no_delta_returns_as_is():
    """Saved state matches exchange — no changes needed."""
    api = _mock_api(balance=1000.0, positions=[])
    saved = {
        "balance": 1000.0,
        "positions": {},
    }
    coord = StartupCoordinator(api=api, state_path="/fake/state.json")
    with patch.object(coord, "_load_state", return_value=saved):
        result = coord.prepare()
    assert result.aligned is True
    assert result.balance == 1000.0


def test_saved_position_closed_on_exchange_is_reconciled():
    """Local state has open position; exchange has none → position cleared."""
    api = _mock_api(balance=1100.0, positions=[])
    saved = {
        "balance": 1000.0,
        "positions": {"BTCUSDT": {"size": 0.01, "entry_price": 30000.0}},
    }
    coord = StartupCoordinator(api=api, state_path="/fake/state.json")
    with patch.object(coord, "_load_state", return_value=saved):
        result = coord.prepare()
    assert "BTCUSDT" not in result.positions
    assert result.balance == 1100.0  # uses exchange balance


def test_balance_mismatch_uses_exchange_balance():
    """Exchange balance differs from saved — always trust exchange."""
    api = _mock_api(balance=850.0)
    saved = {"balance": 1000.0, "positions": {}}
    coord = StartupCoordinator(api=api, state_path="/fake/state.json")
    with patch.object(coord, "_load_state", return_value=saved):
        result = coord.prepare()
    assert result.balance == 850.0


# helper
def unittest_mock_open(data):
    import unittest.mock as m, json, io
    return m.mock_open(read_data=json.dumps(data))
