# src/orchestrator/startup_coordinator.py
"""StartupCoordinator: load saved state, align with exchange, return ready state.

Usage:
    coord = StartupCoordinator(api=binance_api, state_path="data/state.json")
    state = coord.prepare()
    # state.balance, state.positions are now exchange-accurate
    orchestrator.resume(state)
"""
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.client.binance_api import BinanceAPI

logger = logging.getLogger(__name__)


@dataclass
class AlignedState:
    """Exchange-aligned state ready for the orchestrator to consume."""
    balance: float
    positions: dict  # symbol → {size, entry_price}
    aligned: bool = True


class StartupCoordinator:
    """Loads persisted state and aligns it against live exchange data."""

    def __init__(self, api: BinanceAPI, state_path: str) -> None:
        self._api = api
        self._state_path = Path(state_path)

    # ── public ───────────────────────────────────────────────────────────────

    def prepare(self) -> AlignedState:
        """Return an exchange-accurate AlignedState.

        - If no state file exists: fresh start using exchange balance.
        - If state file exists: run StateAligner to reconcile deltas.
        """
        saved = self._load_state()
        exchange_balance = self._fetch_usdt_balance()
        exchange_positions = self._fetch_open_positions()

        if saved is None:
            logger.info("No saved state — fresh start")
            return AlignedState(balance=exchange_balance, positions={})

        logger.info("Saved state found — running alignment")
        aligner = StateAligner(saved, exchange_balance, exchange_positions)
        return aligner.align()

    # ── internal ─────────────────────────────────────────────────────────────

    def _load_state(self) -> Optional[dict]:
        if not self._state_path.exists():
            return None
        try:
            with open(self._state_path) as f:
                return json.load(f)
        except Exception as exc:
            logger.warning(f"Could not load state file: {exc} — treating as fresh start")
            return None

    def _fetch_usdt_balance(self) -> float:
        # get_futures_account_balance() returns {"USDT": float, "BTC": float, ...}
        balances = self._api.get_futures_account_balance() or {}
        return float(balances.get("USDT", 0.0))

    def _fetch_open_positions(self) -> dict:
        """Return {symbol: {size, entry_price}} for non-zero positions."""
        rows = self._api.get_futures_positions() or []
        return {
            r["symbol"]: {
                "size": float(r.get("positionAmt", 0)),
                "entry_price": float(r.get("entryPrice", 0)),
            }
            for r in rows
            if float(r.get("positionAmt", 0)) != 0
        }


class StateAligner:
    """Reconciles saved local state against live exchange state."""

    def __init__(
        self,
        saved: dict,
        exchange_balance: float,
        exchange_positions: dict,
    ) -> None:
        self._saved = saved
        self._ex_balance = exchange_balance
        self._ex_positions = exchange_positions

    def align(self) -> AlignedState:
        """Apply delta reconciliation rules and return aligned state."""
        saved_positions: dict = self._saved.get("positions", {})
        reconciled = {}

        for symbol, local_pos in saved_positions.items():
            if symbol in self._ex_positions:
                # Position still open on exchange — keep exchange version
                reconciled[symbol] = self._ex_positions[symbol]
                logger.info(f"  {symbol}: position carried over from exchange")
            else:
                # Position closed on exchange while we were offline
                logger.info(f"  {symbol}: position closed on exchange, clearing local")

        # Always trust exchange balance
        if self._ex_balance != self._saved.get("balance"):
            logger.info(
                f"  balance: saved={self._saved.get('balance')}, "
                f"exchange={self._ex_balance} — using exchange"
            )

        return AlignedState(
            balance=self._ex_balance,
            positions=reconciled,
            aligned=True,
        )
