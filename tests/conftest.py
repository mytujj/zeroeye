from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
import pytest_asyncio

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = PROJECT_ROOT / "schemas"
MODULES_DIR = PROJECT_ROOT / "market"


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_order_data() -> Dict[str, Any]:
    return {
        "id": "ord_000001",
        "symbol": "BTC/USD",
        "side": "buy",
        "type": "limit",
        "status": "new",
        "price": "50000.00",
        "stop_price": "0.0000",
        "quantity": "1.0000",
        "filled_quantity": "0.0000",
        "remaining_quantity": "1.0000",
        "leaves_quantity": "1.0000",
        "cumulative_quote_quantity": "0.0000",
        "avg_price": "0.0000",
        "time_in_force": "gtc",
        "created_at": "2024-06-01T12:00:00Z",
        "updated_at": "2024-06-01T12:00:00Z",
        "iceberg_quantity": "0.0000",
        "display_quantity": "1.0000",
    }


@pytest.fixture
def mock_invalid_order_data() -> Dict[str, Any]:
    return {
        "id": "ord_bad",
        "symbol": "BTC/USD",
    }


@pytest.fixture
def mock_trade_data() -> Dict[str, Any]:
    return {
        "id": "trade_000001",
        "symbol": "BTC/USD",
        "buy_order_id": "ord_000001",
        "sell_order_id": "ord_000002",
        "price": "50000.00",
        "quantity": "0.5000",
        "quote_quantity": "25000.00",
        "taker_side": "buy",
        "timestamp": "2024-06-01T12:00:05Z",
        "is_buyer_maker": False,
    }


@pytest.fixture
def mock_ticker_data() -> Dict[str, Any]:
    return {
        "symbol": "BTC/USD",
        "bid_price": "49900.00",
        "ask_price": "50100.00",
        "last_price": "50000.00",
        "volume_24h": "1000.50",
        "quote_volume": "50025000.00",
        "high_24h": "51000.00",
        "low_24h": "49000.00",
        "open_24h": "50500.00",
        "change_24h": "-500.00",
        "change_percent": "-0.99",
        "trade_count": 15234,
        "updated_at": "2024-06-01T12:00:00Z",
    }


@pytest.fixture
def mock_candle_data() -> Dict[str, Any]:
    return {
        "symbol": "BTC/USD",
        "interval": "1h",
        "open_time": "2024-06-01T11:00:00Z",
        "close_time": "2024-06-01T12:00:00Z",
        "open": "50000.00",
        "high": "50500.00",
        "low": "49800.00",
        "close": "50200.00",
        "volume": "150.50",
        "quote_volume": "7525000.00",
        "trades": 1234,
    }


@pytest.fixture
def mock_depth_data() -> Dict[str, Any]:
    return {
        "symbol": "BTC/USD",
        "bids": [
            {"price": "49900.00", "quantity": "1.5000", "order_count": 3},
            {"price": "49850.00", "quantity": "2.0000", "order_count": 5},
        ],
        "asks": [
            {"price": "50100.00", "quantity": "0.8000", "order_count": 2},
            {"price": "50150.00", "quantity": "1.2000", "order_count": 4},
        ],
        "timestamp": 1717243200000,
    }


@pytest.fixture
def mock_balance_data() -> Dict[str, Any]:
    return {
        "balances": [
            {"asset": "BTC", "free": "1.5000", "locked": "0.5000", "total": "2.0000"},
            {"asset": "USD", "free": "50000.00", "locked": "25000.00", "total": "75000.00"},
        ]
    }


@pytest.fixture
def mock_position_data() -> Dict[str, Any]:
    return {
        "positions": [
            {
                "symbol": "BTC/USD",
                "quantity": "0.5000",
                "entry_price": "48000.00",
                "mark_price": "50000.00",
                "liquidation_price": "45000.00",
                "pnl": "1000.00",
                "pnl_percent": "4.17",
            }
        ]
    }


# ---------------------------------------------------------------------------
# Health / error response fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_health_response() -> Dict[str, Any]:
    return {
        "status": "ok",
        "timestamp": "2024-06-01T12:00:00Z",
        "uptime": "72h15m30s",
        "version": "3.0",
    }


@pytest.fixture
def mock_error_response() -> Dict[str, Any]:
    return {
        "code": 4004,
        "message": "Resource not found",
        "request_id": "req_abc123",
    }


# ---------------------------------------------------------------------------
# Auth fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_token() -> str:
    return "test-api-key-abc123def456"


@pytest.fixture
def auth_headers(auth_token: str) -> Dict[str, str]:
    return {"X-API-Key": auth_token}


@pytest.fixture
def bearer_headers() -> Dict[str, str]:
    return {"Authorization": "Bearer test-jwt-token-xyz"}


# ---------------------------------------------------------------------------
# Schema loader
# ---------------------------------------------------------------------------

@pytest.fixture
def load_order_schema() -> Dict[str, Any]:
    schema_path = SCHEMAS_DIR / "order.schema.json"
    if not schema_path.exists():
        pytest.skip("order.schema.json not found")
    with open(schema_path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Build module fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_module_list() -> List[Dict[str, Any]]:
    return [
        {"name": "backend", "language": "Rust"},
        {"name": "frontend", "language": "TypeScript"},
        {"name": "market", "language": "Go"},
        {"name": "frailbox", "language": "C"},
        {"name": "engine", "language": "C++"},
        {"name": "compliance", "language": "Java"},
        {"name": "v2-market-stream", "language": "Ruby"},
        {"name": "nfc-scanner", "language": "Lua"},
        {"name": "openapi-haskell", "language": "Haskell"},
        {"name": "openapi-tools", "language": "Lua"},
    ]


# ---------------------------------------------------------------------------
# Async mock HTTP client
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def mock_http_client() -> AsyncMock:
    client = AsyncMock(spec=httpx.AsyncClient)
    return client


@pytest.fixture
def mock_httpx_transport() -> Mock:
    transport = Mock(spec=httpx.AsyncClientTransport)
    return transport
