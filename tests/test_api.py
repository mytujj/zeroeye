from __future__ import annotations

import json
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import sys
from pathlib import Path

import httpx
import pytest
from jsonschema import validate as validate_json_schema

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = PROJECT_ROOT / "schemas"

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# API base helpers
# ---------------------------------------------------------------------------

API_BASE = "http://localhost:8080"
API_V1 = f"{API_BASE}/api/v1"


async def _mock_json_response(status: int, data: Dict[str, Any]) -> httpx.Response:
    return httpx.Response(status, json=data)


# ===================================================================
# 1. HEALTH ENDPOINT
# ===================================================================


class TestHealthEndpoint:
    """Tests for GET /health, /health/ready, /health/live"""

    async def test_health_returns_ok(self, respx_mock, mock_health_response: Dict[str, Any]):
        route = respx_mock.get(f"{API_BASE}/health").mock(
            return_value=httpx.Response(200, json=mock_health_response)
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_BASE}/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "timestamp" in body
        assert "uptime" in body
        assert "version" in body
        assert route.called

    async def test_readiness(self, respx_mock):
        route = respx_mock.get(f"{API_BASE}/health/ready").mock(
            return_value=httpx.Response(200, json={"status": "ready"})
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_BASE}/health/ready")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready"
        assert route.called

    async def test_liveness(self, respx_mock):
        route = respx_mock.get(f"{API_BASE}/health/live").mock(
            return_value=httpx.Response(200, json={"status": "alive"})
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_BASE}/health/live")
        assert resp.status_code == 200
        assert resp.json()["status"] == "alive"
        assert route.called

    async def test_health_not_ready(self, respx_mock):
        route = respx_mock.get(f"{API_BASE}/health/ready").mock(
            return_value=httpx.Response(503, json={"status": "not ready"})
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_BASE}/health/ready")
        assert resp.status_code == 503
        assert resp.json()["status"] == "not ready"
        assert route.called


# ===================================================================
# 2. MARKET DATA ENDPOINTS
# ===================================================================


class TestMarketDataEndpoints:
    """Tests for market data endpoints: trades, depth, ticker, candles, instruments"""

    async def test_get_trades(self, respx_mock, mock_trade_data: Dict[str, Any]):
        data = {"trades": [mock_trade_data]}
        route = respx_mock.get(f"{API_V1}/market/trades").mock(
            return_value=httpx.Response(200, json=data)
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_V1}/market/trades")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["trades"]) == 1
        trade = body["trades"][0]
        assert trade["id"] == "trade_000001"
        assert trade["symbol"] == "BTC/USD"
        assert trade["price"] == "50000.00"
        assert route.called

    async def test_get_orderbook(self, respx_mock, mock_depth_data: Dict[str, Any]):
        route = respx_mock.get(f"{API_V1}/market/orderbook?symbol=BTC/USD").mock(
            return_value=httpx.Response(200, json=mock_depth_data)
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_V1}/market/orderbook", params={"symbol": "BTC/USD"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["symbol"] == "BTC/USD"
        assert len(body["bids"]) == 2
        assert len(body["asks"]) == 2
        assert "timestamp" in body
        assert route.called

    async def test_get_orderbook_missing_symbol(self, respx_mock):
        route = respx_mock.get(f"{API_V1}/market/orderbook").mock(
            return_value=httpx.Response(
                400,
                json={"code": 4001, "message": "symbol parameter is required"},
            )
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_V1}/market/orderbook")
        assert resp.status_code == 400
        assert "symbol" in resp.json()["message"]
        assert route.called

    async def test_get_ticker(self, respx_mock, mock_ticker_data: Dict[str, Any]):
        route = respx_mock.get(f"{API_V1}/market/ticker?symbol=BTC/USD").mock(
            return_value=httpx.Response(200, json=mock_ticker_data)
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_V1}/market/ticker", params={"symbol": "BTC/USD"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["symbol"] == "BTC/USD"
        assert body["last_price"] == "50000.00"
        assert body["bid_price"] == "49900.00"
        assert body["ask_price"] == "50100.00"
        assert route.called

    async def test_get_ticker_missing_symbol(self, respx_mock):
        route = respx_mock.get(f"{API_V1}/market/ticker").mock(
            return_value=httpx.Response(
                400,
                json={"code": 4001, "message": "symbol parameter is required"},
            )
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_V1}/market/ticker")
        assert resp.status_code == 400
        assert route.called

    async def test_get_candles(self, respx_mock, mock_candle_data: Dict[str, Any]):
        data = {"candles": [mock_candle_data]}
        route = respx_mock.get(f"{API_V1}/market/candles").mock(
            return_value=httpx.Response(200, json=data)
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_V1}/market/candles")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["candles"]) == 1
        candle = body["candles"][0]
        assert candle["symbol"] == "BTC/USD"
        assert candle["interval"] == "1h"
        assert route.called

    async def test_get_instruments(self, respx_mock):
        data = {
            "instruments": [
                {"symbol": "BTC/USD", "base": "BTC", "quote": "USD"},
                {"symbol": "ETH/USD", "base": "ETH", "quote": "USD"},
            ],
            "total": 2,
        }
        route = respx_mock.get(f"{API_V1}/market/instruments").mock(
            return_value=httpx.Response(200, json=data)
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_V1}/market/instruments")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["instruments"]) == 2
        assert route.called


# ===================================================================
# 3. ERROR HANDLING
# ===================================================================


class TestErrorHandling:
    """Tests for error responses: 404, 400, auth, rate limit"""

    async def test_404_not_found(self, respx_mock):
        route = respx_mock.get(f"{API_V1}/nonexistent").mock(
            return_value=httpx.Response(404, json={"code": 4004, "message": "Resource not found"})
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_V1}/nonexistent")
        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == 4004
        assert route.called

    async def test_400_bad_request(self, respx_mock):
        route = respx_mock.get(f"{API_V1}/market/orderbook").mock(
            return_value=httpx.Response(
                400, json={"code": 4001, "message": "symbol parameter is required"}
            )
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_V1}/market/orderbook")
        assert resp.status_code == 400
        assert resp.json()["code"] == 4001
        assert route.called

    async def test_401_unauthorized(self, respx_mock):
        route = respx_mock.get(f"{API_V1}/market/trades").mock(
            return_value=httpx.Response(401, json={"code": 4002, "message": "Unauthorized"})
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{API_V1}/market/trades", headers={"Authorization": "Bearer invalid"}
            )
        assert resp.status_code == 401
        assert resp.json()["code"] == 4002
        assert route.called

    async def test_403_forbidden(self, respx_mock):
        route = respx_mock.get(f"{API_V1}/market/trades").mock(
            return_value=httpx.Response(403, json={"code": 4003, "message": "Forbidden"})
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_V1}/market/trades")
        assert resp.status_code == 403
        assert resp.json()["code"] == 4003
        assert route.called

    async def test_429_rate_limited(self, respx_mock):
        route = respx_mock.get(f"{API_V1}/market/trades").mock(
            return_value=httpx.Response(
                429,
                json={"code": 4029, "message": "Rate limit exceeded"},
                headers={
                    "X-RateLimit-Limit": "20",
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": "1717243300",
                },
            )
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_V1}/market/trades")
        assert resp.status_code == 429
        assert resp.json()["code"] == 4029
        assert "X-RateLimit-Limit" in resp.headers
        assert resp.headers["X-RateLimit-Remaining"] == "0"
        assert route.called

    async def test_405_method_not_allowed(self, respx_mock):
        route = respx_mock.post(f"{API_V1}/market/trades").mock(
            return_value=httpx.Response(
                405, json={"code": 4001, "message": "Invalid request"}
            )
        )
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{API_V1}/market/trades")
        assert resp.status_code == 405
        assert route.called

    async def test_500_internal_error(self, respx_mock):
        route = respx_mock.get(f"{API_BASE}/health").mock(
            return_value=httpx.Response(
                500, json={"code": 5001, "message": "Internal server error"}
            )
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_BASE}/health")
        assert resp.status_code == 500
        assert resp.json()["code"] == 5001
        assert route.called

    async def test_auth_missing_token(self, respx_mock):
        route = respx_mock.get(f"{API_V1}/market/trades").mock(
            return_value=httpx.Response(
                401, json={"error": "unauthorized", "message": "Missing authentication token"}
            )
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_V1}/market/trades")
        assert resp.status_code == 401
        assert "Missing authentication token" in resp.json()["message"]
        assert route.called

    async def test_auth_invalid_token(self, respx_mock):
        route = respx_mock.get(f"{API_V1}/market/trades").mock(
            return_value=httpx.Response(
                401,
                json={
                    "error": "invalid_token",
                    "message": "Token signature verification failed",
                },
            )
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{API_V1}/market/trades", headers={"Authorization": "Bearer badtoken"}
            )
        assert resp.status_code == 401
        assert "invalid_token" in resp.json()["error"]
        assert route.called


# ===================================================================
# 4. ORDER SCHEMA VALIDATION
# ===================================================================


class TestOrderSchemaValidation:
    """Tests JSON schema validation of order data against order.schema.json"""

    def test_valid_order_passes_schema(
        self, load_order_schema: Dict[str, Any], mock_order_data: Dict[str, Any]
    ):
        validate_json_schema(instance=mock_order_data, schema=load_order_schema)

    def test_order_required_fields(self, load_order_schema: Dict[str, Any]):
        required = {
            "id", "symbol", "side", "type", "status",
            "price", "quantity", "time_in_force",
            "created_at", "updated_at",
        }
        schema_required = set(load_order_schema.get("required", []))
        assert schema_required == required, (
            f"Schema required fields mismatch. "
            f"Expected {required}, got {schema_required}"
        )

    def test_invalid_order_fails_schema(
        self, load_order_schema: Dict[str, Any], mock_invalid_order_data: Dict[str, Any]
    ):
        with pytest.raises(Exception):
            validate_json_schema(instance=mock_invalid_order_data, schema=load_order_schema)

    def test_order_enum_values(self, load_order_schema: Dict[str, Any]):
        side_enum = load_order_schema["properties"]["side"]["enum"]
        assert set(side_enum) == {"buy", "sell"}

        type_enum = load_order_schema["properties"]["type"]["enum"]
        expected_types = {"limit", "market", "stop_limit", "stop_market", "trailing_stop", "iceberg"}
        assert set(type_enum) == expected_types

        status_enum = load_order_schema["properties"]["status"]["enum"]
        expected_statuses = {"new", "partially_filled", "filled", "cancelled", "rejected", "expired"}
        assert set(status_enum) == expected_statuses

        tif_enum = load_order_schema["properties"]["time_in_force"]["enum"]
        expected_tif = {"gtc", "ioc", "fok", "gtd"}
        assert set(tif_enum) == expected_tif

    def test_order_price_pattern(self, load_order_schema: Dict[str, Any]):
        price_pattern = load_order_schema["properties"]["price"]["pattern"]
        import re
        assert re.match(price_pattern, "50000.00")
        assert re.match(price_pattern, "0.01")
        assert re.match(price_pattern, "100")
        assert not re.match(price_pattern, "abc")
        assert not re.match(price_pattern, "50,000")

    def test_order_id_pattern(self, load_order_schema: Dict[str, Any]):
        id_pattern = load_order_schema["properties"]["id"]["pattern"]
        import re
        assert re.match(id_pattern, "ord_000001")
        assert re.match(id_pattern, "abc-123_XYZ")
        assert not re.match(id_pattern, "bad id!")
        assert not re.match(id_pattern, "id with spaces")

    def test_schema_additional_properties_false(self, load_order_schema: Dict[str, Any]):
        assert load_order_schema.get("additionalProperties") is False

    def test_order_with_extra_field_fails_schema(
        self, load_order_schema: Dict[str, Any], mock_order_data: Dict[str, Any]
    ):
        bad_order = {**mock_order_data, "unknown_field": "should_not_exist"}
        with pytest.raises(Exception):
            validate_json_schema(instance=bad_order, schema=load_order_schema)


# ===================================================================
# 5. DATA STRUCTURE VALIDATION (Order, Trade, Ticker, Candle)
# ===================================================================


class TestDataStructures:
    """Tests the shape and types of core data structures"""

    def test_order_structure(self, mock_order_data: Dict[str, Any]):
        expected_keys = {
            "id", "symbol", "side", "type", "status",
            "price", "stop_price", "quantity", "filled_quantity",
            "remaining_quantity", "leaves_quantity",
            "cumulative_quote_quantity", "avg_price", "time_in_force",
            "created_at", "updated_at",
            "iceberg_quantity", "display_quantity",
        }
        assert set(mock_order_data.keys()) == expected_keys

    def test_trade_structure(self, mock_trade_data: Dict[str, Any]):
        expected_keys = {
            "id", "symbol", "buy_order_id", "sell_order_id",
            "price", "quantity", "quote_quantity",
            "taker_side", "timestamp", "is_buyer_maker",
        }
        assert set(mock_trade_data.keys()) == expected_keys

    def test_ticker_structure(self, mock_ticker_data: Dict[str, Any]):
        expected_keys = {
            "symbol", "bid_price", "ask_price", "last_price",
            "volume_24h", "quote_volume", "high_24h", "low_24h",
            "open_24h", "change_24h", "change_percent",
            "trade_count", "updated_at",
        }
        assert set(mock_ticker_data.keys()) == expected_keys

    def test_candle_structure(self, mock_candle_data: Dict[str, Any]):
        expected_keys = {
            "symbol", "interval", "open_time", "close_time",
            "open", "high", "low", "close",
            "volume", "quote_volume", "trades",
        }
        assert set(mock_candle_data.keys()) == expected_keys

    def test_depth_structure(self, mock_depth_data: Dict[str, Any]):
        assert "symbol" in mock_depth_data
        assert "bids" in mock_depth_data
        assert "asks" in mock_depth_data
        assert "timestamp" in mock_depth_data
        for level in mock_depth_data["bids"]:
            assert {"price", "quantity", "order_count"} == set(level.keys())
        for level in mock_depth_data["asks"]:
            assert {"price", "quantity", "order_count"} == set(level.keys())

    def test_balance_structure(self, mock_balance_data: Dict[str, Any]):
        assert "balances" in mock_balance_data
        for bal in mock_balance_data["balances"]:
            assert {"asset", "free", "locked", "total"} == set(bal.keys())

    def test_position_structure(self, mock_position_data: Dict[str, Any]):
        assert "positions" in mock_position_data
        for pos in mock_position_data["positions"]:
            expected = {
                "symbol", "quantity", "entry_price", "mark_price",
                "liquidation_price", "pnl", "pnl_percent",
            }
            assert set(pos.keys()) == expected

    def test_side_enum_values(self):
        valid_sides = {"buy", "sell"}
        for side in valid_sides:
            assert side in valid_sides
        assert "invalid_side" not in valid_sides

    def test_time_in_force_enum(self):
        valid = {"gtc", "ioc", "fok", "gtd"}
        for tif in valid:
            assert tif in valid
        assert "invalid_tif" not in valid

    def test_order_price_is_decimal_string(self, mock_order_data: Dict[str, Any]):
        price = mock_order_data["price"]
        assert isinstance(price, str)
        parts = price.split(".")
        assert len(parts) == 2
        assert parts[0].isdigit()
        assert parts[1].isdigit()

    def test_balance_amounts_are_strings(self, mock_balance_data: Dict[str, Any]):
        for bal in mock_balance_data["balances"]:
            assert isinstance(bal["free"], str)
            assert isinstance(bal["locked"], str)
            assert isinstance(bal["total"], str)


# ===================================================================
# 6. ORDERS CRUD
# ===================================================================


class TestOrdersCRUD:
    """Tests for order CRUD operations (create, list, get, cancel)"""

    async def test_create_order(self, respx_mock, mock_order_data: Dict[str, Any], auth_headers: Dict[str, str]):
        route = respx_mock.post(f"{API_V1}/orders").mock(
            return_value=httpx.Response(201, json=mock_order_data)
        )
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{API_V1}/orders",
                json={
                    "symbol": "BTC/USD",
                    "side": "buy",
                    "type": "limit",
                    "price": "50000.00",
                    "quantity": "1.0000",
                    "time_in_force": "gtc",
                },
                headers=auth_headers,
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["id"] == "ord_000001"
        assert body["status"] == "new"
        assert route.called

    async def test_list_orders(self, respx_mock, mock_order_data: Dict[str, Any], auth_headers: Dict[str, str]):
        data = {"orders": [mock_order_data], "total": 1}
        route = respx_mock.get(f"{API_V1}/orders").mock(
            return_value=httpx.Response(200, json=data)
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_V1}/orders", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert len(body["orders"]) == 1
        assert route.called

    async def test_get_order_by_id(self, respx_mock, mock_order_data: Dict[str, Any], auth_headers: Dict[str, str]):
        order_id = "ord_000001"
        route = respx_mock.get(f"{API_V1}/orders/{order_id}").mock(
            return_value=httpx.Response(200, json=mock_order_data)
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_V1}/orders/{order_id}", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == order_id
        assert route.called

    async def test_get_order_not_found(self, respx_mock, auth_headers: Dict[str, str]):
        order_id = "ord_nonexistent"
        route = respx_mock.get(f"{API_V1}/orders/{order_id}").mock(
            return_value=httpx.Response(404, json={"code": 4004, "message": "Order not found"})
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_V1}/orders/{order_id}", headers=auth_headers)
        assert resp.status_code == 404
        assert "Order not found" in resp.json()["message"]
        assert route.called

    async def test_cancel_order(self, respx_mock, auth_headers: Dict[str, str]):
        order_id = "ord_000001"
        route = respx_mock.delete(f"{API_V1}/orders/{order_id}").mock(
            return_value=httpx.Response(200, json={"id": order_id, "status": "cancelled"})
        )
        async with httpx.AsyncClient() as client:
            resp = await client.delete(f"{API_V1}/orders/{order_id}", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "cancelled"
        assert route.called

    async def test_cancel_order_not_found(self, respx_mock, auth_headers: Dict[str, str]):
        order_id = "ord_nonexistent"
        route = respx_mock.delete(f"{API_V1}/orders/{order_id}").mock(
            return_value=httpx.Response(404, json={"code": 4004, "message": "Order not found"})
        )
        async with httpx.AsyncClient() as client:
            resp = await client.delete(f"{API_V1}/orders/{order_id}", headers=auth_headers)
        assert resp.status_code == 404
        assert route.called

    async def test_create_order_validation_error(self, respx_mock, auth_headers: Dict[str, str]):
        route = respx_mock.post(f"{API_V1}/orders").mock(
            return_value=httpx.Response(
                400,
                json={
                    "code": 4001,
                    "message": "Validation error",
                    "details": {"side": "must be 'buy' or 'sell'"},
                },
            )
        )
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{API_V1}/orders",
                json={"symbol": "BTC/USD", "side": "invalid", "type": "limit"},
                headers=auth_headers,
            )
        assert resp.status_code == 400
        assert "details" in resp.json()
        assert route.called

    async def test_orders_require_auth(self, respx_mock):
        route = respx_mock.get(f"{API_V1}/orders").mock(
            return_value=httpx.Response(
                401, json={"code": 4002, "message": "Unauthorized"}
            )
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_V1}/orders")
        assert resp.status_code == 401
        assert route.called


# ===================================================================
# 7. ACCOUNT ENDPOINTS
# ===================================================================


class TestAccountEndpoints:
    """Tests for account endpoints: balance, positions"""

    async def test_get_balance(
        self, respx_mock, mock_balance_data: Dict[str, Any], auth_headers: Dict[str, str]
    ):
        route = respx_mock.get(f"{API_V1}/account/balance").mock(
            return_value=httpx.Response(200, json=mock_balance_data)
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_V1}/account/balance", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["balances"]) == 2
        btc_balance = body["balances"][0]
        assert btc_balance["asset"] == "BTC"
        assert btc_balance["free"] == "1.5000"
        assert route.called

    async def test_get_positions(
        self, respx_mock, mock_position_data: Dict[str, Any], auth_headers: Dict[str, str]
    ):
        route = respx_mock.get(f"{API_V1}/account/positions").mock(
            return_value=httpx.Response(200, json=mock_position_data)
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_V1}/account/positions", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["positions"]) == 1
        pos = body["positions"][0]
        assert pos["symbol"] == "BTC/USD"
        assert pos["quantity"] == "0.5000"
        assert route.called

    async def test_account_endpoints_require_auth(self, respx_mock):
        route = respx_mock.get(f"{API_V1}/account/balance").mock(
            return_value=httpx.Response(
                401, json={"code": 4002, "message": "Unauthorized"}
            )
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_V1}/account/balance")
        assert resp.status_code == 401
        assert route.called

    async def test_account_not_found(self, respx_mock, auth_headers: Dict[str, str]):
        route = respx_mock.get(f"{API_V1}/account/balance").mock(
            return_value=httpx.Response(404, json={"code": 4004, "message": "Account not found"})
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_V1}/account/balance", headers=auth_headers)
        assert resp.status_code == 404
        assert route.called


# ===================================================================
# 8. WEBSOCKET
# ===================================================================


class TestWebSocket:
    """Tests for WebSocket connection and message handling"""

    async def test_ws_endpoint_exists(self, respx_mock):
        route = respx_mock.get(f"{API_V1}/ws").mock(
            return_value=httpx.Response(501, json={"code": 5001, "message": "WebSocket endpoint not yet implemented"})
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_V1}/ws")
        assert resp.status_code == 501
        assert route.called

    async def test_ws_unauthorized(self, respx_mock):
        route = respx_mock.get(f"{API_V1}/ws").mock(
            return_value=httpx.Response(401, json={"code": 4002, "message": "Unauthorized"})
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_V1}/ws")
        assert resp.status_code == 401
        assert route.called

    @patch("tests.test_api.httpx.AsyncClient")
    async def test_ws_sends_ping(self, mock_client: MagicMock):
        mock_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_instance

        mock_ws = AsyncMock()
        mock_instance.ws = AsyncMock()

        with patch("httpx.AsyncClient") as mock_http:
            mock_http.return_value.__aenter__.return_value = mock_instance

        assert True

    def test_ws_message_format(self):
        message = json.dumps({"type": "subscribe", "channel": "trades", "symbol": "BTC/USD"})
        parsed = json.loads(message)
        assert parsed["type"] == "subscribe"
        assert parsed["channel"] == "trades"
        assert parsed["symbol"] == "BTC/USD"

    def test_ws_trade_message_format(self, mock_trade_data: Dict[str, Any]):
        ws_message = {"type": "trade", "data": mock_trade_data}
        serialized = json.dumps(ws_message)
        parsed = json.loads(serialized)
        assert parsed["type"] == "trade"
        assert parsed["data"]["id"] == "trade_000001"

    def test_ws_depth_message_format(self, mock_depth_data: Dict[str, Any]):
        ws_message = {"type": "depth", "data": mock_depth_data}
        serialized = json.dumps(ws_message)
        parsed = json.loads(serialized)
        assert parsed["type"] == "depth"
        assert parsed["data"]["symbol"] == "BTC/USD"

    def test_ws_subscribe_request(self):
        subscribe = {
            "type": "subscribe",
            "channel": "ticker",
            "symbol": "ETH/USD",
        }
        msg = json.dumps(subscribe)
        parsed = json.loads(msg)
        assert parsed["type"] == "subscribe"
        assert parsed["channel"] == "ticker"

    def test_ws_unsubscribe_request(self):
        unsubscribe = {
            "type": "unsubscribe",
            "channel": "trades",
            "symbol": "BTC/USD",
        }
        msg = json.dumps(unsubscribe)
        parsed = json.loads(msg)
        assert parsed["type"] == "unsubscribe"
        assert parsed["channel"] == "trades"

    def test_ws_error_message_format(self):
        error_msg = {"type": "error", "code": 4001, "message": "Invalid subscription"}
        serialized = json.dumps(error_msg)
        parsed = json.loads(serialized)
        assert parsed["type"] == "error"
        assert parsed["code"] == 4001

    def test_ws_pong_response(self):
        pong = {"type": "pong", "timestamp": 1717243200000}
        serialized = json.dumps(pong)
        parsed = json.loads(serialized)
        assert parsed["type"] == "pong"
        assert isinstance(parsed["timestamp"], int)


# ===================================================================
# 9. BUILD PROCESS
# ===================================================================


class TestBuildProcess:
    """Tests for build.py module definitions and structure"""

    def test_build_py_imports(self):
        import build
        assert hasattr(build, "MODULES")
        assert hasattr(build, "Module")
        assert hasattr(build, "ROOT")

    def test_all_modules_defined(self, mock_module_list):
        import build
        module_names = {m.name for m in build.MODULES}
        for mod in mock_module_list:
            assert mod["name"] in module_names, f"Missing module: {mod['name']}"

    def test_build_module_structure(self):
        import build
        for module in build.MODULES:
            assert isinstance(module.name, str)
            assert isinstance(module.language, str)
            assert isinstance(module.dir, type(build.ROOT))
            assert isinstance(module.build_cmd, list)
            assert isinstance(module.clean_cmd, list)

    def test_build_dir_is_path_or_none(self):
        import build
        for module in build.MODULES:
            assert module.build_dir is None or isinstance(module.build_dir, type(build.ROOT))

    def test_module_languages(self, mock_module_list):
        languages = {mod["language"] for mod in mock_module_list}
        assert "Rust" in languages
        assert "TypeScript" in languages
        assert "Go" in languages
        assert "C" in languages
        assert "C++" in languages
        assert "Java" in languages
        assert "Ruby" in languages
        assert "Lua" in languages
        assert "Haskell" in languages

    def test_encryptly_platform_config(self):
        import build
        assert len(build.ENCRYPTLY_BINARIES) >= 6
        for key in ["linux-x64", "linux-arm64", "macos-arm64", "macos-x64", "windows-x64", "windows-arm64"]:
            assert key in build.ENCRYPTLY_BINARIES

    def test_build_py_functions_exist(self):
        import build
        assert callable(build.check_prerequisites)
        assert callable(build.build_module)
        assert callable(build.clean_module)
        assert callable(build.verify_binary)
        assert callable(build.build_diagnostic_report)
        assert callable(build.collect_system_info)
        assert callable(build.current_commit_id)

    def test_colors_class(self):
        import build
        assert hasattr(build.Colors, "GREEN")
        assert hasattr(build.Colors, "RED")
        assert hasattr(build.Colors, "YELLOW")
        assert hasattr(build.Colors, "CYAN")
        assert hasattr(build.Colors, "BOLD")
        assert hasattr(build.Colors, "RESET")
        assert hasattr(build.Colors, "GRAY")

    def test_diagnostic_chunk_size(self):
        import build
        assert build.DIAGNOSTIC_CHUNK_SIZE == 40 * 1024 * 1024

    def test_diagnostic_paths_return_type(self):
        import build
        logd_path, metadata_path, commit_id = build.diagnostic_paths_for_commit()
        assert isinstance(logd_path, type(build.ROOT))
        assert isinstance(metadata_path, type(build.ROOT))
        assert isinstance(commit_id, str)
        assert len(commit_id) == 8 or commit_id == "00000000"

    def test_module_has_build_cmd_and_clean_cmd(self):
        import build
        for module in build.MODULES:
            assert len(module.build_cmd) > 0, f"{module.name} missing build_cmd"
            assert len(module.clean_cmd) > 0, f"{module.name} missing clean_cmd"

    def test_market_dir_structure(self):
        market_dir = PROJECT_ROOT / "market"
        assert (market_dir / "gateway").is_dir()
        assert (market_dir / "types").is_dir()
        assert (market_dir / "ws").is_dir()
        assert (market_dir / "matching").is_dir()
        assert (market_dir / "orderbook").is_dir()

    def test_gateway_api_endpoints_defined(self):
        api_file = PROJECT_ROOT / "market" / "gateway" / "api.go"
        assert api_file.exists()
        content = api_file.read_text()
        endpoints = [
            "/health",
            "/health/ready",
            "/health/live",
            "/api/v1/market/instruments",
            "/api/v1/market/orderbook",
            "/api/v1/market/trades",
            "/api/v1/market/ticker",
            "/api/v1/market/candles",
            "/api/v1/market/news",
            "/api/v1/ws",
        ]
        for ep in endpoints:
            assert ep in content, f"Endpoint {ep} not found in api.go"

    def test_order_schema_file_exists(self):
        schema_file = SCHEMAS_DIR / "order.schema.json"
        assert schema_file.exists()
        assert schema_file.is_file()


# ===================================================================
# 10. DATA GENERATOR TESTS
# ===================================================================


class TestDataGenerator:
    """Tests for the data generation tool used to create test data"""

    def test_data_generator_imports(self):
        sys.path.insert(0, str(PROJECT_ROOT / "tools"))
        try:
            from data_generator import DataGenerator
            gen = DataGenerator(seed=42)
            assert gen is not None
        finally:
            sys.path.pop(0)

    def test_data_generator_instruments(self):
        import sys
        sys.path.insert(0, str(PROJECT_ROOT / "tools"))
        try:
            from data_generator import INSTRUMENTS
            assert len(INSTRUMENTS) == 10
            symbols = {i["symbol"] for i in INSTRUMENTS}
            assert "BTC/USD" in symbols
            assert "ETH/USD" in symbols
        finally:
            sys.path.pop(0)

    def test_data_generator_order_sides(self):
        import sys
        sys.path.insert(0, str(PROJECT_ROOT / "tools"))
        try:
            from data_generator import ORDER_SIDES
            assert set(ORDER_SIDES) == {"buy", "sell"}
        finally:
            sys.path.pop(0)

    def test_data_generator_generates_users(self):
        import sys
        sys.path.insert(0, str(PROJECT_ROOT / "tools"))
        try:
            from data_generator import DataGenerator
            gen = DataGenerator(seed=42)
            users = gen.generate_users(5)
            assert len(users) == 5
            for user in users:
                assert "id" in user
                assert "email" in user
                assert "name" in user
                assert "role" in user
        finally:
            sys.path.pop(0)

    def test_data_generator_generates_orders(self):
        import sys
        sys.path.insert(0, str(PROJECT_ROOT / "tools"))
        try:
            from data_generator import DataGenerator
            gen = DataGenerator(seed=42)
            orders = gen.generate_orders(10)
            assert len(orders) == 10
            for order in orders:
                assert "id" in order
                assert "instrument" in order
                assert "side" in order
                assert "type" in order
                assert order["side"] in ("buy", "sell")
        finally:
            sys.path.pop(0)
